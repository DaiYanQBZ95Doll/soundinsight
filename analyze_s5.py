# -*- coding: utf-8 -*-
"""S5 干净探针分析：① 组间材料效应（无记忆污染）；② 闸门外比率合并 S1+S4+S5（n≈294）与覆盖重算。"""
from __future__ import annotations

import csv
import math
import os
import re
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


def fisher(a, b, c, d):
    """双侧 Fisher 精确检验（表 [[a,b],[c,d]]）。"""
    n = a + b + c + d
    def prob(a_, b_, c_, d_):
        return (math.comb(a_ + b_, a_) * math.comb(c_ + d_, c_)) / math.comb(n, a_ + c_)
    p0 = prob(a, b, c, d)
    tot = 0.0
    for a_ in range(0, min(a + b, a + c) + 1):
        b_ = a + b - a_
        c_ = a + c - a_
        d_ = n - a_ - b_ - c_
        if b_ < 0 or c_ < 0 or d_ < 0:
            continue
        p = prob(a_, b_, c_, d_)
        if p <= p0 + 1e-12:
            tot += p
    return min(1.0, tot)


# ---------- ① S5 两臂 ----------
rows = list(csv.DictReader(open("docs/gold_set/s5_clean_probe.csv",
                                encoding="utf-8-sig", errors="replace")))
arm = {"control": [], "treatment": []}
for r in rows:
    v = (r.get(COL) or "").strip()
    if r["臂"] in arm and v in ("0", "1", "?"):
        arm[r["臂"]].append(v)
print("=== ① S5 干净探针（未见过条目 + 随机两臂）===")
for k, v in arm.items():
    pos = sum(1 for x in v if x == "1")
    comp = sum(1 for x in v if x in ("0", "1"))
    unk = sum(1 for x in v if x == "?")
    print(f"  {k:<10} n={len(v)}｜可比 {comp}｜正例 {pos}｜无法判断 {unk}"
          f"｜正例率 {pos/max(1,comp)*100:.2f}%")
a = sum(1 for x in arm["control"] if x == "1")
b = sum(1 for x in arm["control"] if x == "0")
c = sum(1 for x in arm["treatment"] if x == "1")
d = sum(1 for x in arm["treatment"] if x == "0")
print(f"  组间比较（对照 vs 实验，正/负）：{a}/{b} vs {c}/{d}｜"
      f"Fisher 精确检验 双侧 p = {fisher(a, b, c, d):.3f}")
print("  结论：" + ("**未发现材料导致正例率变化**（两臂均 0 正例）——"
                   "即「带材料会不会让我多判正例」在无记忆污染设计下**没有证据支持**"
                   if a == c else "两臂有差异，需注意"))

# ---------- ② 闸门外比率（S1 + S4 + S5）----------
main = {r["编号"]: (r.get(COL) or "").strip()
        for r in csv.DictReader(open("docs/gold_set/assisted_worksheet.csv",
                                     encoding="utf-8-sig", errors="replace"))}
s4 = {r["编号"]: (r.get(COL) or "").strip()
      for r in csv.DictReader(open("docs/gold_set/s1_add100.csv",
                                   encoding="utf-8-sig", errors="replace"))}
s1v = [main[i] for i in main if i.startswith("S1-") and main[i] in ("0", "1")]
s4v = [v for v in s4.values() if v in ("0", "1")]
s5v = [x for k in arm for x in arm[k] if x in ("0", "1")]
k1, k4, k5 = (sum(1 for v in s1v if v == "1"), sum(1 for v in s4v if v == "1"),
              sum(1 for v in s5v if v == "1"))
n1, n4, n5 = len(s1v), len(s4v), len(s5v)
print("\n=== ② 闸门外真阳性率（人工，合并三轮）===")
for tag, k, n in (("S1（首轮）", k1, n1), ("S4（追加）", k4, n4),
                  ("S5（干净探针两臂）", k5, n5)):
    lo, hi = wilson(k, n)
    print(f"  {tag:<16} {k}/{n} = {k/n*100:.2f}%（CI {lo*100:.2f}–{hi*100:.2f}%）")
K, N = k1 + k4 + k5, n1 + n4 + n5
lo, hi = wilson(K, N)
print(f"  **合并 {K}/{N} = {K/N*100:.2f}%（95% CI {lo*100:.2f}%–{hi*100:.2f}%）**｜LLM 口径 1.33%")

# ---------- ③ 覆盖重算 ----------
OUTR, labeled = 87071, 1280
print("\n=== ③ 覆盖重算（成对口径）===")
LF = labeled / 1.0
for rate, tag in ((0.0133, "原 LLM 口径 1.33%"), (K / N, "人工合并点估计"),
                  (lo, "人工 CI 下界"), (hi, "人工 CI 上界"),
                  (3 / 195, "上一轮 n=195 点估计")):
    op = OUTR * rate
    strict = labeled + 19.9 + op
    incl = labeled + 94.7 + op * 1.25
    print(f"  [{tag:<20}] 闸门外正例 {op:>7,.0f}｜严格覆盖 {labeled/strict*100:>5.1f}%"
          f"｜宽松覆盖 {labeled/incl*100:>5.1f}%")
