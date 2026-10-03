# -*- coding: utf-8 -*-
"""P0 出厂验收计分：Arm A（触发 50）→ 精确率；Arm B（未触发 50）→ **分层加权召回**。

召回算法（分层抽样）：
  触发池中的真阳估计 = (A 中真阳数 / 50) × 触发池规模
  未触发池中的真阳估计 = (B 中真阳数 / 50) × 未触发池规模
  召回 = 前者 /（前者 ＋ 后者）；区间用 **bootstrap**（分层重采样 1,000 次）。

用法：python score_p0_accept.py
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rio", os.path.join(HERE, "rulings_io.py"))
rio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rio)

meta = json.load(open(os.path.join(HERE, "v2", "p0_accept_ids.json"), encoding="utf-8"))
got, ambig = rio.read_judgements(os.path.join(HERE, "docs/gold_set/answer_sheet_p0_accept.md"))
n_all = len(meta["ids"])
print(f"答题卡：{len(got)}/{n_all} 条已判｜歧义 {len(ambig)}")
if len(got) < n_all:
    miss = [u for u in meta["ids"] if u not in got]
    print(f"  未填 {len(miss)} 条（示例 {miss[:5]}）→ 请填完再计分")
    sys.exit(1)
A = [(u, "1" if got[u] == "1" else "0") for u in meta["ids"] if u.startswith("A")]
B = [(u, "1" if got[u] == "1" else "0") for u in meta["ids"] if u.startswith("B")]
und_A = sum(1 for u in meta["ids"] if u.startswith("A") and got[u] == "?")
und_B = sum(1 for u in meta["ids"] if u.startswith("B") and got[u] == "?")
kA, kB = sum(1 for _u, v in A if v == "1"), sum(1 for _u, v in B if v == "1")
poolA, poolB = meta["fired_pool"], meta["notfired_pool"]


def wilson(k, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


prec = kA / len(A)
prec_ci = wilson(kA, len(A))
tp_hat = kA / len(A) * poolA
fn_hat = kB / len(B) * poolB
rec = tp_hat / (tp_hat + fn_hat) if (tp_hat + fn_hat) else float("nan")

rng = random.Random(42)
boot = []
for _ in range(1000):
    ka = sum(1 for _ in range(len(A)) if rng.random() < kA / len(A))
    kb = sum(1 for _ in range(len(B)) if rng.random() < kB / len(B))
    t = ka / len(A) * poolA
    f = kb / len(B) * poolB
    boot.append(t / (t + f) if (t + f) else 0.0)
boot.sort()
print(f"\n**[精确率] Arm A（触发 {len(A)} 条，无法判断 {und_A}）**：真阳 {kA}/{len(A)} = "
      f"**{prec*100:.1f}%**（Wilson 95% CI {prec_ci[0]*100:.1f}–{prec_ci[1]*100:.1f}%）")
print(f"**[召回] Arm B（未触发 {len(B)} 条，其中真阳 {kB}，无法判断 {und_B}）**："
      f"触发池真阳估计 {tp_hat:.0f}（池 {poolA:,}）｜未触发池漏掉真阳估计 {fn_hat:.0f}"
      f"（池 {poolB:,}）")
print(f"  ⇒ **召回 ≈ {rec*100:.1f}%**（bootstrap 95% CI "
      f"{boot[25]*100:.1f}–{boot[975]*100:.1f}%）")
json.dump({"n": n_all, "armA": {"n": len(A), "tp": kA, "precision": round(prec, 4),
                                "ci": [round(prec_ci[0], 4), round(prec_ci[1], 4)],
                                "unclear": und_A},
           "armB": {"n": len(B), "tp": kB, "unclear": und_B},
           "pool_fired": poolA, "pool_notfired": poolB,
           "estimated_tp_found": round(tp_hat, 1), "estimated_tp_missed": round(fn_hat, 1),
           "recall": round(rec, 4), "recall_ci": [round(boot[25], 4), round(boot[975], 4)]},
          open(os.path.join(HERE, "v2", "p0_accept_scored.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[写出] v2/p0_accept_scored.json")
