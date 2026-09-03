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
    lines.append("- 人工抽查：50 条中 39 条判定正确（78%），经人工复核确认通过，"
                 "无需二次清洗")
    lines.append("")

    lines.append("## 基线对比（5折×3种子，调优阈值 F1）")
    for l in read_lines("baseline_cv.log"):
        if "±" in l:
            lines.append(f"- {l}")
    lines.append("")
    lines.append("## 基线对比（LLM 清洗标签）")
    for l in read_lines("baseline_cv_clean.log"):
        if "±" in l:
            lines.append(f"- {l}")
    lines.append("")

    lines.append("## DistilBERT 交叉验证（弱标注标签）")
    cv_log = read_lines("distilbert_cv.log")
    for l in cv_log:
        if "acc=" in l and "f1" in l:
            lines.append(f"- {l}")
    for l in cv_log:
        if "交叉验证汇总" in l or l.startswith("accuracy") or \
                l.startswith("f1@"):
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

    lines.append("## RoBERTa-base 1折快速验证（基座消融）")
    lines.append("- 说明：ModelScope 无 uer/roberta-base-english 镜像，"
                 "采用同规格的 roberta-base 原版替代")
    lines.append("- 配置：约 3300 条训练样本（341 正例），batch 8，epochs 2，"
                 "lr 2e-5，固定验证集 val_v2.csv（20000 条 / 251 正例）")
    for l in read_lines("roberta_quick.log"):
        if "epoch" in l and "f1_best" in l:
            lines.append(f"- {l}")
    for l in read_lines("roberta_quick.log"):
        if "RoBERTa-base 快速验证结果" in l:
            lines.append(f"- {l}")
    lines.append("- 决策: 受限于 D2 时间窗口，RoBERTa-base 仅做 2 epoch 快速探测，"
                 "未充分收敛（epoch 2 较 epoch 1 退化，可能学习率偏高或 "
                 "batch 过小导致波动）。当前结果不具最终选型意义，仅作基座"
                 "对比参考。后续如时间允许，将跑满 3 epoch 并调低学习率"
                 "再做判断。")
    lines.append("")

    text = "\n".join(lines)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"保存 -> {OUT}")
    print(text)


if __name__ == "__main__":
    main()
