# -*- coding: utf-8 -*-
# 本脚本用于音质关键词标注：对评论文本做单词边界正则匹配，生成 sound_related 与 sound_negative 两列标签。
"""Step 1: word-boundary sound keyword labeling on real Electronics reviews."""
import os
import re
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "local_data.csv")
OUTPUT_CSV = os.path.join(HERE, "labeled_data_final.csv")
RANDOM_SEED = 42
SAMPLE_K = 15

KEYWORDS = [
    "sound", "audio", "bass", "treble", "clarity", "muffled", "distortion",
    "static", "hiss", "crisp", "muddy", "volume", "pitch", "frequency",
    "crackling", "popping", "sibilance", "tinny", "boomy", "hollow",
    "scratchy", "buzzing", "rattling",
]


def main() -> None:
    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    print(f"Loaded {len(df)} rows from {INPUT_CSV}")

    pattern = re.compile(r"\b(?:" + "|".join(map(re.escape, KEYWORDS)) + r")\b",
                         re.IGNORECASE)
    df["sound_related"] = df["text"].str.contains(pattern, na=False).astype(int)
    df["sound_negative"] = np.where(
        (df["sound_related"] == 1) & (df["rating"] <= 2), 1, 0
    )

    n_total = len(df)
    n_rel = int(df["sound_related"].sum())
    n_neg = int(df["sound_negative"].sum())

    print("\n=== Step 1 results ===")
    print(f"sound_related: {n_rel} / {n_total} ({n_rel / n_total:.2%})")
    print(f"sound_negative: {n_neg} / {n_total} ({n_neg / n_total:.2%} of all; "
          f"{n_neg / max(n_rel, 1):.2%} of sound_related)")
    print("\nCross-table (rows=sound_related, cols=rating):")
    print(pd.crosstab(df["sound_related"], df["rating"]).to_string())

    print(f"\n=== {SAMPLE_K} random sound_negative = 1 samples ===")
    samples = df[df["sound_negative"] == 1].sample(
        n=min(SAMPLE_K, n_neg), random_state=RANDOM_SEED
    )
    if n_neg == 0:
        print("(none)")
    for i, row in enumerate(samples.itertuples(index=False), 1):
        print(f"\n--- Sample {i} (rating={int(row.rating)}) ---")
        print(row.text[:600])

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"\nSaved {len(df)} rows -> {OUTPUT_CSV}")
    print("Columns:", list(df.columns))


if __name__ == "__main__":
    main()
