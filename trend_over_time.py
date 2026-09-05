# -*- coding: utf-8 -*-
# 本脚本用于 D 批次趋势图：按月聚合评论量与音质差评率，保存 trend_over_time.png。
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
EXPANDED_CSV = os.path.join(HERE, "electronics_expanded.csv")
LABELED_CSV = os.path.join(HERE, "labeled_llm.csv")
OUT_PNG = os.path.join(HERE, "trend_over_time.png")


def main() -> None:
    exp = pd.read_csv(EXPANDED_CSV, encoding="utf-8", keep_default_na=False)
    lab = pd.read_csv(LABELED_CSV, encoding="utf-8", keep_default_na=False)
    assert len(exp) == len(lab), "两个数据文件行数不一致，无法按位置对齐"

    exp["ts"] = pd.to_datetime(exp["timestamp"], unit="ms", utc=True,
                               errors="coerce")
    exp["month"] = exp["ts"].dt.to_period("M")
    exp["neg"] = lab["sound_negative_llm"].astype(int).to_numpy()

    monthly = exp.groupby("month").agg(total=("neg", "size"),
                                       negs=("neg", "sum"))
    monthly["rate"] = monthly["negs"] / monthly["total"]
    # 只看 2021 年及以后（早期样本极少，噪声大）
    monthly = monthly[monthly.index >= pd.Period("2021-01", freq="M")]

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax1 = plt.subplots(figsize=(10, 4.8))
    x = [str(m) for m in monthly.index]
    ax1.bar(x, monthly["total"], color="#dbeafe", label="评论量")
    ax1.set_ylabel("月度评论量")
    ax2 = ax1.twinx()
    ax2.plot(x, monthly["rate"], color="#c0392b", marker="o", markersize=3,
             label="音质差评率")
    ax2.set_ylabel("音质差评率")
    ax2.set_ylim(0, max(monthly["rate"].max() * 1.3, 0.05))
    ax1.set_title("音质差评率月度趋势（2021-2023，十万条真实评论）")
    ax1.tick_params(axis="x", rotation=60, labelsize=7)
    fig.legend(loc="upper left", bbox_to_anchor=(0.12, 0.95))
    fig.tight_layout()
    plt.savefig(OUT_PNG, dpi=150)
    print(f"保存 -> {OUT_PNG}")
    print("2023 年月度差评率:")
    print(monthly[monthly.index >= pd.Period("2023-01", freq="M")]
          [["total", "negs", "rate"]].to_string())


if __name__ == "__main__":
    main()
