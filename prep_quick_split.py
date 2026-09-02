# -*- coding: utf-8 -*-
# 本脚本用于快速验证数据准备：生成固定验证集 val_v2.csv 与 30% 快速训练子集。
import os
import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_llm.csv")
VAL_CSV = os.path.join(HERE, "val_v2.csv")
QUICK_CSV = os.path.join(HERE, "train_quick.csv")
SEED = 42


def main() -> None:
    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    texts = df["text"].astype(str).tolist()
    labels = df["sound_negative_llm"].astype(int).tolist()

    X_tr, X_va, y_tr, y_va = train_test_split(
        texts, labels, test_size=0.2, random_state=SEED, stratify=labels)

    val = pd.DataFrame({"text": X_va, "sound_negative": y_va})
    val.to_csv(VAL_CSV, index=False, encoding="utf-8")
    print(f"val_v2.csv: {len(val)} 行 | 正例 {sum(y_va)}")

    rng = np.random.RandomState(SEED)
    pos = [i for i, y in enumerate(y_tr) if y == 1]
    neg = [i for i, y in enumerate(y_tr) if y == 0]
    neg_keep = rng.choice(neg, size=len(pos) * 10, replace=False)
    idx = np.concatenate([pos, neg_keep])
    rng.shuffle(idx)
    quick_idx = rng.choice(idx, size=int(len(idx) * 0.3), replace=False)
    quick = pd.DataFrame({
        "text": [X_tr[i] for i in quick_idx],
        "sound_negative": [y_tr[i] for i in quick_idx],
    })
    quick.to_csv(QUICK_CSV, index=False, encoding="utf-8")
    print(f"train_quick.csv: {len(quick)} 行 | 正例 {int(quick['sound_negative'].sum())}")


if __name__ == "__main__":
    main()
