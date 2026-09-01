# -*- coding: utf-8 -*-
# 本脚本用于补充复核输入：全部音质相关且三星的样本，送 LLM 判定是否为漏检正例。
import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_expanded.csv")
OUT_JSONL = os.path.join(HERE, "three_star_input.jsonl")


def main() -> None:
    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    sub = df[(df["sound_related"] == 1) & (df["rating"] == 3)]
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for idx, row in sub.iterrows():
            f.write(json.dumps({
                "id": int(idx),
                "rating": int(row["rating"]),
                "text": str(row["text"]),
            }, ensure_ascii=False) + "\n")
    print(f"三星音质相关样本: {len(sub)} -> {OUT_JSONL}")


if __name__ == "__main__":
    main()
