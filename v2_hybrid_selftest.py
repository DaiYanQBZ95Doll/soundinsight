# -*- coding: utf-8 -*-
"""对 v2_w1_hybrid.py 的核心函数做合成数据自检（不需要 GPU）。"""
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
from v2_w1_hybrid import SHORT_MAX, hybrid_probs, metrics_hybrid  # noqa: E402

# 合成：6 短 + 6 长；长档 3 正例。切窗概率比截断高（模拟真实情形）
tl = [10, 20, 30, 40, 50, 60, 200, 300, 400, 500, 600, 700]
y = [1, 0, 1, 0, 0, 0, 1, 1, 0, 1, 0, 0]
ptr = [0.9, 0.1, 0.8, 0.2, 0.1, 0.05, 0.3, 0.2, 0.1, 0.4, 0.2, 0.1]
pseg = [0.9, 0.1, 0.8, 0.2, 0.1, 0.05, 0.85, 0.75, 0.2, 0.9, 0.3, 0.15]

print("== 用例 1：短档阈值 0.5 / 长档 0.5 ==")
probs, thrs = hybrid_probs(tl, ptr, pseg, 0.5, 0.5)
m1 = metrics_hybrid(y, probs, thrs)
print(f"  {m1}")
assert m1["TP"] == 5 and m1["FP"] == 0, "短+长档全对时 TP 应为 5"

print("== 用例 2：长档阈值过高（0.95）会漏掉长档正例 ==")
probs2, thrs2 = hybrid_probs(tl, ptr, pseg, 0.5, 0.95)
m2 = metrics_hybrid(y, probs2, thrs2)
print(f"  {m2}")
assert m2["TP"] == 2, "长档 3 正例在 0.95 阈值下应只留 0.9 那条 → TP=2"

print("== 用例 3：分档生效性（长档用切窗概率而非截断概率）==")
# 若长档误用截断概率，则 6 条长档正例里只有 0.4 那条能过 0.5 → TP<=3
idx_long = [i for i, L in enumerate(tl) if L > SHORT_MAX]
assert all(abs(probs[i] - pseg[i]) < 1e-9 for i in idx_long), "长档必须取切窗概率"
print("  长档取值来源正确（切窗概率）")
print("自检通过")
