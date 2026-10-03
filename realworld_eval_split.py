# -*- coding: utf-8 -*-
"""按"训练侧 / 留出侧"分别重算真实场景性能——暴露此前 0.427 的污染成分。"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
COL = "人工判定(1=音质差评/0=不是)"


def wilson(k, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def prf(y, p, thr):
    tp = sum(1 for a, b in zip(y, p) if a == 1 and b >= thr)
    fp = sum(1 for a, b in zip(y, p) if a == 0 and b >= thr)
    fn = sum(1 for a, b in zip(y, p) if a == 1 and b < thr)
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    f1 = (2 * prec * rec / (prec + rec)) if (prec == prec and rec == rec and prec + rec) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec, "f1": f1}


# 人工判定 + row_index
human = {}
for f in ("docs/gold_set/assisted_worksheet.csv", "docs/gold_set/s1_add100.csv",
          "docs/gold_set/s5_clean_probe.csv"):
    for r in csv.DictReader(open(f, encoding="utf-8-sig", errors="replace")):
        v = (r.get(COL) or "").strip()
        if v in ("0", "1"):
            human[r["编号"]] = int(v)
side = json.load(open("v2/human_overlap_split.json", encoding="utf-8"))
train_side, hold_side = set(side["train_side"]), set(side["holdout_side"])

# 概率（realworld_eval 已存）
res = json.load(open("v2/realworld_eval.json", encoding="utf-8"))
# 顺序 = worksheet(300) + s1_add100(100) + s5(100)，过滤掉未判/无文本
rows = []
for r in csv.DictReader(open("docs/gold_set/worksheet.csv", encoding="utf-8-sig", errors="replace")):
    rows.append(r["编号"])
for f in ("docs/gold_set/s1_add100.csv", "docs/gold_set/s5_clean_probe.csv"):
    for r in csv.DictReader(open(f, encoding="utf-8-sig", errors="replace")):
        rows.append(r["编号"])

print(f"{'模型':<26}{'子集':<14}{'n':>4}{'真阳':>5}{'TP':>4}{'FP':>4}{'FN':>4}{'精确':>8}{'召回':>8}{'F1':>8}")
out = {}
for model, d in res["models"].items():
    probs = d["probs"]
    thr = d["thr_tuned"]
    # 对齐：probs 只含"有文本且已判"的条目，按 rows 顺序
    seq = [i for i in rows if i in human]
    assert len(seq) == len(probs), f"对齐失败 {len(seq)} vs {len(probs)}"
    pm = dict(zip(seq, probs))
    out[model] = {}
    for label, subset in (("全部（80%污染）", set(seq)),
                          ("训练侧（污染）", set(seq) & train_side),
                          ("留出侧（干净）", set(seq) & hold_side)):
        ids = [i for i in seq if i in subset]
        y = [human[i] for i in ids]
        pp = [pm[i] for i in ids]
        m = prf(y, pp, thr)
        lo, hi = wilson(m["tp"], sum(y)) if sum(y) else (float("nan"), float("nan"))
        out[model][label] = {**{k: (None if v != v else v) for k, v in m.items()},
                             "n": len(ids), "pos": sum(y),
                             "recall_ci": [None if lo != lo else round(lo, 3),
                                           None if hi != hi else round(hi, 3)]}
        print(f"{model:<26}{label:<14}{len(ids):>4}{sum(y):>5}{m['tp']:>4}{m['fp']:>4}{m['fn']:>4}"
              f"{m['precision']:>8.3f}{m['recall']:>8.3f}{m['f1']:>8.3f}")
json.dump(out, open("v2/realworld_eval_split.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\n[写出] v2/realworld_eval_split.json")
print("结论：**留出侧才是无污染口径**；其正例数很少，故召回不可定，但可与污染侧对照看差距。")
