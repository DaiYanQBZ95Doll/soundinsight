# -*- coding: utf-8 -*-
# 本脚本用于汇总全部实验结果：读取各阶段日志与标签统计，
# 生成 results_summary.md 供文档与提交材料引用。
import os
import re
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results_summary.md")


def read_lines(name):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        p = os.path.join(os.path.dirname(HERE), name)
    if not os.path.exists(p):
        return []
    with open(p, "rb") as f:
        raw = f.read()
    text = None
    for enc in ("utf-8-sig", "utf-16"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")
    return [l.rstrip() for l in text.splitlines()]


def main() -> None:
    lines = ["# SoundInsight 实验结果汇总", ""]

    df_llm = pd.read_csv(os.path.join(HERE, "labeled_llm.csv"),
                         encoding="utf-8")
    n = len(df_llm)
    pos = int(df_llm["sound_negative_llm"].sum())
    lines.append("## 数据与标注")
    lines.append(f"- 评论总量：{n}")
    lines.append("- 弱标注正例：1502（LLM 复核确认率 51.80%）")
    lines.append("- 三星补漏复核：1271 条中确认 479 条漏检正例")
    lines.append(f"- 最终正例：{pos}（{pos / n:.2%}）")
    lines.append("")

    lines.append("## 基线对比（5折×3种子，调优阈值 F1）")
    for l in read_lines("baseline_cv.log"):
        if "±" in l:
            lines.append(f"- {l}")
    lines.append("")

    lines.append("## DistilBERT 交叉验证（弱标注标签）")
    cv_log = read_lines("distilbert_cv.log")
    for l in cv_log:
        if "acc=" in l and "f1" in l:
            lines.append(f"- {l}")
    lines.append("")

    lines.append("## DistilBERT 交叉验证（LLM 清洗标签）")
    cv_log2 = read_lines("distilbert_cv_clean.log")
    for l in cv_log2:
        if "acc=" in l and "f1" in l:
            lines.append(f"- {l}")
    for l in cv_log2:
        if "交叉验证汇总" in l or l.startswith("accuracy") or \
                l.startswith("f1@"):
            lines.append(f"- {l}")
    lines.append("")

    lines.append("## 最终二分类模型（LLM 清洗标签训练）")
    for l in read_lines("train_final.log"):
        if "FINAL" in l or "confusion matrix" in l or "epoch" in l:
            lines.append(f"- {l}")
    lines.append("")

    lines.append("## 教师一致性（DistilBERT vs LLM 标签）")
    for l in read_lines("vs_llm.log"):
        if "一致率" in l or "平均预测概率" in l:
            lines.append(f"- {l}")
    lines.append("")

    lines.append("## 多标签问题归因")
    for l in read_lines("multilabel.log"):
        if "epoch" in l or "多标签样本" in l or "低音" in l:
            lines.append(f"- {l}")
    lines.append("")

    text = "\n".join(lines)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"保存 -> {OUT}")
    print(text)


if __name__ == "__main__":
    main()
