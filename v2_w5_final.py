# -*- coding: utf-8 -*-
"""W5 终评：v2 候选模型的阈值扫描（tune 选）与指标报告（test 报）+ 闸门第 (1) 条判定。

口径（冻结清单 §二 W5 + 采纳闸门 §四/§七）：
- v2 候选模型：`v2/model_maxlen256`（在当前标签集的 80% 训练划分上、seed 42、max_len 256 训得）；
- 阈值：**只在 `val_v3_tune` 上扫描**；指标**只在 `val_v3_test` 上报**；
- 闸门第 (1) 条：`val_v3_test` 上 **F1@调优 ≥ 0.72 或 PR-AUC ≥ 0.75**。

输出：`v2/w5_probs_{tune,test}.csv`（概率缓存）、`v2/w5_final.json`、`v2/w5_final.md`。

用法：python v2_w5_final.py [--model v2/model_maxlen256] [--max-len 256]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np
import torch
from sklearn.metrics import (average_precision_score,
                             precision_recall_fscore_support)
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_w1_longtext import load_csv_texts, predict  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v2")
TUNE, TEST = os.path.join(HERE, "val_v3_tune.csv"), os.path.join(HERE, "val_v3_test.csv")
GATE_F1, GATE_PRAUC = 0.72, 0.75
GRID = [round(0.05 * k, 2) for k in range(1, 20)]


def probs(tag, path, tok, model, max_len, device):
    cache = os.path.join(OUT, f"w5_probs_{tag}.csv")
    if os.path.isfile(cache):
        y, p = [], []
        with open(cache, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                y.append(int(r["label"]))
                p.append(float(r["prob"]))
        print(f"[{tag}] 命中缓存 n={len(y)}")
        return np.array(y), np.array(p)
    texts, labels = load_csv_texts(path)
    pr = predict(model, tok, texts, max_len, "truncate", max_len, 64, device)
    with open(cache, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["text", "label", "prob"])
        for i, t in enumerate(texts):
            w.writerow([t, labels[i], f"{pr[i]:.6f}"])
    print(f"[{tag}] 概率已缓存 n={len(texts)}")
    return np.array(labels), pr


def m(y, p, thr):
    pred = (p >= thr).astype(int)
    a, b, c, _ = precision_recall_fscore_support(y, pred, average="binary",
                                                 zero_division=0)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    return {"thr": float(thr), "P": round(float(a) * 100, 1), "R": round(float(b) * 100, 1),
            "F1": round(float(c), 4), "TP": tp, "FP": fp, "FN": fn}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.path.join(HERE, "v2", "model_maxlen256"))
    ap.add_argument("--max-len", type=int, default=256)
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = DistilBertTokenizer.from_pretrained(args.model)
    model = DistilBertForSequenceClassification.from_pretrained(
        args.model).to(device).eval()
    print(f"device={device} | 模型 {os.path.relpath(args.model, HERE)} | max_len={args.max_len}")

    y_t, p_t = probs("tune", TUNE, tok, model, args.max_len, device)
    y_s, p_s = probs("test", TEST, tok, model, args.max_len, device)

    # 阈值扫描（只在 tune 上）
    scan = [m(y_t, p_t, thr) for thr in GRID]
    best = max(scan, key=lambda d: d["F1"])
    print(f"[tune 选中阈值] {best['thr']}（tune F1 {best['F1']}，P {best['P']}%／R {best['R']}%）")

    # test 上报：调优档 + 0.5 档
    test_tuned = m(y_s, p_s, best["thr"])
    test_05 = m(y_s, p_s, 0.5)
    prauc_tuned = float(average_precision_score(y_s, p_s))
    prauc_tune = float(average_precision_score(y_t, p_t))
    print(f"[test @调优({best['thr']})] P {test_tuned['P']}% R {test_tuned['R']}% "
          f"F1 {test_tuned['F1']} (TP{test_tuned['TP']}/FP{test_tuned['FP']}/FN{test_tuned['FN']})")
    print(f"[test @0.5]              P {test_05['P']}% R {test_05['R']}% F1 {test_05['F1']}")
    print(f"[test PR-AUC] {prauc_tuned:.4f}（tune {prauc_tune:.4f}）")

    gate = {"threshold_f1": {"rule": f"F1@调优 ≥ {GATE_F1}",
                             "value": test_tuned["F1"], "pass": test_tuned["F1"] >= GATE_F1},
            "pr_auc": {"rule": f"PR-AUC ≥ {GATE_PRAUC}", "value": round(prauc_tuned, 4),
                       "pass": prauc_tuned >= GATE_PRAUC}}
    gate["pass_any"] = gate["threshold_f1"]["pass"] or gate["pr_auc"]["pass"]
    print(f"[闸门第 (1) 条] F1@调优 {test_tuned['F1']} / PR-AUC {prauc_tuned:.4f} → "
          f"{'通过' if gate['pass_any'] else '未通过'}")

    payload = {"gen": "[v2]", "model": os.path.relpath(args.model, HERE),
               "max_len": args.max_len,
               "protocol": "阈值只在 val_v3_tune 上扫描；指标只在 val_v3_test 上报（消除 A1-8 同集偏置）",
               "val_v3_tune": {"n": int(len(y_t)), "pos": int(y_t.sum())},
               "val_v3_test": {"n": int(len(y_s)), "pos": int(y_s.sum())},
               "chosen_threshold": best["thr"], "tune_scan": scan,
               "tune_best": best, "test_at_tuned": test_tuned, "test_at_0.5": test_05,
               "pr_auc": {"tune": round(prauc_tune, 4), "test": round(prauc_tuned, 4)},
               "gate_item_1": gate,
               "v1_reference": {"F1@tuned": 0.6871, "F1@0.5": 0.6241,
                                "note": "v1 数字在 val_v2 上、且含同集选阈值偏置；两代不可直比"}}
    with open(os.path.join(OUT, "w5_final.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    md = ["# W5 终评：v2 候选模型的阈值扫描与闸门判定", "",
          f"> 模型 `{os.path.relpath(args.model, HERE)}`（max_len={args.max_len}）；"
          f"阈值只在 `val_v3_tune`（n={len(y_t)}，正例 {int(y_t.sum())}）上扫描，"
          f"指标只在 `val_v3_test`（n={len(y_s)}，正例 {int(y_s.sum())}）上报告。", "",
          "## 阈值扫描（tune）", "",
          "| 阈值 | P | R | F1 |", "|---|---|---|---|"]
    for d in scan:
        star = " ←选中" if d["thr"] == best["thr"] else ""
        md.append(f"| {d['thr']}{star} | {d['P']}% | {d['R']}% | {d['F1']} |")
    md += ["", "## test 上报", "",
           "| 口径 | 阈值 | P | R | F1 | TP/FP/FN |", "|---|---|---|---|---|---|",
           f"| 调优档 | {test_tuned['thr']} | {test_tuned['P']}% | {test_tuned['R']}% | "
           f"**{test_tuned['F1']}** | {test_tuned['TP']}/{test_tuned['FP']}/{test_tuned['FN']} |",
           f"| 高召回档 | 0.5 | {test_05['P']}% | {test_05['R']}% | {test_05['F1']} | "
           f"{test_05['TP']}/{test_05['FP']}/{test_05['FN']} |",
           "", f"- **PR-AUC（test）**：{prauc_tuned:.4f}（tune {prauc_tune:.4f}）", "",
           "## 采纳闸门第 (1) 条", "",
           f"- F1@调优 ≥ {GATE_F1}：**{'通过' if gate['threshold_f1']['pass'] else '未通过'}**"
           f"（实测 {test_tuned['F1']}）",
           f"- PR-AUC ≥ {GATE_PRAUC}：**{'通过' if gate['pr_auc']['pass'] else '未通过'}**"
           f"（实测 {prauc_tuned:.4f}）",
           f"- **合计：{'通过' if gate['pass_any'] else '未通过'}**（二者取或）", "",
           f"> v1 参考：F1@调优 0.6871／F1@0.5 0.6241（均在 `val_v2` 上、含同集选阈值偏置）——"
           f"**两代不可直比**。", ""]
    with open(os.path.join(OUT, "w5_final.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))
    print("[写出] v2/w5_final.json / .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
