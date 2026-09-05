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

EXCLUDE_DIRS = {".git", "exp01_弱标注交叉验证", "exp02_清洗标签交叉验证",
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
    "ppt_speed_fix.py",
}

README_SUBMISSION = """# SoundInsight 复赛作品提交包

本 zip 包含：

1. 更新世界的锋芒_SoundInsight_Demo.zip —— 可运行 Demo 源码包
2. 更新世界的锋芒_SoundInsight_复赛作品.pdf —— 【请手动放入最终 PDF】
3. 更新世界的锋芒_SoundInsight_演示视频.mp4 —— 【请手动放入演示视频】

请在最终提交前把 PDF 与视频文件放进本 zip 后提交。
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


def make_final_zip() -> None:
    if not os.path.isfile(DEMO_ZIP):
        make_demo_zip()
    with zipfile.ZipFile(FINAL_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(DEMO_ZIP, os.path.basename(DEMO_ZIP))
        z.writestr("README_SUBMISSION.txt", README_SUBMISSION)
    print(f"生成 {FINAL_ZIP}（骨架，待用户放入 PDF 与视频）")


def main() -> None:
    make_demo_zip()
    make_final_zip()


if __name__ == "__main__":
    main()
