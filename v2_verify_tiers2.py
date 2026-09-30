# -*- coding: utf-8 -*-
"""验证 W17 三档表在真实报告输出中生效（中文/英文两版）。"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
import report_builder as rb

common = dict(src_name="样例集（验证用）", n_total=100, n_unsupported=2, n_valid=98,
              n_neg=12, avg_rating=3.78,
              issue_counts={"清晰度": 6, "杂音": 4, "低音": 1, "音量": 1, "高音": 0},
              examples=[{"text": "bad bass rattle", "issue": "低音", "prob": 0.991}],
              n_mid=5)

zh = rb.build_report(**common, lang="zh")
en = rb.build_report(**common, lang="en")
checks = {
    "中文三档表标题": "置信度档位与建议动作" in zh,
    "中文高档行": "| 高 |" in zh,
    "中文中档行": "| 中 |" in zh,
    "中文低档行": "| 低 |" in zh,
    "行动建议带档位标签": "置信档：高" in zh,
    "附注顺延为七": "## 七、附注" in zh,
    "英文三档表存在": "Confidence tiers and recommended actions" in en,
    "英文档位标签": "tier: high" in en,
}
for k, v in checks.items():
    print(f"  {'OK ' if v else 'BAD'} {k}")
print("--- 中文报告节标题 ---")
for line in zh.splitlines():
    if line.startswith("## "):
        print("  " + line)
