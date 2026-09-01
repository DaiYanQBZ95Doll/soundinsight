# -*- coding: utf-8 -*-
# 本脚本用于扩充数据的标注：单词边界匹配生成音质相关与音质负面标签，
# 并按问题类别输出多标签归因列（低音、清晰度、杂音、音量、高音）。
import os
import re
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "electronics_expanded.csv")
OUTPUT_CSV = os.path.join(HERE, "labeled_expanded.csv")

SOUND_KEYWORDS = [
    "sound", "audio", "bass", "treble", "clarity", "muffled", "distortion",
    "static", "hiss", "crisp", "muddy", "volume", "pitch", "frequency",
    "crackling", "popping", "sibilance", "tinny", "boomy", "hollow",
    "scratchy", "buzzing", "rattling",
]

ISSUE_BUCKETS = {
    "issue_bass": ["bass", "boomy"],
    "issue_clarity": ["muffled", "muddy", "clarity", "hollow", "tinny"],
    "issue_noise": ["static", "hiss", "distortion", "crackling", "buzzing",
                    "popping", "sibilance", "rattling", "scratchy"],
    "issue_volume": ["volume"],
    "issue_treble": ["treble", "pitch", "frequency"],
}


def build_re(words):
    return re.compile(r"\b(?:" + "|".join(map(re.escape, words)) + r")\b",
                      re.IGNORECASE)


def main() -> None:
    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    print(f"读取 {len(df)} 行 -> {INPUT_CSV}")

    sound_re = build_re(SOUND_KEYWORDS)
    df["sound_related"] = df["text"].str.contains(sound_re, na=False).astype(int)
    df["sound_negative"] = np.where(
        (df["sound_related"] == 1) & (df["rating"] <= 2), 1, 0
    )

    for col, words in ISSUE_BUCKETS.items():
        rex = build_re(words)
        df[col] = (df["sound_related"] == 1) & \
            df["text"].str.contains(rex, na=False)
        df[col] = df[col].astype(int)

    n = len(df)
    print(f"sound_related: {int(df['sound_related'].sum())} ({int(df['sound_related'].sum()) / n:.2%})")
    print(f"sound_negative: {int(df['sound_negative'].sum())} ({int(df['sound_negative'].sum()) / n:.2%})")
    print("多标签分布（sound_related 内）:")
    rel = df[df["sound_related"] == 1]
    for col in ISSUE_BUCKETS:
        print(f"  {col}: {int(rel[col].sum())}")

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"保存 -> {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
