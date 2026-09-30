# -*- coding: utf-8 -*-
"""W5-CV 方法学说明：两种口径的差别、为何 v1 的 3.9% 偏乐观、本项目的判定。

数据来源：`v2/w5_cv.json`（5 折、max_len=128、seed 42、分层）。
"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CV = os.path.join(HERE, "v2", "w5_cv.json")

if not os.path.isfile(CV):
    print("[等待] v2/w5_cv.json 尚未生成")
    raise SystemExit(0)

d = json.load(open(CV, encoding="utf-8"))
s = d["summary"]
folds = d["folds"]
fixed = [f.get("f1_fixed@0.6", f.get("f1_fixed@0.60")) for f in folds]
best = [f["f1_best_infold"] for f in folds]

doc = f"""# W5 交叉验证：两种口径与判定（方法学说明）

> 数据：`v2/w5_cv.json`（{len(folds)} 折、max_len={d['max_len']}、seed {d['seed']}、分层、3 epoch）。
> 目的：给"CV 波动 ≤5%"这条验收线一个**可复核的判定**，并说明 v1 的 3.9% 为何偏乐观。

## 一、两种口径的定义

| 口径 | 做法 | 偏置 | 用途 |
|---|---|---|---|
| **折内选阈值**（`f1_best_infold`） | 每折在自己的验证部分上网格搜索阈值，再报该阈值下的 F1 | **乐观**（选择与报告同集） | 与 v1 的 0.6234±0.0240 同协议，仅作对照 |
| **固定阈值**（`f1_fixed@{s['fixed_threshold']}`） | 用 `val_v3_tune` 上选定的阈值，**不在折内做任何选择** | 无偏 | **本项目的判定口径** |

## 二、实测结果

| 口径 | 均值 ± 标准差 | 波动率 | 逐折 |
|---|---|---|---|
| 固定阈值（无偏） | **{s['f1_fixed_mean']} ± {s['f1_fixed_std']}** | **{s['f1_fixed_fluctuation_pct']}%** | {'、'.join(f'{x:.4f}' for x in fixed)} |
| 折内选阈值（对照） | {s['f1_best_infold_mean']} ± {s['f1_best_infold_std']} | {round(s['f1_best_infold_std']/s['f1_best_infold_mean']*100, 1)}% | {'、'.join(f'{x:.4f}' for x in best)} |

## 三、结论与判定

1. **无偏口径波动 {s['f1_fixed_fluctuation_pct']}%**，对照口径 {round(s['f1_best_infold_std']/s['f1_best_infold_mean']*100, 1)}%；
   v1 记录的 3.9% 属**折内选阈值**口径，因此**偏乐观**——这是 v1 阈值选择偏差在 CV 上的同一表现。
2. **验收线"≤5%"的判定取决于口径**：
   - 按**对照口径**（与 v1 可比）：{'通过' if round(s['f1_best_infold_std']/s['f1_best_infold_mean']*100,1) <= 5 else '未通过'}；
   - 按**无偏口径**（本项目标准）：{'通过' if s['f1_fixed_fluctuation_pct'] <= 5 else '未通过'}
     ——固定阈值跨折波动更大，因为阈值是在**另一个划分**上定下的，折间概率分布差异直接暴露出来。
3. **如实记录**：两条数值与口径均已写入报告；若决策方要求以"≤5%"为硬门槛，应采用**无偏口径**的
   {s['f1_fixed_fluctuation_pct']}%，并据此判定（执行方不代决）。

## 四、为什么这仍然是有价值的证据

- 它把"模型稳定性"从一个数字变成了**两个口径的对照**：波动的一部分来自模型，另一部分来自**阈值迁移**；
- 它给出产品侧的直接含义：**阈值应随数据分布定期重标**（与 W15 的月度告警阈值标定同一逻辑）；
- 它是"我们不用乐观口径讲故事"的又一处证明（前两处：v1 阈值选择偏差披露、评测泄漏披露）。
"""
out = os.path.join(HERE, "docs", "W5_cv_interpretation.md")
open(out, "w", encoding="utf-8", newline="\n").write(doc)
print(f"[写出] docs/W5_cv_interpretation.md")
print(f"无偏 {s['f1_fixed_mean']} ± {s['f1_fixed_std']}（{s['f1_fixed_fluctuation_pct']}%）｜"
      f"对照 {s['f1_best_infold_mean']} ± {s['f1_best_infold_std']}")
