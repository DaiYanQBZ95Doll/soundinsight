# -*- coding: utf-8 -*-
"""W2：多标签归因的逐类阈值——在 `val_v3_tune` 上选，在 `val_v3_test` 上报告。

为什么这样做（缺憾 A1-6 / A1-8）：
v1 的逐类阈值是在**同一验证划分**上网格搜索得到的（`per_class_thresholds_probe.json`
自注"指标偏乐观，仅供收益量级参考"），宏 F1 0.6481 → 0.7834 因此不可直接对外引用。
本脚本把"选阈值"与"报指标"分开：阈值只在 tune 上选，指标只在 test 上报。

DoD（冻结清单 §二 W2）：
- 阈值取自 `val_v3_tune`；
- `val_v3_test` 上宏 F1 ≥ 0.6481`[v1]`，且高音类 F1 ≥ 0.5（或给出明确失败边界）。

用法：python v2_w2_perclass.py [--max-len 128]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np
import torch
from sklearn.metrics import f1_score, precision_recall_fscore_support
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "multi_label_model")
TUNE_CSV = os.path.join(HERE, "val_v3_tune.csv")
TEST_CSV = os.path.join(HERE, "val_v3_test.csv")
V2_CSV = os.path.join(HERE, "val_v2.csv")
OUT_DIR = os.path.join(HERE, "v2")
GRID = tuple(round(x, 2) for x in np.arange(0.05, 0.96, 0.05))
FROZEN_UNIFIED = 0.6481          # [v1] 统一 0.5 档宏 F1
PROBE_OPTIMISTIC = 0.7834        # [v1] 同集选阈值的乐观值（不可对外）


def load(path, cols=("issue_bass_llm", "issue_clarity_llm", "issue_noise_llm",
                     "issue_volume_llm", "issue_treble_llm")):
    texts, ys = [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            texts.append(str(row["text"]))
            ys.append([int(float(row.get(c) or 0)) for c in cols])
    return texts, np.array(ys, dtype=int)


@torch.no_grad()
def predict(texts, tok, model, device, max_len, bs=64):
    out = []
    for i in range(0, len(texts), bs):
        enc = tok(texts[i:i + bs], truncation=True, max_length=max_len,
                  padding=True, return_tensors="pt").to(device)
        out.append(torch.sigmoid(model(**enc).logits).cpu().numpy())
    return np.vstack(out) if out else np.zeros((0, 5), dtype=np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-len", type=int, default=128)
    args = ap.parse_args()

    for p in (TUNE_CSV, TEST_CSV):
        if not os.path.isfile(p):
            print(f"[FAIL] 缺少 {p}（先跑 v2_w6_split.py）")
            return 1
    labels_path = os.path.join(MODEL_DIR, "issue_labels.json")
    names = json.load(open(labels_path, encoding="utf-8")) if os.path.isfile(labels_path) \
        else ["低音", "清晰度", "杂音", "音量", "高音"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_DIR).to(device).eval()
    print(f"device={device} | 类别 {names}")

    res = {}
    for tag, path in (("tune", TUNE_CSV), ("test", TEST_CSV), ("val_v2", V2_CSV)):
        texts, Y = load(path)
        P = predict(texts, tok, model, device, args.max_len)
        res[tag] = {"texts": texts, "Y": Y, "P": P}
        print(f"{tag}: {len(texts)} 行，各类正例 {Y.sum(axis=0).tolist()}")

    # 1) 在 tune 上逐类网格搜索
    Yt, Pt = res["tune"]["Y"], res["tune"]["P"]
    chosen = {}
    for j, name in enumerate(names):
        best, best_f1 = 0.5, -1.0
        for thr in GRID:
            f1 = f1_score(Yt[:, j], (Pt[:, j] >= thr).astype(int), zero_division=0)
            if f1 > best_f1:
                best, best_f1 = thr, f1
        chosen[name] = {"thr": best, "tune_f1": round(float(best_f1), 4)}
        print(f"  [tune 选中] {name}: thr={best} (tune F1 {best_f1:.4f})")

    # 2) 在 test 上报（统一 0.5 与 tune 阈值两行）
    Ys, Ps = res["test"]["Y"], res["test"]["P"]
    macros = {}
    per_class = {}
    for tag, thrs in (("unified_0.5", [0.5] * len(names)),
                      ("tuned_on_tune", [chosen[n]["thr"] for n in names])):
        pred = np.stack([(Ps[:, j] >= thrs[j]).astype(int) for j in range(len(names))], 1)
        macros[tag] = round(float(f1_score(Ys, pred, average="macro", zero_division=0)), 4)
        pr, rc, f1, sup = precision_recall_fscore_support(Ys, pred, zero_division=0)
        per_class[tag] = {names[j]: {"P": round(float(pr[j]) * 100, 1),
                                     "R": round(float(rc[j]) * 100, 1),
                                     "F1": round(float(f1[j]), 4),
                                     "n_pos": int(Ys[:, j].sum())} for j in range(len(names))}
        print(f"  [test/{tag}] 宏 F1 {macros[tag]:.4f}")

    treble = per_class["tuned_on_tune"][names[-1]]["F1"]
    verdict = {
        "macro_ge_v1": macros["tuned_on_tune"] >= FROZEN_UNIFIED,
        "treble_ge_0.5": treble >= 0.5,
    }
    print(f"  DoD：宏 F1 ≥ {FROZEN_UNIFIED} → {verdict['macro_ge_v1']}；"
          f"高音 F1 ≥ 0.5（实测 {treble}）→ {verdict['treble_ge_0.5']}")

    os.makedirs(OUT_DIR, exist_ok=True)
    payload = {
        "gen": "[v2]",
        "protocol": "阈值在 val_v3_tune 上选，指标在 val_v3_test 上报（消除 A1-8 同集偏置）",
        "val_v3_tune": {"n": int(len(res["tune"]["texts"])),
                        "pos_per_class": res["tune"]["Y"].sum(axis=0).tolist()},
        "val_v3_test": {"n": int(len(res["test"]["texts"])),
                        "pos_per_class": Ys.sum(axis=0).tolist()},
        "chosen_thresholds": chosen,
        "test_macro_f1": macros,
        "test_per_class": per_class,
        "v1_reference": {"unified_0.5_macro_f1": FROZEN_UNIFIED,
                         "same_set_probe_macro_f1_not_citable": PROBE_OPTIMISTIC},
        "dod": verdict,
    }
    with open(os.path.join(OUT_DIR, "w2_perclass_thresholds.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    lines = ["# W2 多标签逐类阈值（tune 选阈值 / test 报指标）", "",
             f"> 协议：阈值在 `val_v3_tune`（n={len(res['tune']['texts'])}）上网格搜索，"
             f"指标在 `val_v3_test`（n={len(res['test']['texts'])}）上报告。"
             f"v1 的 0.7834 是在**同一集合**上选阈值得到的（`per_class_thresholds_probe.json` "
             f"自注偏乐观），本表以 test 列为准，两者不可混用。", "",
             "## 选中的阈值（来自 tune）", "",
             "| 类别 | 阈值 | tune 上 F1 |", "|---|---|---|"]
    for name in names:
        lines.append(f"| {name} | {chosen[name]['thr']} | {chosen[name]['tune_f1']} |")
    lines += ["", "## test 上的结果", "",
              "| 口径 | 宏 F1 | " + " | ".join(f"{n} F1" for n in names) + " |",
              "|---" * (len(names) + 2) + "|"]
    for tag in ("unified_0.5", "tuned_on_tune"):
        row = f"| {tag} | **{macros[tag]}** | " + \
              " | ".join(f"{per_class[tag][n]['F1']}" for n in names) + " |"
        lines.append(row)
    lines += ["", "## DoD 判定", "",
              f"- 宏 F1 ≥ {FROZEN_UNIFIED}`[v1]`（统一 0.5 档）："
              f"**{'通过' if verdict['macro_ge_v1'] else '未通过'}**（实测 {macros['tuned_on_tune']}）",
              f"- 高音类 F1 ≥ 0.5：**{'通过' if verdict['treble_ge_0.5'] else '未通过'}**"
              f"（实测 {treble}）",
              "",
              "## 各类明细（tuned_on_tune）", "",
              "| 类别 | P | R | F1 | test 正例数 |", "|---|---|---|---|---|"]
    for n in names:
        d = per_class["tuned_on_tune"][n]
        lines.append(f"| {n} | {d['P']}% | {d['R']}% | {d['F1']} | {d['n_pos']} |")
    lines.append("")
    with open(os.path.join(OUT_DIR, "w2_perclass_thresholds.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"[写出] {OUT_DIR}/w2_perclass_thresholds.md / .json")
    return 0 if all(verdict.values()) else 3


if __name__ == "__main__":
    raise SystemExit(main())
