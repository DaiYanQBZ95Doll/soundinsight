# -*- coding: utf-8 -*-
# 本脚本用于准备漏检抽样：从规则判负的样本中抽取 300 条（200 条音质相关三星、
# 100 条音质无关），输出 neg_review_input.jsonl 供 LLM 复核漏检率。
import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_expanded.csv")
OUT_JSONL = os.path.join(HERE, "neg_review_input.jsonl")


def main() -> None:
    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    g3 = df[(df["sound_related"] == 1) & (df["rating"] == 3)].sample(
        n=200, random_state=42)
    g0 = df[df["sound_related"] == 0].sample(n=100, random_state=42)
    sub = pd.concat([g3, g0])
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for idx, row in sub.iterrows():
            f.write(json.dumps({
                "id": int(idx),
                "rating": int(row["rating"]),
                "text": str(row["text"]),
            }, ensure_ascii=False) + "\n")
    print(f"漏检抽样: {len(sub)} 条 -> {OUT_JSONL}")


if __name__ == "__main__":
    main()
