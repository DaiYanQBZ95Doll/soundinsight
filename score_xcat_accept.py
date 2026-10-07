# -*- coding: utf-8 -*-
"""音箱试点人工验收计分（与耳机同协议）：
  Arm A（留出集内**全部**触发 42 条，普查）→ 精确率（Wilson CI）
  Arm B（未触发池 566 抽 50）→ 召回（分层加权；零命中用三倍法则）
对照：LLM 标签口径（v2/xcat_speaker_eval.json）。
"""
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
spec = importlib.util.spec_from_file_location("rio", os.path.join(HERE, "rulings_io.py"))
rio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rio)
meta = json.load(open(os.path.join(HERE, "v2", "xcat_accept_ids.json"), encoding="utf-8"))
got, amb = rio.read_judgements(os.path.join(HERE, "docs/gold_set/answer_sheet_xcat_accept.md"))
n_all = len(meta["ids"])
print(f"已判 {len(got)}/{n_all}｜歧义 {len(amb)}")
if len(got) < n_all:
    print(f"  未填：{[u for u in meta['ids'] if u not in got][:6]}")
    sys.exit(1)


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


A = [u for u in meta["ids"] if u.startswith("A")]
B = [u for u in meta["ids"] if u.startswith("B")]
tpA = sum(1 for u in A if got[u] == "1")
und = sum(1 for u in A + B if got.get(u) == "?")
prec = tpA / len(A)
lo, hi = wilson(tpA, len(A))
print(f"\n[精确率] Arm A（{len(A)} 条＝留出集内全部触发，普查）：真阳 {tpA} → "
      f"**{prec*100:.1f}%**（Wilson CI {lo*100:.0f}–{hi*100:.0f}%）｜无法判断 {und}")
tpB = sum(1 for u in B if got[u] == "1")
poolB = meta["pool_notfired"]
if tpB == 0:
    ub = 3 / len(B)
    fn_ub = ub * poolB
    rec, rec_lo = 1.0, tpA / (tpA + fn_ub)
    print(f"[召回] Arm B 真阳 0/{len(B)} → 三倍法则漏判率 ≤{ub*100:.1f}%"
          f"（未触发池 {poolB} 中最多约 {fn_ub:.0f} 条） ⇒ **召回 {rec*100:.1f}%"
          f"（下界 {rec_lo*100:.1f}%）**")
    out_rec = {"recall": rec, "lower": round(rec_lo, 4)}
else:
    fn_hat = tpB / len(B) * poolB
    rec = tpA / (tpA + fn_hat)
    rng = random.Random(42)
    boot = []
    for _ in range(1000):
        kb = sum(1 for _ in range(len(B)) if rng.random() < tpB / len(B))
        f = kb / len(B) * poolB
        boot.append(tpA / (tpA + f) if (tpA + f) else 0.0)
    boot.sort()
    print(f"[召回] Arm B 真阳 {tpB}/{len(B)}（池 {poolB}）→ 漏判估计 {fn_hat:.0f} 条 ⇒ "
          f"**召回 {rec*100:.1f}%**（bootstrap 95% {boot[25]*100:.0f}–{boot[975]*100:.0f}%）")
    out_rec = {"recall": round(rec, 4),
               "ci": [round(boot[25], 4), round(boot[975], 4)]}
ev = json.load(open(os.path.join(HERE, "v2", "xcat_speaker_eval.json"), encoding="utf-8"))
print(f"\n[对照] LLM 标签口径（冻结留出集）：{ev['metrics']['0.5']}")
json.dump({"n": n_all, "armA": {"n": len(A), "tp": tpA, "precision": round(prec, 4),
                                "ci": [round(lo, 4), round(hi, 4)]},
           "armB": {"n": len(B), "tp": tpB, "pool": poolB},
           "recall": out_rec, "llm_caliber": ev["metrics"]["0.5"],
           "note": "人工口径；口径与 LLM 标签不可混用"},
          open(os.path.join(HERE, "v2", "xcat_accept_scored.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[写出] v2/xcat_accept_scored.json")
