# -*- coding: utf-8 -*-
# 本脚本用于合并学习曲线最终数据：500 档取四次平均，重绘图并更新统计文档。
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PNG = os.path.join(HERE, "learning_curve.png")
STATS_MD = os.path.join(HERE, "stats_validation.md")

# 最终数据：500 档为 4 次平均，其余为 2 次平均
DATA = {
    100: (0.4067, 0.0108, 2),
    300: (0.5214, 0.0723, 2),
    500: (0.5099, 0.0434, 4),
    800: (0.5256, 0.0110, 2),
    1000: (0.5666, 0.0532, 2),
    1257: (0.6179, 0.0454, 2),
}


def main() -> None:
    xs = sorted(DATA.keys())
    means = [DATA[n][0] for n in xs]
    stds = [DATA[n][1] for n in xs]

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.errorbar(xs, means, yerr=stds, marker="o", capsize=4,
                color="#1b5fd8")
    for x, m in zip(xs, means):
        ax.text(x, m + 0.008, f"{m:.3f}", ha="center", fontsize=9)
    ax.set_xlabel("正例数量")
    ax.set_ylabel("验证集 F1@0.5（val_v2）")
    ax.set_title("学习曲线：正例数量对音质差评识别 F1 的影响")
    ax.set_xlim(0, 1350)
    ax.annotate("所有数据量严格使用独立验证集 val_v2；500 档为 4 次平均",
                xy=(1257, means[-1]), xytext=(800, means[-1] - 0.045),
                fontsize=8, arrowprops=dict(arrowstyle="->", color="gray"))
    fig.tight_layout()
    plt.savefig(OUT_PNG, dpi=150)
    print(f"重绘 -> {OUT_PNG}")

    with open(STATS_MD, encoding="utf-8") as f:
        content = f.read()

    table_rows = "\n".join(
        f"| {n} | {DATA[n][0]:.4f} | {DATA[n][1]:.4f} |"
        for n in xs)
    start = content.find("| 正例数量 |")
    end = content.find("\n\n", content.find("| 1257"))
    new_table = ("| 正例数量 | 平均 F1@0.5 | 标准差 |\n"
                 "|---------|------------|--------|\n" + table_rows)
    content = content[:start] + new_table + content[end:]
    old_conclusion = content[
        content.find("结论："):content.find("\n\n## 二、PR 曲线")]
    new_conclusion = ("结论：F1 随正例数量整体上升，100 到 300 提升最陡，"
                      "之后爬升放缓。500 档四次平均为 0.5099，较 300 档"
                      "略低，属于小样本训练的随机波动；"
                      "800 至 1257 档持续回升，整体趋势明确。")
    content = content.replace(old_conclusion, new_conclusion)
    content = content.replace(
        "所有数据量均严格使用独立验证集 val_v2，训练正例不足时从训练池有放回重采样补齐。每个数据量两次训练取平均：",
        "所有数据量均严格使用独立验证集 val_v2，训练池来自高音补捞前标签集"
        "（训练正例恰 1006 条，与 val_v2 同源零重叠），训练正例不足时从"
        "训练池有放回重采样补齐。500 档为四次训练平均，其余档为两次平均：")
    with open(STATS_MD, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"更新 -> {STATS_MD}")


if __name__ == "__main__":
    main()
