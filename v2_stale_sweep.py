# -*- coding: utf-8 -*-
"""陈旧表述扫描：找出当前态文档里"已不成立"的措辞（待填／运行中／尚未生成／草案待定稿等）。

用途：换代与收尾后，这类词若仍留在对外文档里，会与事实不符（审计的 D7 检查覆盖"否定性状态
断言"，但不覆盖"待填／运行中"这类过程态措辞）。
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

# 只扫"对外/当前态"文档（历史材料与内部过程文档另行处理）
FILES = ["README.md", "MODEL_CARD.md", "competition_v4.md", "results_summary.md",
         "llm_baseline.md", "length_bucket_eval.md", "calibration_eval.md",
         "error_taxonomy.md", "throughput_eval.md", "stats_validation.md",
         "ablation_summary.md", "significance_test.md", "confidence_tiered.md",
         "edge_case_benchmark.md", "insight_report_v2.md", "insight_report_v2_en.md",
         "QWEN_HANDOFF.md", "PROJECT_BRIEF_QWEN.md",
         "docs/N1_narrative_mainline.md", "docs/N1b_downgrade_narrative.md",
         "docs/N2_narrative_final.md", "docs/N3_calibration_evidence.md",
         "docs/N4_target_argument.md", "docs/N5_qna_factbase.md",
         "docs/v2_gate_verdict.md", "docs/DoD_completion_table.md",
         "docs/M3b_judge_access_guide.md", "docs/M8a_submission_precheck.md"]

PATTERNS = {
    "待填": r"待填",
    "运行中": r"运行中|进行中",
    "尚未生成": r"尚未生成|未生成",
    "待生成": r"待生成",
    "SKIP": r"\bSKIP\b",
    "待定稿": r"待定稿",
    "待实测": r"待实测",
    "待决策": r"待决策",
    "未开始": r"未开始",
    "草案": r"草案",
}
EXEMPT_MARKERS = ("历史", "v1（复赛", "[v1]", "按设计", "待人工", "人侧", "D5", "D10",
                  "把柄", "不可执行", "未来工作", "未开展", "尚未落地")

hits = []
for rel in FILES:
    p = os.path.join(HERE, rel)
    if not os.path.isfile(p):
        continue
    for i, line in enumerate(open(p, encoding="utf-8", errors="replace").read().splitlines(), 1):
        for name, pat in PATTERNS.items():
            if re.search(pat, line):
                if any(m in line for m in EXEMPT_MARKERS):
                    continue
                hits.append((rel, i, name, line.strip()[:110]))

print(f"扫描 {len(FILES)} 份当前态/对外文档，命中 {len(hits)} 处疑似陈旧表述\n")
cur = None
for rel, i, name, snippet in hits:
    if rel != cur:
        print(f"[{rel}]")
        cur = rel
    print(f"    L{i}（{name}）{snippet}")
if not hits:
    print("  （无命中）")
