# -*- coding: utf-8 -*-
# E3 吞吐实测：GPU 与 CPU 各对 100 / 1000 条评论跑 3 轮，
# 记录每轮耗时，输出 throughput_eval.md。
# 数据取自 val_v2 前 N 条文本（推断路径与产品一致：predict_core）。
import os
import sys
import time

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
from predict_core import load, predict_batch  # noqa: E402

VAL = os.path.join(HERE, "val_v2.csv")
OUT_MD = os.path.join(HERE, "throughput_eval.md")


def bench(device, texts, rounds=3):
    load(device)  # 预热（首轮加载不计时）
    times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        predict_batch(texts, device)
        times.append(time.perf_counter() - t0)
    return times


def main() -> None:
    df = pd.read_csv(VAL, encoding="utf-8", keep_default_na=False)
    lines = ["# 推理吞吐实测报告（throughput_eval.md）", "",
             "口径：RTX 4060 Laptop 8GB / 本地 CPU，predict_core 路径"
             "（含二分类 + 命中的多标签归因），batch_size=64，"
             "每档 3 轮取中位数与均值。数据为 val_v2 前 N 条文本。", "",
             "| 设备 | N | 第1轮(s) | 第2轮(s) | 第3轮(s) | 中位数(s) | "
             "吞吐(条/s) |", "|---|---|---|---|---|---|---|"]
    for device in ("cuda", "cpu"):
        for n in (100, 1000):
            texts = df["text"].astype(str).head(n).tolist()
            t = bench(device, texts)
            med = sorted(t)[len(t) // 2]
            lines.append(f"| {device} | {n} | {t[0]:.3f} | {t[1]:.3f} | "
                         f"{t[2]:.3f} | {med:.3f} | {n/med:.1f} |")
            print(f"{device} n={n} times={[round(x,3) for x in t]} "
                  f"med={med:.3f}")
    lines += ["", "如实说明：CPU 档的吞吐受本机后台负载影响，"
              "数值为该机器的快照而非标称性能；GPU 档为独占时段实测。"
              "与 v3/v4 中\"1000 条 2 分钟\"等表述的差异以此实测为准。", ""]
    text = "\n".join(lines)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"saved -> {OUT_MD}")


if __name__ == "__main__":
    main()
