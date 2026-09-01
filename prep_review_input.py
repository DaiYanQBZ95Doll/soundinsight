# -*- coding: utf-8 -*-
# 本脚本用于准备 LLM 复核输入：抽取弱标注为正例（音质相关且评分两星以下）的样本，
# 输出 review_input.jsonl 供宿主侧 LLM 工具批量复核。
import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_expanded.csv")
OUT_JSONL = os.path.join(HERE, "review_input.jsonl")


def main() -> None:
    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    pos = df[(df["sound_related"] == 1) & (df["rating"] <= 2)]
    print(f"弱标注正例: {len(pos)}")
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for idx, row in pos.iterrows():
            f.write(json.dumps({
                "id": int(idx),
                "rating": int(row["rating"]),
                "text": str(row["text"]),
            }, ensure_ascii=False) + "\n")
    print(f"写入 -> {OUT_JSONL}")


if __name__ == "__main__":
    main()
