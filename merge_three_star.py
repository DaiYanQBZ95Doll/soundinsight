# -*- coding: utf-8 -*-
# 本脚本用于合并三星样本复核结果：把 LLM 确认的漏检正例并入最终标签集。
import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
LABELED_CSV = os.path.join(HERE, "labeled_llm.csv")
REVIEW_JSONL = os.path.join(HERE, "three_star_result.jsonl")


def main() -> None:
    df = pd.read_csv(LABELED_CSV, encoding="utf-8")
    verdicts = {}
    with open(REVIEW_JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            verdicts[int(rec["id"])] = rec

    n_confirmed = sum(1 for v in verdicts.values() if v["verdict"] == 1)
    print(f"复核: {len(verdicts)} | LLM 确认正例: {n_confirmed}")

    for i, rec in verdicts.items():
        if rec["verdict"] == 1:
            df.loc[i, "sound_negative_llm"] = 1
            for iss in rec.get("issues", []):
                col = "issue_" + iss + "_llm"
                if col in df.columns:
                    df.loc[i, col] = 1

    n_pos = int(df["sound_negative_llm"].sum())
    print(f"合并后正例总数: {n_pos} ({n_pos / len(df):.2%})")
    df.to_csv(LABELED_CSV, index=False, encoding="utf-8")
    print(f"保存 -> {LABELED_CSV}")


if __name__ == "__main__":
    main()
