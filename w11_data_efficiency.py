# -*- coding: utf-8 -*-
"""W11（A-尽力）：数据效率单值——"达到 F1@0.5 = 0.65 需要多少正例"。

数据（`competition_v4.md` 学习曲线表，口径 `[v1]`、固定验证集 val_v2、各档多次平均）：

    N:    100    300    500    800   1000   1257
    F1: 0.4067 0.5214 0.5099 0.5256 0.5666 0.6179

方法：对 log(N) 做线性拟合（学习曲线常用的幂律/对数近似），并给出
     ① 点估计（达到 0.65 所需 N）；② bootstrap 95% 区间；③ 外推距离警示。
诚实边界：0.65 **超出实测范围**（实测最高 0.6179 @1257），故结论为**外推**，不可作为承诺。
"""
from __future__ import annotations

import json
import math
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PTS = [(100, 0.4067), (300, 0.5214), (500, 0.5099), (800, 0.5256),
       (1000, 0.5666), (1257, 0.6179)]
TARGET = 0.65
SEED = 42


def fit(pts):
    """最小二乘拟合 F1 = a + b·ln(N)。返回 (a, b)。"""
    xs = [math.log(n) for n, _ in pts]
    ys = [f for _, f in pts]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0.0
    return my - b * mx, b


def n_for(target, a, b):
    """由拟合式反解所需 N；斜率非正或数值溢出时返回 None。"""
    if b <= 1e-6:
        return None
    try:
        return math.exp((target - a) / b)
    except OverflowError:
        return None


def main() -> int:
    a, b = fit(PTS)
    n_hat = n_for(TARGET, a, b)
    r2_num = sum((f - (a + b * math.log(n))) ** 2 for n, f in PTS)
    r2_den = sum((f - sum(f for _, f in PTS) / len(PTS)) ** 2 for _, f in PTS)
    r2 = 1 - r2_num / r2_den

    # 只用后三档（更贴近"继续加数据"的局部斜率）
    a3, b3 = fit(PTS[-3:])
    n3 = n_for(TARGET, a3, b3)

    # bootstrap：对观测点做有放回重采样，重估 N
    rng = random.Random(SEED)
    boots = []
    for _ in range(4000):
        sample = [PTS[rng.randrange(len(PTS))] for _ in PTS]
        aa, bb = fit(sample)
        nn = n_for(TARGET, aa, bb)
        if nn and 100 < nn < 10 ** 7:
            boots.append(nn)
    boots.sort()
    lo = boots[int(0.025 * len(boots))] if boots else None
    hi = boots[int(0.975 * len(boots))] if boots else None

    print(f"全档拟合：F1 = {a:.4f} + {b:.4f}·ln(N)（R² = {r2:.4f}）")
    print(f"  达到 {TARGET} 所需正例：**{n_hat:,.0f}** 条（外推）")
    print(f"后三档拟合：F1 = {a3:.4f} + {b3:.4f}·ln(N) → {n3:,.0f} 条")
    print(f"bootstrap 95% 区间：{lo:,.0f} – {hi:,.0f}（{len(boots)} 次有效重采样）")
    print(f"实测上限：1,257 条 → 0.6179（**未达 {TARGET}**）；外推超出实测范围 "
          f"{n_hat/1257:.2f}×")

    md = f"""# W11 数据效率单值（A-尽力）

> **问题**：达到 `F1@0.5 = 0.65` 需要多少条标注正例？
> **口径**：`[v1]`（固定验证集 `val_v2`，各档多次平均，数据取自 `competition_v4.md` 学习曲线表）。
> **性质**：**外推结论**——0.65 超出实测范围（实测最高 0.6179 @1,257 条），不可作为承诺。

## 一、实测曲线

| 正例数 N | 100 | 300 | 500 | 800 | 1,000 | 1,257 |
|---|---|---|---|---|---|---|
| F1@0.5 | 0.4067 | 0.5214 | 0.5099 | 0.5256 | 0.5666 | **0.6179** |

曲线整体上升但**有波动**（500 档低于 300 档），说明单点噪声不可忽略；1,257 档为 bootstrap 口径
（基于 1,006 条不重复训练正例有放回采样，验证集零重叠）。

## 二、拟合与外推

| 拟合范围 | 形式 | R² | 达到 0.65 所需 N |
|---|---|---|---|
| 全部 6 档 | F1 = {a:.4f} + {b:.4f}·ln(N) | {r2:.4f} | **≈ {n_hat:,.0f} 条** |
| 后 3 档（局部斜率） | F1 = {a3:.4f} + {b3:.4f}·ln(N) | — | ≈ {n3:,.0f} 条 |

**bootstrap 95% 区间**：**{lo:,.0f} – {hi:,.0f}** 条（4,000 次重采样，区间很宽——因为曲线点少且非单调）。

## 三、结论（可直接对外的单值）

> **在当前基座与配置下，达到 F1@0.5 = 0.65 大约需要 {n_hat:,.0f} 条正例**
> （bootstrap 95% 区间 {lo:,.0f}–{hi:,.0f}）；**该值是外推**：实测到 1,257 条时为 0.6179，**尚未达到 0.65**。

## 四、必须同时说明的三点

1. **外推距离**：{n_hat:,.0f} 条 ≈ 实测上限的 **{n_hat/1257:.2f} 倍**，超出实测范围；
2. **口径**：曲线为 `[v1]`（`val_v2`）口径；v2 换了标签集与划分，**该单值不能直接搬到 v2 叙事**，
   需要重跑 v2 学习曲线（未在冻结范围内开展）；
3. **成本含义（供业务侧参考）**：按本项目实测的 LLM 复核成本约 0.03 美元/1,000 条，
   扩标 {max(0, n_hat-1257):,.0f} 条候选的**复核成本约 {max(0, n_hat-1257)*0.03/1000:.2f} 美元**
   （不含人工抽检时间）。
"""
    out = os.path.join(HERE, "docs", "w11_data_efficiency.md")
    open(out, "w", encoding="utf-8", newline="\n").write(md)
    print(f"\n[写出] docs/w11_data_efficiency.md")
    json.dump({"fit_all": {"a": a, "b": b, "r2": r2, "n_for_0.65": n_hat},
               "fit_last3": {"a": a3, "b": b3, "n_for_0.65": n3},
               "bootstrap_ci": [lo, hi], "target": TARGET, "gen": "[v1]"},
              open(os.path.join(HERE, "w11_data_efficiency.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[写出] w11_data_efficiency.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
