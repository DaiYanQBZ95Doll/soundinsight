# -*- coding: utf-8 -*-
"""生成两张缺失的图表：可靠性曲线（W7 校准）与月度差评率趋势（W15）。

数据来源：
- reliability_curve.png ← `v2/w7_calibration.json` 的 test 分箱（校准前/后对照）
- monthly_trend.png     ← `review_meta_v2.csv` 的 timestamp + `labeled_llm.csv` 的 sound_negative_llm
"""
from __future__ import annotations

import csv
import json
import os
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def reliability() -> None:
    d = json.load(open(os.path.join(HERE, "v2", "w7_calibration.json"), encoding="utf-8"))
    bins = [b for b in d["results"]["test"]["bins"] if b["n"] and b["conf"] is not None]
    conf = [b["conf"] for b in bins]
    acc = [b["acc"] for b in bins]
    n = [b["n"] for b in bins]
    fig, ax = plt.subplots(figsize=(5.2, 5.0), dpi=160)
    ax.plot([0, 1], [0, 1], "--", color="#888", lw=1, label="完美校准")
    sc = ax.scatter(conf, acc, s=[max(18, min(320, x)) for x in n], c="#1f77b4",
                    alpha=0.85, edgecolor="white", zorder=3)
    ax.plot(conf, acc, "-", color="#1f77b4", lw=1.4, zorder=2)
    for b in bins:
        if b["n"] >= 20:
            ax.annotate(f"n={b['n']}", (b["conf"], b["acc"]), fontsize=6.5,
                        xytext=(4, -8), textcoords="offset points", color="#333")
    ax.set_xlabel(f"预测概率（温度缩放 T={d['temperature']} 后）")
    ax.set_ylabel("实际正确率")
    ax.set_title("可靠性曲线（val_v3_test，n=10,000；点面积∝箱内条数）")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", fontsize=8)
    txt = (f"整体 ECE {d['results']['test']['ece_before']} → {d['results']['test']['ece_after']}\n"
           f"抗稀释 ECE（p≥0.5）{d['ece_dilution_resistant']['before']} → "
           f"{d['ece_dilution_resistant']['after']}")
    ax.text(0.98, 0.02, txt, ha="right", va="bottom", fontsize=7.5,
            bbox=dict(boxstyle="round,pad=0.35", fc="#f5f5f5", ec="#ccc"))
    fig.tight_layout()
    out = os.path.join(HERE, "reliability_curve.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[写出] reliability_curve.png（{os.path.getsize(out)/1024:.0f} KB，{len(bins)} 个非空箱）")


def monthly() -> None:
    import datetime
    labels = {}
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8",
              errors="replace") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            labels[i] = int(float(row.get("sound_negative_llm") or 0))
    counts: dict[str, list[int]] = {}
    with open(os.path.join(HERE, "review_meta_v2.csv"), encoding="utf-8",
              errors="replace") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            raw = (row.get("timestamp") or "").strip()
            if not raw.isdigit():
                continue
            ms = int(raw)
            # 兼容秒/毫秒两种量级
            sec = ms / 1000.0 if ms > 1e11 else float(ms)
            try:
                dt = datetime.datetime.fromtimestamp(sec)
            except (OverflowError, OSError, ValueError):
                continue
            key = f"{dt.year:04d}-{dt.month:02d}"
            slot = counts.setdefault(key, [0, 0])
            slot[0] += 1
            slot[1] += labels.get(i, 0)
    keys = sorted(k for k in counts if k >= "2015-01")
    x = [k for k in keys]
    total = [counts[k][0] for k in keys]
    pos = [counts[k][1] for k in keys]
    rate = [p / t * 100 if t else 0 for p, t in zip(pos, total)]
    fig, ax = plt.subplots(figsize=(8.4, 3.6), dpi=160)
    ax.bar(x, total, color="#dce6f1", label="评论总数（左轴）")
    ax.set_ylabel("评论总数")
    ax.set_xticks(range(0, len(x), max(1, len(x) // 14)))
    ax.set_xticklabels([x[i] for i in range(0, len(x), max(1, len(x) // 14))],
                       rotation=45, ha="right", fontsize=7)
    ax2 = ax.twinx()
    ax2.plot(x, rate, "-o", color="#c0392b", ms=3, lw=1.4, label="音质差评率（右轴）")
    ax2.set_ylabel("音质差评率（%）", color="#c0392b")
    ax2.tick_params(axis="y", colors="#c0392b")
    glob = sum(pos) / max(sum(total), 1) * 100
    ax2.axhline(glob, ls="--", color="#7f8c8d", lw=1)
    ax2.text(len(x) - 1, glob * 1.06, f"全局 {glob:.2f}%", ha="right", fontsize=7.5,
             color="#7f8c8d")
    ax2.set_title("月度评论量与音质差评率（W15；用于漂移监控与告警阈值标定）", fontsize=10)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)
    fig.tight_layout()
    out = os.path.join(HERE, "monthly_trend.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[写出] monthly_trend.png（{os.path.getsize(out)/1024:.0f} KB，{len(x)} 个月；"
          f"全局差评率 {glob:.2f}%）")


if __name__ == "__main__":
    reliability()
    monthly()
