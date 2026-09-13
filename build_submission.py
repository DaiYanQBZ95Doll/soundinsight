# -*- coding: utf-8 -*-
# 本脚本用于生成提交物打包：
#   1. 更新世界的锋芒_SoundInsight_Demo.zip（源码+配置+样例+模型下载脚本，不含权重）
#   2. 更新世界的锋芒_SoundInsight_复赛作品.zip（骨架：Demo.zip + 提交说明）
import os
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_ZIP = os.path.join(HERE, "更新世界的锋芒_SoundInsight_Demo.zip")
FINAL_ZIP = os.path.join(HERE, "更新世界的锋芒_SoundInsight_复赛作品.zip")

INCLUDE_FILES = [
    "config.json",
    "requirements.txt",
    "README.md",
    "edge_cases.md",
    "MODEL_CARD.md",
    "install.bat",
    "sample_reviews_100.csv",
    "download_models.py",
]

EXCLUDE_DIRS = {".git", ".ms_upload_tmp", "exp01_弱标注交叉验证",
                "exp02_清洗标签交叉验证",
                "exp03_LLM复核与标签清洗", "exp04_多标签归因",
                "exp05_教师一致性", "exp06_最终二分类模型",
                "exp07_ablation_A", "exp08_ablation_B", "exp09_ablation_C",
                "sound_model", "multi_label_model", "distilbert-base-uncased",
                "roberta-base", "deployment"}

# 开发期脚本：不入 Demo 包
DEV_SCRIPTS = {
    "audit_ppt.py", "check_doc_numbers.py", "build_pdf.py",
    "build_pdf_v2.py", "capture_demo_output.py", "archive_exp.py",
    "make_samples.py", "finalize_curve.py", "retier_conf.py",
    "prep_human_review.py", "upload_models.py",
    "val_pred_dump.py", "prep_err_taxonomy.py", "taxonomy_agg.py",
    "llm_eval_metrics.py", "prep_llm_eval.py", "throughput_bench.py",
    "calibration_eval.py", "length_bucket_eval.py", "edge_case_benchmark.py",
    "ppt_speed_fix.py", "deploy_check.py", "batch_check.py",
    "llm_qwen_metrics.py", "extract_template.py",
}

README_SUBMISSION = """# SoundInsight 复赛作品提交包

本 zip 包含：

1. 更新世界的锋芒_SoundInsight_复赛作品.pdf —— 主文档（【请手动放入最终 PDF】）
2. 更新世界的锋芒_SoundInsight_Demo.zip —— 可运行 Demo 源码包
3. 更新世界的锋芒_SoundInsight_演示视频.mp4 —— 【请手动放入演示视频】
4. 更新世界的锋芒_SoundInsight_其他材料.zip —— 验证报告、审计结果、图表与人工复核原始表

请在最终提交前把 PDF 与视频文件放进本 zip 后提交。
"""

OTHER_ZIP = os.path.join(HERE, "更新世界的锋芒_SoundInsight_其他材料.zip")

# 其他材料（验证报告 / 审计 / 图表 / 人工复核原始表 / 复算脚本）
OTHER_FILES = [
    "results_summary.md", "number_audit.md", "MODEL_CARD.md",
    "llm_baseline.md", "llm_eval_metrics.json", "llm_qwen_metrics.json",
    "length_bucket_eval.md", "edge_case_benchmark.md", "calibration_eval.md",
    "error_taxonomy.md", "throughput_eval.md", "stats_validation.md",
    "ablation_summary.md", "significance_test.md", "confidence_tiered.md",
    "qna_preparation.md", "edge_cases.md", "user_scenarios.md",
    "docs/dataset_audit.md", "docs/year_split_output.txt",
    "docs/drift_plan.md", "docs/project_full_record.md",
    "docs/file_inventory.md",
    "human_review_50.csv", "human_review_conf30.csv",
    "human_review_noise16.csv",
    "architecture.png", "learning_curve.png", "pr_curve.png",
    "confusion_matrix.png", "calibration_curve.png", "trend_over_time.png",
    "demo_output.png",
    "check_doc_numbers.py", "audit_ppt.py", "deploy_check.py",
    "batch_check.py", "val_pred_dump.py", "calibration_eval.py",
    "length_bucket_eval.py", "edge_case_benchmark.py", "throughput_bench.py",
    "llm_eval_metrics.py", "llm_qwen_metrics.py", "taxonomy_agg.py",
    "prep_err_taxonomy.py",
]

OTHER_README = """# SoundInsight 其他材料说明

本包为补充材料，供评委核查"数字是否可复现、结论是否可验证"。所有数字的权威源是
results_summary.md（冻结口径）；不同口径（冻结口径 / 1000 条子集口径 / 工程数字）
在报告中均已显式标注，不可混用。

## 一、验证报告
- llm_baseline.md：跨 LLM 对照实验（deepseek-chat、qwen3.7-plus 三设置；含循环性红利声明）
- length_bucket_eval.md：按 tokenizer 长度分桶（>128 token 截断桶 F1 0.565）
- edge_case_benchmark.md：六类边界场景定向探针
- calibration_eval.md：十箱 ECE 与过度自信证据
- error_taxonomy.md：FP/FN 错误分类学 + 标注噪声人工终审（15/16 → 9.1%）
- throughput_eval.md：GPU/CPU 吞吐实测
- stats_validation.md / ablation_summary.md / significance_test.md / confidence_tiered.md：
  统计验证、消融、显著性检验、置信度分层
- docs/dataset_audit.md / docs/year_split_output.txt：数据集字段考古与年份分桶脚本输出原文
- docs/drift_plan.md：数据漂移监控方案

## 二、审计与验收
- number_audit.md：数字一致性审计结果（含官方模板格式对照节）
- check_doc_numbers.py：审计脚本本体（可一键复跑：python check_doc_numbers.py）
- deploy_check.py / batch_check.py：在线 Demo 自动验收脚本（单条推理 + 批量上传）

## 三、人工复核原始表
- human_review_50.csv：标注人工抽查 50 条（通过率 78%）
- human_review_conf30.csv：中置信 8 条人工复核（3/8 通过 → 全部剔除）
- human_review_noise16.csv：标注噪声 16 条人工终审（15/16 确认）

## 四、图表
架构图、学习曲线、PR 曲线、混淆矩阵、可靠性曲线、月度趋势图、Demo 截图。

## 五、复算脚本
生成上述报告所需的推理与统计脚本（val_pred_dump.py、calibration_eval.py、
length_bucket_eval.py、edge_case_benchmark.py、throughput_bench.py、
llm_eval_metrics.py、llm_qwen_metrics.py、taxonomy_agg.py 等）。运行需本地模型权重
（从 ModelScope 公开仓库下载，见 MODEL_CARD.md）。

## 六、如实声明
本包不含任何虚构数据或虚构用户证言；本阶段未开展真实用户验证（已在
competition_v4.md 局限章节披露）。
"""


def collect_files():
    items = {}
    for name in INCLUDE_FILES:
        p = os.path.join(HERE, name)
        if os.path.isfile(p):
            items[name] = p
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS
                   and not d.startswith("~$")]
        for fn in files:
            if fn.endswith(".py") and fn not in DEV_SCRIPTS:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, HERE)
                items[rel] = full
    return sorted(items.items())


def make_demo_zip() -> None:
    items = collect_files()
    with zipfile.ZipFile(DEMO_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, full in items:
            z.write(full, rel)
    print(f"生成 {DEMO_ZIP}（{len(items)} 个文件）")


def make_other_zip() -> None:
    items = [(n, os.path.join(HERE, n)) for n in OTHER_FILES
             if os.path.isfile(os.path.join(HERE, n))]
    missing = [n for n in OTHER_FILES
               if not os.path.isfile(os.path.join(HERE, n))]
    with zipfile.ZipFile(OTHER_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for n, p in items:
            z.write(p, n)
        z.writestr("README_其他材料.txt", OTHER_README)
    note = f"，缺失 {missing}" if missing else ""
    print(f"生成 {OTHER_ZIP}（{len(items)} 个文件 + 说明{note}）")


def make_final_zip() -> None:
    if not os.path.isfile(DEMO_ZIP):
        make_demo_zip()
    if not os.path.isfile(OTHER_ZIP):
        make_other_zip()
    with zipfile.ZipFile(FINAL_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(DEMO_ZIP, os.path.basename(DEMO_ZIP))
        z.write(OTHER_ZIP, os.path.basename(OTHER_ZIP))
        z.writestr("README_SUBMISSION.txt", README_SUBMISSION)
    print(f"生成 {FINAL_ZIP}（骨架，待用户放入 PDF 与视频）")


def main() -> None:
    make_demo_zip()
    make_other_zip()
    make_final_zip()


if __name__ == "__main__":
    main()
