# -*- coding: utf-8 -*-
# C4 前置：从 val_preds_dump.csv 提取 FP/FN 错误样本，生成
# llm_err_input.jsonl（id/kind/text/label/prob），供 LLM 错误分类。
import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP = os.path.join(HERE, "val_preds_dump.csv")
OUT = os.path.join(HERE, "llm_err_input.jsonl")


def main() -> None:
    df = pd.read_csv(DUMP, encoding="utf-8", keep_default_na=False)
    y = df["sound_negative"].astype(int)
    p = df["pred"].astype(int)
    fp = df[(y == 0) & (p == 1)]
    fn = df[(y == 1) & (p == 0)]
    print(f"FP={len(fp)} FN={len(fn)}")
    with open(OUT, "w", encoding="utf-8") as f:
        idx = 0
        for kind, sub in [("fp", fp), ("fn", fn)]:
            for _, row in sub.iterrows():
                f.write(json.dumps({
                    "id": idx,
                    "kind": kind,
                    "text": str(row["text"])[:500],
                    "label": int(row["sound_negative"]),
                    "prob": float(row["prob"]),
                }, ensure_ascii=False) + "\n")
                idx += 1
    print(f"saved -> {OUT} ({idx} rows)")


if __name__ == "__main__":
    main()
