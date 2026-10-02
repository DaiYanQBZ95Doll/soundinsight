# -*- coding: utf-8 -*-
"""M6：构建决赛提交包 `更新世界的锋芒_SoundInsight_决赛入围定稿作品.zip`。

内容（按决赛模板 §八 命名规范）：
  1. 更新世界的锋芒_SoundInsight_决赛入围定稿作品.docx —— 主文档（M1 生成，模板九节 + 附录 A–F）
  2. 更新世界的锋芒_SoundInsight_Demo.zip —— 可运行 Demo 源码包（含样例输出；不含权重）
  3. 更新世界的锋芒_SoundInsight_演示视频.mp4 —— 演示视频（沿用 v1 成片；屏幕数字为 v1 口径，见说明）
  4. 更新世界的锋芒_SoundInsight_其他材料.zip —— 验证报告 / v2 证据 / 审计 / 图表 / 人工复核表
  5. README_SUBMISSION.txt —— 提交说明

**红线 9**：本脚本只写决赛包文件名，绝不覆盖/修改复赛包
`更新世界的锋芒_SoundInsight_复赛作品.zip`（脚本内对其做只读哈希核对）。

用法：python build_finals_package.py
"""
from __future__ import annotations

import hashlib
import os
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TEAM, NAME = "更新世界的锋芒", "SoundInsight"
MAIN_DOC = f"{TEAM}_{NAME}_决赛入围定稿作品.docx"
DEMO_ZIP = f"{TEAM}_{NAME}_Demo.zip"
VIDEO = f"{TEAM}_{NAME}_演示视频.mp4"
OTHER_ZIP = f"{TEAM}_{NAME}_其他材料.zip"
FINALS_ZIP = f"{TEAM}_{NAME}_决赛入围定稿作品.zip"
RECAP_ZIP = f"{TEAM}_{NAME}_复赛作品.zip"
FROZEN_RECAP_SHA = "e6cae286515ef1d2"

# Demo 包：入口与配置（**显式白名单**——产品运行所需的最小完整集合）
DEMO_INCLUDE = ["demo_sound_v2.py", "demo_sound.py", "soundinsight_agent.py",
                "report_builder.py", "api_server.py", "predict_core.py",
                "text_utils.py", "config.json",
                "requirements.txt", "README.md", "MODEL_CARD.md", "edge_cases.md",
                "install.bat", "sample_reviews_100.csv", "download_models.py",
                # 样例输出：让评委不必装模型也能看到报告长什么样
                "insight_report_v2.md", "insight_report_v2_en.md",
                "demo_output.png"]
# 开发/评测/打包类脚本：不入 Demo 包
DEV_SCRIPTS = {
    "check_doc_numbers.py", "scan_repo_hygiene.py", "test_audit_checks.py",
    "precommit_guard.py", "make_ai_handoff.py", "hashes.py", "hash_files.py",
    "build_submission.py", "pack_final.py", "pack_when_free.py",
    "build_finals_docx.py", "build_finals_docx2.py", "build_finals_content.py",
    "build_finals_appendix.py", "build_finals_package.py", "gen_v2_artifacts.py",
    "extract_template.py", "md_to_pdf.py", "md_to_docx.py", "verify_docx.py",
    "build_pdf.py", "build_pdf_v2.py", "capture_demo_output.py", "archive_exp.py",
    "deploy_check.py", "batch_check.py", "make_samples.py", "finalize_curve.py",
    "prep_human_review.py", "upload_models.py", "val_pred_dump.py",
    "prep_err_taxonomy.py", "taxonomy_agg.py", "llm_eval_metrics.py",
    "prep_llm_eval.py", "throughput_bench.py", "calibration_eval.py",
    "length_bucket_eval.py", "edge_case_benchmark.py", "ppt_speed_fix.py",
    "llm_qwen_metrics.py", "check_video.py", "check_edge_cases.py", "retime_srt.py",
    "rebuild_video_timing.py", "verify_online_report.py", "check_studio_build.py",
    "diagnose_treble.py", "tune_per_class_threshold.py", "make_video_assets.py",
    "fix_ppt_threshold.py", "train_multilabel.py", "distilbert_cv.py",
    "restore_timestamps.py", "purge_leaked_objects.py", "mask_history_secrets.py",
    "v2_report_probe.py", "v2_report_verify2.py",
}
DEV_PREFIXES = ("v2_w", "v2_fix", "v2_m0", "v2_read", "v2_cred", "v2_hybrid",
                "v2_tick", "v2_del", "v2_verify", "v2_meta", "v2_eval")
EXCLUDE_DIRS = {".git", ".ms_upload_tmp", ".dsh", "node_modules", "__pycache__",
                "_tmp_selftest", "v2", "sound_model", "multi_label_model",
                "distilbert-base-uncased", "roberta-base", "deployment",
                "exp01_弱标注交叉验证", "exp02_清洗标签交叉验证",
                "exp03_LLM复核与标签清洗", "exp04_多标签归因", "exp05_教师一致性",
                "exp06_最终二分类模型", "exp07_ablation_A", "exp08_ablation_B",
                "exp09_ablation_C", "更新世界的锋芒_SoundInsight_复赛作品",
                "更新世界的锋芒_SoundInsight_其他材料"}

# 其他材料：显式清单（存在才收，缺失会列出）
OTHER_FILES = [
    # 验证报告
    "results_summary.md", "llm_baseline.md", "length_bucket_eval.md",
    "edge_case_benchmark.md", "calibration_eval.md", "error_taxonomy.md",
    "throughput_eval.md", "stats_validation.md", "ablation_summary.md",
    "significance_test.md", "confidence_tiered.md", "MODEL_CARD.md",
    "insight_report_v2.md", "insight_report_v2_en.md", "competition_v4.md",
    # v2 证据（决赛新增）
    "v2/w5_final.md", "v2/w5_final.json", "v2/w2_perclass_thresholds.md",
    "v2/w2_perclass_thresholds.json", "v2/w7_calibration.md",
    "v2/w7_calibration.json", "v2/MODEL_CARD_v2.md", "v2/v2_artifacts.json",
    "v2/threshold.json", "v2/w4_summary.json", "v2/w4_strata.json",
    "docs/w1_longtext_variants.md", "docs/w17_failure_cases.md",
    "docs/w17_confidence_actions.md", "docs/e2_erratum.md",
    "docs/v2_gate_verdict.md", "docs/v2_acceptance_benchmark.md",
    "docs/external_sources_register.md", "docs/drift_plan.md",
    "docs/legacy_materials_notice.md", "docs/D13_seal_declaration.md",
    "docs/dataset_audit.md", "docs/year_split_output.txt",
    # 决赛叙事与提交准备（N 线 + 人侧清单）
    "docs/N1_narrative_mainline.md", "docs/N1b_downgrade_narrative.md",
    "docs/N2_narrative_final.md", "docs/N3_calibration_evidence.md",
    "docs/N4_target_argument.md", "docs/N5_qna_factbase.md",
    "docs/M8a_submission_precheck.md", "docs/M3b_judge_access_guide.md",
    "docs/sandbox_operation_notes.md", "docs/llm_credential_status.md",
    "v2/w5_cv.json", "v2/m0_switch_report.json", "docs/W5_cv_interpretation.md",
    "docs/w11_data_efficiency.md", "docs/w13_keyword_miss_rate.md",
    "docs/N6_review_risk_list.md", "w11_data_efficiency.py", "w13_keyword_miss_rate.py",
    "v2_w4_mine.py", "v2_w4_estimate.py", "v2_w4_prescreen.py",
    "docs/w4_prescreen_estimate.md", "v2/w4_prescreen.json",
    "v2_gate_outside_probe.py", "docs/outside_gate_fp.md",
    "docs/scoped_findings.md", "v2/scoped_estimates.json",
    "docs/decision_request_v15_and_nline.md",
    "docs/reassessment_after_credential.md",
    "docs/progress_report_current.md",
    "docs/decision_queue.md",
    "docs/three_stage_comparison.md",
    "docs/REVIEWER_BRIEF.md", "docs/EXECUTION_DISCIPLINE.md",
    "docs/joint_review_agenda.md",
    "docs/opinion_dsh_joint_review.md",
    "docs/taxonomy_three_paths.md", "docs/ppt_claims_erratum.md",
    "check_external_deps.py", "gold_set_helper.py", "cross_model_review.py",
    "push_daily.py",
    "docs/bus/README.md",
    "docs/bus/INDEX.md",
    "docs/bus/TEMPLATE.md",
    "docs/bus/rulings.md", "docs/bus/availability.json",
    "docs/bus/round-01/dsh.md",
    "make_bus_index.py",
    "make_reviewer_brief.py",
    "docs/human_gold_set_protocol.md", "make_gold_set.py", "score_gold_set.py",
    "make_gold_set_notes.py", "gold_set_helper.py",
    "docs/gold_set/JUDGING.md", "apply_human_rulings.py",
    "docs/gold_set/answer_sheet_s1_add100.md", "docs/gold_set/s1_add100.csv",
    "make_s1_add100.py", "inscope_reeval.py", "scope_classify.py",
    "docs/inscope_reeval.md",
    "docs/gold_set/bias_probe_design.md", "docs/gold_set/bias_probe_sheet.md",
    "make_bias_probe.py", "score_bias_probe.py", "compare_passes.py",
    "docs/gold_set/answer_sheet.md", "docs/gold_set/answer_sheet_kimi.md",
    "docs/gold_set/review_notes.md", "docs/gold_set/assisted_worksheet.csv",
    "v2/ai_scope_classification.json", "v2/w4_review_POOL_invalid.jsonl", "w4_model_vs_llm.py",
    "docs/difficulty_stratification.md", "outside_gate_fp.py",
    "difficulty_stratification.py", "check_url_consistency.py",
    "check_refs_and_deps.py",
    # 审计与卫生
    "number_audit.md", "docs/repo_hygiene_scan.md",
    "docs/pre_lock_completeness_audit.md", "docs/completeness_audit_round2.md",
    "docs/evidence_index_exp.md",
    # 人工复核原始表
    "human_review_50.csv", "human_review_conf30.csv", "human_review_noise16.csv",
    # 图表
    "architecture.png", "learning_curve.png", "pr_curve.png",
    "confusion_matrix.png", "reliability_curve.png", "monthly_trend.png",
    "demo_output.png",
    # 复算脚本
    "val_pred_dump.py", "calibration_eval.py", "length_bucket_eval.py",
    "edge_case_benchmark.py", "throughput_bench.py", "llm_eval_metrics.py",
    "llm_qwen_metrics.py", "taxonomy_agg.py", "check_doc_numbers.py",
    "scan_repo_hygiene.py", "v2_w5_final.py", "v2_w2_perclass.py",
    "v2_w7_calibration.py", "v2_m0_switch_check.py", "recover_meta_fields.py",
    "v2_w6_split.py", "v2_meta_analysis.py", "v2_w17_failure_stats.py",
]

README = f"""# SoundInsight 决赛入围定稿提交包

本 zip 共 5 个条目：

1. {MAIN_DOC} —— 主文档（按官方决赛模板填写：九节 + 附录 A–F）
2. {DEMO_ZIP} —— 可运行 Demo 源码包（含样例输出与一键模型下载脚本，**不含权重**）
3. {VIDEO} —— 演示视频（3 分 23 秒，H.264）
4. {OTHER_ZIP} —— 其他材料（验证报告、v2 证据、审计结果、图表、人工复核原始表、复算脚本）
5. README_SUBMISSION.txt —— 本说明

## 两代口径（务必注意）
本包数字存在两代口径，**不可直比**：
- **v1**（复赛已提交口径，样本集 `val_v2`）：F1@调优(0.9744) = 0.6871、F1@0.5 = 0.6241、CV 0.6234±0.0240。
- **v2**（决赛口径，样本集 `val_v3_test`，n=10,000／正例 128，阈值取自 `val_v3_tune`）：
  **F1@调优(0.6) = 0.7220、PR-AUC = 0.7811、归因宏 F1 = 0.8273、高音 F1 = 0.5333**。
- **视频说明**：演示视频沿用 v1 成片，画面中的模型指标为 v1 口径；主文档与验证报告均已换代为 v2 口径。
  视频中"口径"与文档不一致之处，**以主文档与 v2 证据为准**。

## 模型调用与边界（唯一权威表述）
1. 本项目产品推理 100% 本地、零第三方 API。
2. 数据标注与复核环节调用 DeepSeek 官方 API（模型标识 deepseek-chat）。
3. 另有 qwen3.7-plus（阿里云百炼 Token Plan API）仅供评审用途的跨 LLM 稳健性对照实验，不参与产品推理。

## 如实声明
- 未修复短板均在主文档附录 B（已知局限）中披露，包括：长文本桶召回 68.3%（未达 70% 验收线）、
  高音类 F1 0.5333、标注噪声 9.1%、**未开展真实用户验证**（客观原因见附录）。
- v1 的阈值选择偏差与"评测划分不可复现"问题已在附录 C（已知表述勘误与口径演进）中首次披露。
- 权重未入包：v1 权重由 download_models.py 从公开模型仓库下载；v2 权重按 SHA256 与训练命令登记
  （v2/v2_artifacts.json），可由第三方复算。

在线 Demo：https://modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight
代码仓库：https://gitcode.com/DaiYanQBZ95Doll/soundinsight
"""


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_demo() -> dict[str, str]:
    """Demo 包内容＝**显式白名单**（不再遍历仓库）。

    2026-10-01 事故：原先"遍历仓库所有 .py 再排除黑名单"的做法把解包临时目录
    `_tmp_pkgcheck/`（51 个条目）与多个开发脚本扫进了 Demo 包。白名单从根上消除该类泄漏：
    包内容 = 产品运行必需文件 + 部署目录源码 + 样例输出。
    """
    items: dict[str, str] = {}
    for n in DEMO_INCLUDE:
        p = os.path.join(HERE, n)
        if os.path.isfile(p):
            items[n] = p
        else:
            print(f"  [注意] Demo 白名单文件缺失：{n}")
    dep = os.path.join(HERE, "deployment")
    if os.path.isdir(dep):
        for fn in sorted(os.listdir(dep)):
            p = os.path.join(dep, fn)
            if os.path.isfile(p) and fn not in DEV_SCRIPTS:
                items[f"deployment/{fn}"] = p
    return dict(sorted(items.items()))


def build_zips() -> tuple[list[str], list[str]]:
    missing: list[str] = []

    # --- Demo zip ---
    demo = collect_demo()
    demo_path = os.path.join(HERE, DEMO_ZIP)
    with zipfile.ZipFile(demo_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, full in demo.items():
            z.write(full, rel)
    print(f"[Demo] {len(demo)} 个条目 → {DEMO_ZIP}"
          f"（{os.path.getsize(demo_path)/1024/1024:.1f} MB）")

    # --- 其他材料 zip ---
    added = 0
    other_path = os.path.join(HERE, OTHER_ZIP)
    with zipfile.ZipFile(other_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in OTHER_FILES:
            p = os.path.join(HERE, rel)
            if os.path.isfile(p):
                z.write(p, rel)
                added += 1
            else:
                missing.append(rel)
        # 附上过程说明类文档（与上面清单去重，避免 zip 内重复条目）
        for rel in ("PROGRESS_SYNC.md",):
            p = os.path.join(HERE, rel)
            if os.path.isfile(p) and rel not in OTHER_FILES:
                z.write(p, rel)
                added += 1
    print(f"[其他材料] {added} 个条目 → {OTHER_ZIP}"
          f"（{os.path.getsize(other_path)/1024/1024:.1f} MB）")
    return list(demo), missing


def main() -> int:
    # 红线 9 前置核对：复赛包必须仍在且哈希未变
    recap = os.path.join(HERE, RECAP_ZIP)
    if not os.path.isfile(recap):
        print(f"[FAIL] 复赛包不存在：{RECAP_ZIP}（不得继续）")
        return 1
    rs = sha256(recap)
    print(f"[红线 9] 复赛包 {RECAP_ZIP}：sha256 {rs[:16]}"
          f"（冻结值 {FROZEN_RECAP_SHA}）→ {'一致' if rs.startswith(FROZEN_RECAP_SHA) else '不一致！'}")

    demo, missing = build_zips()
    if missing:
        print(f"[其他材料] 缺失 {len(missing)} 项：{'、'.join(missing[:8])}"
              f"{' …' if len(missing) > 8 else ''}")

    # 主文档与视频（视频优先用 faststart 版本：moov 前置，网页/流式播放不卡顿；
    # 由 make_faststart.py 纯 Python 重排，verify_faststart.py 逐块验证数据零改动）
    doc = os.path.join(HERE, MAIN_DOC)
    video_fs = os.path.join(HERE, VIDEO.replace(".mp4", "_faststart.mp4"))
    video = video_fs if os.path.isfile(video_fs) else os.path.join(HERE, VIDEO)
    print(f"[视频] 入包版本：{os.path.basename(video)}"
          f"{'（faststart，moov 前置）' if video is video_fs else '（原版，moov 在尾）'}")
    for p, label in ((doc, "主文档"), (video, "视频")):
        if not os.path.isfile(p):
            print(f"[FAIL] 缺少{label}：{os.path.basename(p)}")
            return 1

    finals = os.path.join(HERE, FINALS_ZIP)
    with zipfile.ZipFile(finals, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(doc, MAIN_DOC)
        z.write(os.path.join(HERE, DEMO_ZIP), DEMO_ZIP)
        z.write(video, VIDEO)
        z.write(os.path.join(HERE, OTHER_ZIP), OTHER_ZIP)
        z.writestr("README_SUBMISSION.txt", README)
    print(f"[决赛包] {FINALS_ZIP}（{os.path.getsize(finals)/1024/1024:.1f} MB）")
    with zipfile.ZipFile(finals) as z:
        print("  条目清单：")
        for i in z.infolist():
            print(f"    {i.filename:<62} {i.file_size/1024/1024:>8.2f} MB")
    print(f"  决赛包 SHA256: {sha256(finals)[:16]}")

    # 复核复赛包未被改动
    rs2 = sha256(recap)
    print(f"[红线 9 复核] 复赛包 sha256 {rs2[:16]} → "
          f"{'未改动 ✓' if rs2 == rs else '被改动 ✗'}")
    return 0 if rs2 == rs else 1


if __name__ == "__main__":
    raise SystemExit(main())
