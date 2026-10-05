# -*- coding: utf-8 -*-
"""复核卡完整计分（容忍未判条目：按已判子集估计，并注明缺口）。"""
from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import random
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
got, _amb = rio.read_judgements(os.path.join(HERE, "docs/gold_set/answer_sheet_recheck.md"))
A = [(u, i) for u, i in zip(meta["ids"], meta["row_index"])
     if u.startswith("A") and u in got]
B = [(u, i) for u, i in zip(meta["ids"], meta["row_index"])
     if u.startswith("B") and u in got]
miss = [u for u in meta["ids"] if u not in got]
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
yB = [1 if got.get(u) == "1" else 0 for u, _i in B]
probs = rwe.predict([texts[i] for _u, i in A], cfg["bin_model_dir"],
                    int(cfg.get("max_len", 256)))
poolA, poolB = meta["fired_pool"], meta["notfired_pool"]
print(f"复核卡：Arm A {len(A)}/50（触发池 {poolA}）｜Arm B {len(B)}/50（未触发池 {poolB}）"
      f"｜未判 {miss or '无'}")
out = {"n_A": len(A), "n_B": len(B), "missing": miss, "pool_fired": poolA,
       "pool_notfired": poolB, "by_tier": {}, "tp_armA": sum(yA), "tp_armB": sum(yB)}
print("\n## 精确率（Arm A）")
for thr in (0.5, 0.9, 0.95):
    idx = [k for k, p in enumerate(probs) if p >= thr]
    if not idx:
        continue
    k = sum(yA[j] for j in idx)
    lo, hi = wilson(k, len(idx))
    out["by_tier"][thr] = {"n": len(idx), "tp": k, "P": round(k / len(idx), 4),
                           "ci": [round(lo, 4), round(hi, 4)]}
    print(f"  ≥{thr:.2f}：n={len(idx)}｜真阳 {k}｜**精确率 {k/len(idx)*100:.1f}%**"
          f"（CI {lo*100:.0f}–{hi*100:.0f}%）")
print("\n## 召回（分层加权；B 段按已判 49 条估计，缺口 1 条）")
tp_hat = sum(yA) / len(A) * poolA
if sum(yB) == 0:
    ub = 3 / len(B)
    fn_ub = ub * poolB
    rec, rec_lo = 1.0, tp_hat / (tp_hat + fn_ub)
    print(f"  未触发臂真阳 0/{len(B)} → 三倍法则漏判率 ≤{ub*100:.1f}%"
          f"（池 {poolB} 中最多约 {fn_ub:.0f} 条真阳被漏）")
    print(f"  ⇒ **召回 {rec*100:.1f}%（下界 {rec_lo*100:.1f}%）**")
    out.update({"recall": rec, "recall_lower": round(rec_lo, 4),
                "miss_rate_ub": round(ub, 4), "max_missed": round(fn_ub)})
else:
    fn_hat = sum(yB) / len(B) * poolB
    rec = tp_hat / (tp_hat + fn_hat)
    rng = random.Random(42)
    boot = []
    for _ in range(1000):
        ka = sum(1 for _ in range(len(A)) if rng.random() < sum(yA) / len(A))
        kb = sum(1 for _ in range(len(B)) if rng.random() < sum(yB) / len(B))
        t, f = ka / len(A) * poolA, kb / len(B) * poolB
        boot.append(t / (t + f) if (t + f) else 0.0)
    boot.sort()
    print(f"  触发池真阳估计 {tp_hat:.0f}｜未触发池漏判估计 {fn_hat:.0f}"
          f"（未触发臂真阳 {sum(yB)}/{len(B)}）")
    print(f"  ⇒ **召回 {rec*100:.1f}%**（bootstrap 95% {boot[25]*100:.1f}–{boot[975]*100:.1f}%）")
    out.update({"recall": round(rec, 4),
                "recall_ci": [round(boot[25], 4), round(boot[975], 4)]})
json.dump(out, open(os.path.join(HERE, "v2", "recheck_scored.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\n[写出] v2/recheck_scored.json")
