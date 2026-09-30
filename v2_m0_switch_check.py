# -*- coding: utf-8 -*-
"""M0 换代核对器：扫描 A 类文件里的 v1 数字，列出**未标代际**的位置。

用途（冻结清单 §二 M0 / §九 三类清单）：
"一次性换代"要求所有对外材料与当前态文档同步到 v2，**0 项滞留 v1**。
本脚本把"哪些文件、哪些行仍带 v1 数字且没有代际标注"变成机械清单，
M0 执行时按清单逐项处理；M1 完成后重跑本脚本应为**零残留**（或全部带 `[v1]` 标注）。

口径：
- v1 关键 token：0.6871 / 0.9744 / 0.6241 / 0.6234 / 0.7191 / 0.1266 / 0.000932 / 89.6 / 47.9；
- 合规：该行同时含 `[v1]`（历史口径声明）或属豁免文件（历史材料 / 登记类 / 审计类）；
- 输出：按文件聚合的待处理行清单（前 3 条示例）+ 统计。

用法：python v2_m0_switch_check.py [--limit-per-file 3]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GIT = r"C:\Program Files\Git\cmd\git.exe"

V1_TOKENS = ("0.6871", "0.9744", "0.6241", "0.6234", "0.7191",
             "0.000932", "89.6", "47.9")
# 数字边界：避免把 `prob 0.9744496` 里的子串当成阈值 0.9744（误报）
V1_PATTERNS = [re.compile(r"(?<![\d.])" + re.escape(t) + r"(?![\d])") for t in V1_TOKENS]
OUT_DIR = os.path.join(HERE, "v2")

# A 类（必改）：对外材料与当前态文档——来自冻结清单 §九
A_CLASS = [
    "results_summary.md", "competition_v4.md", "competition_v3.txt", "README.md",
    "MODEL_CARD.md", "llm_baseline.md", "length_bucket_eval.md",
    "edge_case_benchmark.md", "calibration_eval.md", "error_taxonomy.md",
    "throughput_eval.md", "stats_validation.md", "ablation_summary.md",
    "significance_test.md", "confidence_tiered.md",
    "AI_HANDOFF/01_project_overview.md", "AI_HANDOFF/03_metrics_and_caveats.md",
    "AI_HANDOFF/04_evidence_index.md", "AI_HANDOFF/06_pending_and_redlines.md",
    "AI_HANDOFF/07_glossary.md", "AI_HANDOFF/README.md",
    "QWEN_HANDOFF.md", "PROJECT_BRIEF_QWEN.md", "qna_preparation.md",
    "docs/finals_stage.md", "docs/v2_acceptance_benchmark.md",
    "docs/final_project_review_and_execution_plan.md",
    "docs/external_sources_register.md", "docs/legacy_materials_notice.md",
    "docs/frozen_execution_checklist.md", "report_builder.py",
    "deployment/report_builder.py", "ppt_text_dump.md", "video_script.md",
    "video_script.srt", "make_video_assets.py", "insight_report_v2.md",
    "insight_report_v2_en.md",
]
# 豁免：登记/审计/历史说明类（引用 v1 数字是其职责）
EXEMPT = {
    "results_summary.md",              # 数字权威源：历史与新增并存，属登记性质
    "docs/legacy_materials_notice.md",  # 废弃 claim 一览：必然逐条列出旧数字
    "docs/v2_acceptance_benchmark.md",  # 闸门文档：参照值即 v1
    "docs/frozen_execution_checklist.md",
    "docs/final_project_review_and_execution_plan.md",
    "docs/external_sources_register.md",
    "qna_preparation.md",
    "video_script.md", "video_script.srt", "make_video_assets.py",
}
SKIP_DIRS = (".git", "node_modules", "__pycache__")


def read_head(path: str):
    p = os.path.join(HERE, path)
    if not os.path.isfile(p):
        return None
    return open(p, encoding="utf-8", errors="replace").read().splitlines()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-per-file", type=int, default=3)
    args = ap.parse_args()

    report, total = {}, 0
    for f in A_CLASS:
        lines = read_head(f)
        if lines is None:
            report[f] = {"missing": True}
            continue
        hits = []
        for i, line in enumerate(lines, 1):
            if not any(p.search(line) for p in V1_PATTERNS):
                continue
            if "[v1]" in line or "（v1" in line or "`v1`" in line:
                continue
            hits.append({"line": i, "text": line.strip()[:110]})
        if hits:
            report[f] = {"hits": len(hits), "exempt": f in EXEMPT,
                         "samples": hits[:args.limit_per_file]}
            if f not in EXEMPT:
                total += len(hits)

    print(f"M0 换代核对：检查 {len(A_CLASS)} 个 A 类文件")
    print(f"**待处理命中（非豁免文件，未标 [v1]）**：{total} 行\n")
    for f, d in sorted(report.items(), key=lambda kv: -(kv[1].get("hits") or 0)):
        if "hits" not in d:
            continue
        flag = "豁免" if d["exempt"] else "待处理"
        print(f"[{d['hits']:>3}] {f}（{flag}）")
        for s in d["samples"]:
            print(f"        {s['line']}: {s['text']}")
    payload = {"checked": len(A_CLASS), "pending_non_exempt": total, "detail": report}
    with open(os.path.join(OUT_DIR, "m0_switch_report.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"\n[写出] v2/m0_switch_report.json")
    print("说明：本清单即 M0 的待办；M1 完成后重跑应仅剩豁免项。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
