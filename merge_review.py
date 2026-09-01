# -*- coding: utf-8 -*-
# 本脚本用于合并 LLM 复核结果：统计弱标注精度，生成经 LLM 清洗的最终标签集。
import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
LABELED_CSV = os.path.join(HERE, "labeled_expanded.csv")
REVIEW_JSONL = os.path.join(HERE, "review_result.jsonl")
OUT_CSV = os.path.join(HERE, "labeled_llm.csv")

ISSUE_COLS = ["issue_bass", "issue_clarity", "issue_noise",
              "issue_volume", "issue_treble"]


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

    n_reviewed = len(verdicts)
    ids = list(verdicts.keys())
    sub = df.loc[ids].copy()
    sub["llm_verdict"] = [verdicts[i]["verdict"] for i in ids]

    # 弱标注精度：LLM 确认为正例的比例
    precision = float((sub["llm_verdict"] == 1).mean())
    print(f"LLM 复核样本: {n_reviewed}")
    print(f"弱标注精度（LLM确认为正例）: {precision:.2%}")
    print("按评分分层:")
    print(sub.groupby("rating")["llm_verdict"].agg(["count", "mean"]).to_string())

    # 生成 LLM 清洗后的标签
    df["sound_negative_llm"] = 0
    df.loc[ids, "sound_negative_llm"] = sub["llm_verdict"].values
    for col in ISSUE_COLS:
        df[col + "_llm"] = 0
    for i in ids:
        for iss in verdicts[i].get("issues", []):
            col = "issue_" + iss + "_llm"
            if col in df.columns:
                df.loc[i, col] = 1

    n_pos = int(df["sound_negative_llm"].sum())
    print(f"清洗后正例: {n_pos} ({n_pos / len(df):.2%})")
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"保存 -> {OUT_CSV}")


if __name__ == "__main__":
    main()
