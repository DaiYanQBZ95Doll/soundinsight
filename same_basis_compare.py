# -*- coding: utf-8 -*-
"""同基准对照实验（回应红队刺 2/3/4）：把 v1 与 v2 放在**同一个测试集**上比较，并给出 bootstrap 区间。

要回答的三个问题：
  ① v1 的 0.6871 与 v2 的 0.7220 是否可比？→ 把两个模型都放到 val_v3_test（无泄漏）上报；
  ② 0.7220 这个点估计有多稳？→ 对 128 条正例做 bootstrap（2,000 次）给 95% 区间；
  ③ 归因宏 F1 0.6481 → 0.8273 的跳变来自模型还是来自**逐类阈值选择**？
     → 同一模型在「统一 0.5」与「tune 选阈值」两档分别报。

产出：`v2/same_basis_comparison.json` + 控制台表
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np
import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_w1_longtext import predict  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.join(HERE, "v2")
CLASSES = ["bass", "clarity", "noise", "volume", "treble"]


def read_csv(path):
    return list(csv.DictReader(open(path, encoding="utf-8", errors="replace")))


def f1_from(y, pred):
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return (2 * p * r / (p + r) if p + r else 0.0), p, r


def bootstrap_ci(y, prob, thr, n_boot=2000, seed=42):
    rng = np.random.default_rng(seed)
    n = len(y)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        f1, _, _ = f1_from(y[idx], (prob[idx] >= thr).astype(int))
        vals.append(f1)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main() -> int:
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    test = read_csv(os.path.join(HERE, "val_v3_test.csv"))
    texts = [r["text"] for r in test]
    y = np.array([int(r["sound_negative"]) for r in test])
    tune = read_csv(os.path.join(HERE, "val_v3_tune.csv"))
    t_texts = [r["text"] for r in tune]
    y_tune = np.array([int(r["sound_negative"]) for r in tune])
    print(f"test n={len(y)}（正例 {int(y.sum())}）｜tune n={len(y_tune)}（正例 {int(y_tune.sum())}）｜device={dev}")

    out = {"test_n": len(y), "test_pos": int(y.sum()),
           "tune_n": len(y_tune), "tune_pos": int(y_tune.sum()), "models": {}}

    # ---------- 二分类：v1 与 v2 都放到 val_v3_test（以及 tune，用于选各自阈值）----------
    for tag, path, thr_json in (
            ("v1", os.path.join(HERE, "sound_model"), os.path.join(HERE, "sound_model", "threshold.json")),
            ("v2", os.path.join(V2, "model_maxlen256"), os.path.join(V2, "threshold.json"))):
        if not os.path.isdir(path):
            print(f"  [跳过] {tag} 权重不存在：{path}")
            continue
        tok = DistilBertTokenizer.from_pretrained(path)
        model = DistilBertForSequenceClassification.from_pretrained(path).to(dev).eval()
        max_len = 256 if tag == "v2" else 128
        thr_file = json.load(open(thr_json, encoding="utf-8")) if os.path.isfile(thr_json) else {}
        thr_own = float(thr_file.get("tuned", thr_file.get("threshold", 0.5)))
        p_tune = np.array(predict(model, tok, t_texts, max_len, "truncate", max_len, 64, dev))
        p_test = np.array(predict(model, tok, texts, max_len, "truncate", max_len, 64, dev))
        # 在 tune 上选最优阈值（公平：两个模型都用同一套选择规则）
        grid = np.arange(0.05, 0.96, 0.05)
        best_thr = max(grid, key=lambda t: f1_from(y_tune, (p_tune >= t).astype(int))[0])
        row = {"own_threshold": round(thr_own, 4), "tuned_on_val_v3_tune": round(float(best_thr), 2),
               "max_len": max_len}
        for label, thr in (("at_own_thr", thr_own), ("at_0.5", 0.5), ("at_tuned", best_thr)):
            f1, pr, rc = f1_from(y, (p_test >= thr).astype(int))
            lo, hi = bootstrap_ci(y, p_test, thr)
            row[label] = {"thr": round(float(thr), 4), "F1": round(f1, 4),
                          "P": round(pr, 4), "R": round(rc, 4),
                          "F1_ci95": [round(lo, 4), round(hi, 4)]}
            print(f"  [{tag}] thr={thr:.2f}（{label}）→ F1 {f1:.4f}"
                  f"（95% CI {lo:.4f}–{hi:.4f}）｜P {pr:.3f}｜R {rc:.3f}")
        out["models"][tag] = row

    # ---------- 归因：同一模型在「统一 0.5」与「tune 选阈值」两档 ----------
    print("\n=== 归因（多标签）：阈值选择 vs 模型能力 ===")
    ml = os.path.join(HERE, "multi_label_model")
    tok = DistilBertTokenizer.from_pretrained(ml)
    model = DistilBertForSequenceClassification.from_pretrained(ml).to(dev).eval()
    with open(os.path.join(ml, "issue_labels.json"), encoding="utf-8") as fh:
        labels_meta = json.load(fh)
    print(f"  issue_labels: {str(labels_meta)[:120]}")

    def ml_probs(texts_):
        res = []
        with torch.no_grad():
            for i in range(0, len(texts_), 64):
                e = tok(texts_[i:i + 64], truncation=True, max_length=128, padding=True,
                        return_tensors="pt")
                res.append(torch.sigmoid(model(**{k: v.to(dev) for k, v in e.items()}).logits)
                           .cpu().numpy())
        return np.vstack(res)

    pos_t = [r for r in test if int(r["sound_negative"]) == 1]
    Yt = np.array([[1 if str(r.get(f"issue_{c}_llm")) == "1" else 0 for c in CLASSES]
                   for r in pos_t])
    pos_tu = [r for r in tune if int(r["sound_negative"]) == 1]
    Ytu = np.array([[1 if str(r.get(f"issue_{c}_llm")) == "1" else 0 for c in CLASSES]
                    for r in pos_tu])
    P_t = ml_probs([r["text"] for r in pos_t])
    P_tu = ml_probs([r["text"] for r in pos_tu])
    grid = np.arange(0.05, 0.96, 0.05)
    thr_sel = []
    for k in range(len(CLASSES)):
        thr_sel.append(float(max(grid, key=lambda t: f1_from(Ytu[:, k], (P_tu[:, k] >= t).astype(int))[0])))
    res = {"test_pos": len(pos_t), "thresholds_tuned_on_tune": [round(x, 2) for x in thr_sel],
           "at_0.5": {}, "at_tuned": {}}
    for name, thrs in (("at_0.5", [0.5] * 5), ("at_tuned", thr_sel)):
        f1s = []
        for k, c in enumerate(CLASSES):
            f1, pr, rc = f1_from(Yt[:, k], (P_t[:, k] >= thrs[k]).astype(int))
            f1s.append(f1)
            res[name][c] = {"thr": round(thrs[k], 2), "F1": round(f1, 4),
                            "P": round(pr, 4), "R": round(rc, 4),
                            "test_pos": int(Yt[:, k].sum())}
            print(f"  [{name}] {c:<8} thr={thrs[k]:.2f} → F1 {f1:.4f}（测试正例 {int(Yt[:, k].sum())}）")
        res[name]["macro_F1"] = round(float(np.mean(f1s)), 4)
        print(f"  [{name}] **宏 F1 = {res[name]['macro_F1']}**")
    out["attribution"] = res
    out["note"] = ("v1 与 v2 在同一 val_v3_test 上比较；阈值均在 val_v3_tune 上按同一规则选择；"
                   "CI 为对测试集做 2,000 次 bootstrap（含正例重采样）")
    json.dump(out, open(os.path.join(V2, "same_basis_comparison.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n[写出] v2/same_basis_comparison.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
