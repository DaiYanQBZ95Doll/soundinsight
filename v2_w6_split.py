# -*- coding: utf-8 -*-
"""W6：生成 val_v3_tune / val_v3_test 划分（阈值只在 tune 上选、只在 test 上报）。

为什么需要（冻结清单 §二 W6、`docs/v2_acceptance_benchmark.md` §四）：
v1 的阈值是在**同一集合**上网格搜索并报数（`distilbert_cv.py:90`），构成从未披露的
乐观偏置（缺憾 A1-8）。v2 起必须把"选阈值"与"报指标"分开。

本脚本口径：
- 输入 `val_v2.csv`（冻结 20k，正例 251，来自 labeled_llm.csv 的 20% 分层留出）；
- 用 **seed 42、test_size=0.5、stratify** 分层对半切 → tune 10,000 / test 10,000；
- 输出 `val_v3_tune.csv` / `val_v3_test.csv`（列与 val_v2 一致：text, sound_negative）；
- 写出 `v2/w6_split_manifest.json` 记录参数与计数，供复算与审计。

**已知代价（如实记录）**：对半切后每侧正例约 125 条，正例底盘更薄，单点指标噪声更大
（对应缺憾 A2-14）。因此 v2 的结论须同时报出两侧指标与样本量，不得只报更好的一侧。
若 W4（四五星开采）产出新标签集，则 val_v3 须在新标签集上重划，协议不变。

用法：python v2_w6_split.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np
from sklearn.model_selection import train_test_split

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
VAL_CSV = os.path.join(HERE, "val_v2.csv")
TUNE_CSV = os.path.join(HERE, "val_v3_tune.csv")
TEST_CSV = os.path.join(HERE, "val_v3_test.csv")
MANIFEST = os.path.join(HERE, "v2", "w6_split_manifest.json")
SEED = 42


def main() -> int:
    texts, labels = [], []
    with open(VAL_CSV, encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            texts.append(str(row["text"]))
            labels.append(int(float(row["sound_negative"])))
    n_pos = sum(labels)
    print(f"输入 {VAL_CSV}: {len(texts)} 行，正例 {n_pos}")

    idx = np.arange(len(texts))
    i_tr, i_te = train_test_split(idx, test_size=0.5, random_state=SEED,
                                  stratify=labels)

    def dump(path, indices):
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["text", "sound_negative"])
            for i in indices:
                w.writerow([texts[i], labels[i]])
        pos = sum(labels[i] for i in indices)
        print(f"  -> {os.path.basename(path)}: {len(indices)} 行，正例 {pos}")
        return {"file": os.path.basename(path), "n": len(indices), "pos": int(pos)}

    a = dump(TUNE_CSV, i_tr)
    b = dump(TEST_CSV, i_te)

    manifest = {
        "purpose": "W6：阈值选择与指标报告分离（消除 A1-8 同集选阈值的乐观偏置）",
        "source": os.path.basename(VAL_CSV),
        "source_n": len(texts),
        "source_pos": int(n_pos),
        "seed": SEED,
        "test_size": 0.5,
        "stratify": "sound_negative",
        "roles": {"val_v3_tune": "只用于选阈值/校准/早停等一切调参",
                  "val_v3_test": "只用于报告最终指标；不得用于任何选择"},
        "tune": a,
        "test": b,
        "caveat": "对半切后每侧正例约 125 条，单点指标噪声更大（A2-14）；"
                  "结论须报双侧与样本量，不得只报更优侧。",
        "gen": "[v2]",
    }
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(f"[写出] {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
