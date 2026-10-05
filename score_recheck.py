# -*- coding: utf-8 -*-
"""复核卡计分（支持只判了 Arm A）：独立样本确认判别器的**精确率**。

抽样框：判别器自身触发池 74 条中抽 50（68% 抽样比）；Arm A 是简单随机样本 →
样本精确率即总体精确率的无偏估计（68% 抽样比下区间可再收窄，此处给保守的 Wilson）。
"""
from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))


def load_mod(n, p):
    spec = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rio = load_mod("rio", os.path.join(HERE, "rulings_io.py"))
rwe = load_mod("rwe", os.path.join(HERE, "realworld_eval.py"))
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
meta = json.load(open(os.path.join(HERE, "v2", "recheck_ids.json"), encoding="utf-8"))
got, amb = rio.read_judgements(os.path.join(HERE, "docs/gold_set/answer_sheet_recheck.md"))
A = [(u, i) for u, i in zip(meta["ids"], meta["row_index"]) if u.startswith("A")]
B = [(u, i) for u, i in zip(meta["ids"], meta["row_index"]) if u.startswith("B")]
nA = sum(1 for u, _i in A if u in got)
nB = sum(1 for u, _i in B if u in got)
print(f"已判：Arm A {nA}/{len(A)}｜Arm B {nB}/{len(B)}｜歧义 {len(amb)}")
if nA < len(A):
    print("  Arm A 未判完 → 请判完再计分")
    sys.exit(1)
texts = []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


yA = [1 if got.get(u) == "1" else 0 for u, _i in A]
probs = rwe.predict([texts[i] for _u, i in A], cfg["bin_model_dir"],
                    int(cfg.get("max_len", 256)))
und = sum(1 for u, _i in A if got.get(u) == "?")
pool = meta["fired_pool"]
print(f"\n## 复核卡（独立样本，Arm A 触发档 {len(A)} 条，无法判断 {und}）")
out = {"n": len(A), "unclear": und, "fired_pool": pool,
       "model": cfg["bin_model_dir"], "by_tier": {}}
for thr in (0.5, 0.9, 0.95):
    idx = [k for k, p in enumerate(probs) if p >= thr]
    if not idx:
        continue
    k = sum(yA[j] for j in idx)
    lo, hi = wilson(k, len(idx))
    out["by_tier"][thr] = {"n": len(idx), "tp": k, "P": round(k / len(idx), 4),
                           "ci": [round(lo, 4), round(hi, 4)]}
    print(f"  ≥{thr:.2f}：n={len(idx):>2}｜真阳 {k:>2}｜**精确率 {k/len(idx)*100:.1f}%**"
          f"（Wilson CI {lo*100:.0f}–{hi*100:.0f}%）")
# 与上一张卡对照（同一模型、不同样本）
prev = {}
p_prev = os.path.join(HERE, "v2", "disc_vs_v2_human.json")
if os.path.isfile(p_prev):
    for row in json.load(open(p_prev, encoding="utf-8")):
        if row["model"].startswith("disc"):
            prev[row["thr"]] = row["precision"]
print("\n## 与首张卡的对照（同一模型，独立样本）")
for thr, v in out["by_tier"].items():
    if thr in prev:
        print(f"  ≥{thr:.2f}：首张卡 {prev[thr]*100:.1f}% → 复核卡 {v['P']*100:.1f}%"
              f"（差 {(v['P']-prev[thr])*100:+.1f} 点）")
json.dump(out, open(os.path.join(HERE, "v2", "recheck_scored.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\n[写出] v2/recheck_scored.json")
