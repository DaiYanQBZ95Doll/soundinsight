# -*- coding: utf-8 -*-
"""E5 + M0：填入 v2 代际 token（使跨代检查生效），并把 A 类文件里的 v1 数字标注为 [v1]。

E5：`GEN_TOKENS["v2"]` 目前为空 → 代际混用检查只覆盖 v1。v2 指标已产生，填入：
    0.7220（F1@调优）、0.7206（F1@0.5）、0.7811（PR-AUC）、0.8273（归因宏 F1）、0.5333（高音 F1）。
M0：对 A 类文件中"带 v1 数字但未标代际"的行，在该数字后插入 `[v1]`；
    并在若干关键文件顶部插入「v2 现状块」（当前代际为主，v1 为历史对照）。
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

V1_TOKENS = ["0.6871", "0.9744", "0.6241", "0.6234", "0.7191", "0.000932", "89.6", "47.9"]

A_CLASS = [
    "results_summary.md", "competition_v4.md", "competition_v3.txt", "README.md",
    "MODEL_CARD.md", "llm_baseline.md", "length_bucket_eval.md",
    "edge_case_benchmark.md", "calibration_eval.md", "error_taxonomy.md",
    "throughput_eval.md", "stats_validation.md", "ablation_summary.md",
    "significance_test.md", "confidence_tiered.md",
    "AI_HANDOFF/01_project_overview.md", "AI_HANDOFF/03_metrics_and_caveats.md",
    "AI_HANDOFF/04_evidence_index.md", "AI_HANDOFF/06_pending_and_redlines.md",
    "AI_HANDOFF/07_glossary.md", "AI_HANDOFF/README.md",
    "QWEN_HANDOFF.md", "PROJECT_BRIEF_QWEN.md",
    "docs/finals_stage.md", "report_builder.py", "deployment/report_builder.py",
    "ppt_text_dump.md", "video_script.md", "video_script.srt", "make_video_assets.py",
    "insight_report_v2.md", "insight_report_v2_en.md",
]
EXEMPT = {"results_summary.md", "docs/legacy_materials_notice.md",
          "docs/v2_acceptance_benchmark.md", "docs/frozen_execution_checklist.md",
          "docs/final_project_review_and_execution_plan.md",
          "docs/external_sources_register.md"}


def tag_line(line: str) -> tuple[str, int]:
    """在未标注的 v1 数字后插入 [v1]（跳过已有标签的行）。"""
    if "[v1]" in line or "`v1`" in line:
        return line, 0
    n = 0
    out = line
    for tok in V1_TOKENS:
        # 只处理"数字本体"（后接非数字字符），避免插入到更长数字中间
        pattern = re.compile(r"(?<![\d.])" + re.escape(tok) + r"(?![\d])")
        def repl(m):
            nonlocal n
            n += 1
            return m.group(0) + "[v1]"
        out = pattern.sub(repl, out)
    return out, n


def main() -> int:
    # ---------- E5：填 v2 tokens ----------
    cp = os.path.join(HERE, "check_doc_numbers.py")
    s = open(cp, encoding="utf-8").read()
    old = '    "v2": [],  # 待填：v2 的 F1 / 阈值 / CV 等'
    new = ('    "v2": ["0.7220", "0.7206", "0.7811", "0.8273", "0.5333"],'
           '  # E5 填入：F1@调优/F1@0.5/PR-AUC/归因宏F1/高音F1')
    if "E5 填入" not in s and s.count(old) == 1:
        open(cp, "w", encoding="utf-8").write(s.replace(old, new))
        print("  [E5] GEN_TOKENS['v2'] 已填入 5 个 token")
    else:
        print("  [E5] 已填或锚点未命中")

    # ---------- M0：标注 v1 ----------
    total = 0
    for f in A_CLASS:
        if f in EXEMPT:
            continue
        p = os.path.join(HERE, f)
        if not os.path.isfile(p):
            continue
        lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
        hits = 0
        for i, ln in enumerate(lines):
            if not any(t in ln for t in V1_TOKENS):
                continue
            new_ln, n = tag_line(ln)
            if n:
                lines[i] = new_ln
                hits += n
        if hits:
            open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
            print(f"  [M0] {f}: 标注 {hits} 处")
            total += hits
    print(f"M0 合计标注 {total} 处")

    # ---------- v2 现状块（关键文件顶部） ----------
    block = (
        "\n> **代际说明（2026-10-01）**：本文档主体为 **v1（复赛已提交口径）**，其中 v1 数字均已标注 `[v1]`；\n"
        "> **当前代际为 v2**：`val_v3_test`（n=10,000／正例 128，阈值取自 `val_v3_tune`）上\n"
        "> **F1@调优(0.6) = 0.7220`[v2]`、F1@0.5 = 0.7206`[v2]`、PR-AUC = 0.7811`[v2]`、"
        "归因宏 F1 = 0.8273`[v2]`、高音 F1 = 0.5333`[v2]`**；\n"
        "> 两代**样本集不同、不可直比**；v2 完整证据见 `v2/w5_final.md`、`v2/w2_perclass_thresholds.md`、"
        "`v2/w7_calibration.md`、`docs/v2_gate_verdict.md`。\n")
    for f in ("results_summary.md", "MODEL_CARD.md", "AI_HANDOFF/03_metrics_and_caveats.md",
              "competition_v4.md", "README.md"):
        p = os.path.join(HERE, f)
        if not os.path.isfile(p):
            continue
        s2 = open(p, encoding="utf-8", errors="replace").read()
        if "代际说明（2026-10-01）" in s2:
            continue
        lines = s2.splitlines()
        # 插到第一个标题行之后
        for i, ln in enumerate(lines):
            if ln.startswith("#"):
                lines.insert(i + 1, block)
                break
        open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
        print(f"  [v2 现状块] {f}")
    print("完成")


if __name__ == '__main__':
    raise SystemExit(main())
