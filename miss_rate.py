# -*- coding: utf-8 -*-
# 本脚本用于统计漏检率：读取 LLM 对规则判负样本的复核结果，
# 估算关键词规则的漏检比例，并输出分层统计。
import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_expanded.csv")
REVIEW_JSONL = os.path.join(HERE, "neg_review_result.jsonl")


def main() -> None:
    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    verdicts = {}
    with open(REVIEW_JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            verdicts[int(rec["id"])] = rec["verdict"]

    ids = list(verdicts.keys())
    sub = df.loc[ids].copy()
    sub["llm_verdict"] = [verdicts[i] for i in ids]
    missed = int((sub["llm_verdict"] == 1).sum())
    print(f"漏检抽样: {len(sub)} 条 | LLM 判定为漏检正例: {missed}")
    print("分层统计:")
    grp = sub.groupby(["sound_related", "rating"])["llm_verdict"]
    print(grp.agg(["count", "sum"]).to_string())
    # 规则总判负样本量：全部 - 1502 弱标注正例
    total_neg = len(df) - 1502
    print(f"规则判负总量: {total_neg}")
    # 简单外推（按抽样比例）
    g3_missed = int(sub[(sub["sound_related"] == 1) & (sub["rating"] == 3)]
                    ["llm_verdict"].sum())
    g3_total = len(df[(df["sound_related"] == 1) & (df["rating"] == 3)])
    print(f"音质相关三星样本: {g3_total} | 抽样漏检 {g3_missed}/200"
          f" -> 外推漏检约 {int(g3_total * g3_missed / 200)} 条")


if __name__ == "__main__":
    main()
