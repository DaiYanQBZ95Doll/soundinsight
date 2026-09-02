# -*- coding: utf-8 -*-
# 本脚本用于数据提纯准备：抽取三星补漏确认的 479 条正例做置信度复核输入，
# 并从十万条评论中按关键词捞取高音候选样本。
import json
import os
import re
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
THREE_STAR_RESULT = os.path.join(HERE, "three_star_result.jsonl")
EXPANDED_CSV = os.path.join(HERE, "electronics_expanded.csv")
CONF_INPUT = os.path.join(HERE, "conf_review_input.jsonl")
TREBLE_INPUT = os.path.join(HERE, "treble_candidates.jsonl")

TREBLE_KEYWORDS = ["shrill", "piercing", "sibilant", "screeching",
                   "ear-splitting", "tinny", "harsh treble"]


def main() -> None:
    confirmed = []
    with open(THREE_STAR_RESULT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec["verdict"] == 1:
                confirmed.append(rec)

    df = pd.read_csv(EXPANDED_CSV, encoding="utf-8")
    with open(CONF_INPUT, "w", encoding="utf-8") as f:
        for rec in confirmed:
            f.write(json.dumps({
                "id": rec["id"],
                "rating": 3,
                "text": str(df.loc[rec["id"], "text"]),
            }, ensure_ascii=False) + "\n")
    print(f"置信度复核输入: {len(confirmed)} 条 -> {CONF_INPUT}")

    rex = re.compile(r"\b(?:" + "|".join(map(re.escape, TREBLE_KEYWORDS)) +
                     r")\b", re.IGNORECASE)
    hits = df[df["text"].str.contains(rex, na=False)]
    with open(TREBLE_INPUT, "w", encoding="utf-8") as f:
        for idx, row in hits.iterrows():
            f.write(json.dumps({
                "id": int(idx),
                "rating": int(row["rating"]),
                "text": str(row["text"]),
            }, ensure_ascii=False) + "\n")
    print(f"高音候选: {len(hits)} 条 -> {TREBLE_INPUT}")


if __name__ == "__main__":
    main()
