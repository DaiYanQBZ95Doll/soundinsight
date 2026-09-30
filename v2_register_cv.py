# -*- coding: utf-8 -*-
"""CV 落盘后的登记：把 `v2/w5_cv.json` 结果写入清单 W5 行与 PROGRESS_SYNC。

用法：python v2_register_cv.py   （CV 未完成时给出提示并退出）
"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CV = os.path.join(HERE, "v2", "w5_cv.json")

if not os.path.isfile(CV):
    print("[等待] v2/w5_cv.json 尚未生成（CV 仍在跑）")
    raise SystemExit(0)

d = json.load(open(CV, encoding="utf-8"))
s = d["summary"]
folds = d["folds"]
print(f"折数 {len(folds)}｜固定阈值 {s['fixed_threshold']}｜无偏 F1 "
      f"{s['f1_fixed_mean']} ± {s['f1_fixed_std']}（波动 {s['f1_fixed_fluctuation_pct']}%）")
print(f"折内选阈值（偏乐观）：{s['f1_best_infold_mean']} ± {s['f1_best_infold_std']}")
print(f"逐折（固定）：{[f['f1_fixed@0.60'] if 'f1_fixed@0.60' in f else list(f.values())[3] for f in folds]}")

verdict = "✅ 通过" if d.get("cv_stability_pass") else "⚠️ 未通过（波动 >5%）"
detail = (f"5 折 CV 完成（max_len={d['max_len']}，与 v1 的 CV 同窗口）："
          f"**无偏口径（固定阈值 {s['fixed_threshold']}、不在折内做任何选择）"
          f"{s['f1_fixed_mean']} ± {s['f1_fixed_std']}（波动 {s['f1_fixed_fluctuation_pct']}%）**；"
          f"对照口径（折内选阈值，与 v1 的 0.6234±0.0240 同协议但偏乐观）"
          f"{s['f1_best_infold_mean']} ± {s['f1_best_infold_std']}。"
          f"验收线≤5% → {verdict}。逐折固定阈值 F1："
          + "、".join(f"{x:.4f}" for x in
                      [f.get('f1_fixed@0.6', f.get('f1_fixed@0.60')) for f in folds])
          + f"。证据 `v2/w5_cv.json`（用时 {d.get('elapsed_min')} 分钟）")

P = os.path.join(HERE, "docs", "frozen_execution_checklist.md")
s2 = open(P, encoding="utf-8").read()
anchor = "| **W5** 🟡 部分完成（闸门(1) ✅／v2 登记 ✅／CV 运行中） |"
i = s2.find(anchor)
if i < 0:
    # 退化：找任意 W5 行
    i = s2.find("| **W5**")
if i >= 0:
    j = s2.find("\n", i)
    row = s2[i:j]
    if "w5_cv.json" not in row:
        row = row.replace("🟡 部分完成（闸门(1) ✅／v2 登记 ✅／CV 运行中）",
                          "✅ 2026-10-01（闸门(1) ✅／v2 登记 ✅／CV ✅）")
        s2 = s2[:i] + row + " " + detail + " | 执行方 | ✅ |" + s2[j:]
        open(P, "w", encoding="utf-8", newline="\n").write(s2)
        print("[改] 清单 W5 行已登记 CV 结果")
    else:
        print("[跳过] W5 行已含 CV 结果")

Q = os.path.join(HERE, "PROGRESS_SYNC.md")
t = open(Q, encoding="utf-8").read()
ADD = f"""
## W 线第 12 轮：W5 收尾——5 折 CV 完成

- {detail}
- **口径说明**：固定阈值口径**无偏但不稳**（跨折 F1 波动来自阈值在别的划分上选定）；
  折内选阈值口径**与 v1 可比但偏乐观**（v1 即 0.6234±0.0240）。两者并列报告，不混用。
- 结论：W5 的三项（重训模型、阈值扫描、CV）全部完成；采纳闸门第 (1) 条此前已通过。
"""
if "W 线第 12 轮" not in t:
    k = t.find("## 待办（触发式，未触发前不执行）")
    t = t[:k] + ADD + "\n" + t[k:]
    open(Q, "w", encoding="utf-8", newline="\n").write(t)
    print("[增] PROGRESS_SYNC 第 12 轮")
