# -*- coding: utf-8 -*-
# 本脚本用于实验归档：把各阶段关键产物按 expNN 策略名 目录归档，禁止覆盖历史结果。
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)

ARCHIVES = [
    ("exp01_弱标注交叉验证", [
        ("PARENT", "distilbert_cv.log"),
        ("PARENT", "baseline_cv.log"),
    ]),
    ("exp02_清洗标签交叉验证", [
        ("PARENT", "distilbert_cv_clean.log"),
        ("PARENT", "baseline_cv_clean.log"),
    ]),
    ("exp03_LLM复核与标签清洗", [
        ("HERE", "review_result.jsonl"),
        ("HERE", "three_star_result.jsonl"),
        ("HERE", "neg_review_result.jsonl"),
        ("HERE", "labeled_llm.csv"),
    ]),
    ("exp04_多标签归因", [
        ("PARENT", "multilabel.log"),
        ("HERE", "multi_label_model"),
    ]),
    ("exp05_教师一致性", [
        ("PARENT", "vs_llm.log"),
    ]),
    ("exp06_最终二分类模型", [
        ("PARENT", "train_final.log"),
        ("HERE", "training_output.txt"),
        ("HERE", "confusion_matrix.png"),
        ("HERE", "sound_model"),
    ]),
]


def main() -> None:
    for name, items in ARCHIVES:
        dst = os.path.join(HERE, name)
        os.makedirs(dst, exist_ok=True)
        for scope, src in items:
            base = HERE if scope == "HERE" else PARENT
            full = os.path.join(base, src)
            if not os.path.exists(full):
                print(f"跳过（不存在）: {name}/{src}")
                continue
            target = os.path.join(dst, os.path.basename(src))
            if os.path.isdir(full):
                shutil.copytree(full, target, dirs_exist_ok=True)
            else:
                shutil.copy2(full, target)
        print(f"归档完成: {name}")
    print("全部归档完成，历史产物未覆盖。")


if __name__ == "__main__":
    main()
