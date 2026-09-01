# -*- coding: utf-8 -*-
# 本脚本用于生成人工抽查样本：从最终正例中随机抽 50 条，供人类快速审核标注质量。
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_llm.csv")
OUT_CSV = os.path.join(HERE, "human_review_50.csv")


def main() -> None:
    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    pos = df[df["sound_negative_llm"] == 1]
    sample = pos.sample(n=50, random_state=42)
    out = pd.DataFrame({
        "id": sample.index,
        "rating": sample["rating"],
        "text": sample["text"],
        "人工判定_1为音质负面_留空待填": "",
        "备注_留空待填": "",
    })
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"人工抽查样本: {len(out)} 条 -> {OUT_CSV}")


if __name__ == "__main__":
    main()
