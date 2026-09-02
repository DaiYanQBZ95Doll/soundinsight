# -*- coding: utf-8 -*-
# 本脚本用于生成系统架构图 architecture.png：数据层到应用层的完整链路。
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PNG = os.path.join(HERE, "architecture.png")

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def box(ax, x, y, title, lines, fc, w=2.5, h=1.6):
    ax.add_patch(plt.Rectangle((x - w / 2, y - h / 2), w, h,
                               facecolor=fc, edgecolor="#444444",
                               linewidth=1.2, zorder=2))
    ax.text(x, y + 0.22, title, ha="center", va="center",
            fontsize=12, fontweight="bold", zorder=3)
    for i, ln in enumerate(lines):
        ax.text(x, y - 0.18 - i * 0.3, ln, ha="center", va="center",
                fontsize=8.5, color="#333333", zorder=3)


def main() -> None:
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5.5)
    ax.axis("off")

    box(ax, 1.6, 2.75, "数据层",
        ["Amazon评论数据", "10万条真实评论"], "#dbeafe")
    box(ax, 4.6, 2.75, "标注层 RLCA",
        ["规则初筛（关键词匹配）", "LLM复核（qwen3.7-plus）",
         "正例 1257 条"], "#d1fae5")
    box(ax, 7.8, 2.75, "模型层 DistilBERT",
        ["二分类 + 五类多标签归因", "1:10欠采样 / 阈值扫描",
         "5折CV：F1 0.6234±0.024"], "#fef3c7")
    box(ax, 10.6, 2.75, "应用层",
        ["Agent 一键报告", "Gradio Demo"], "#fce7f3")

    for x1, x2 in [(2.85, 3.35), (5.85, 6.55), (9.05, 9.35)]:
        ax.annotate("", xy=(x2, 2.75), xytext=(x1, 2.75),
                    arrowprops=dict(arrowstyle="->", color="#1b5fd8",
                                    lw=1.6, zorder=4))

    ax.text(6, 0.55, "SoundInsight 系统架构：数据 → 标注 → 模型 → 应用",
            ha="center", fontsize=13, fontweight="bold")
    ax.text(6, 0.1, "验证集：20000 条（251 正例）｜最终模型 F1 0.687 "
            "（阈值 0.97）｜召回率 89.6%",
            ha="center", fontsize=9.5, color="#555555")

    fig.tight_layout()
    plt.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    print(f"保存 -> {OUT_PNG}")


if __name__ == "__main__":
    main()
