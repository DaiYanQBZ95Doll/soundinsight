# -*- coding: utf-8 -*-
# 本脚本用于生成样例评论集：从 val_v2 抽样 100 条，覆盖明确差评、
# 明确非音质、边界案例与多语言，用于视频录制与评委自测。
import json
import os
import re
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
VAL_CSV = os.path.join(HERE, "val_v2.csv")
OUT_CSV = os.path.join(HERE, "sample_reviews_100.csv")

EDGE_PATTERNS = {
    "委婉表达": r"expected|not as|fine for|acceptable|could be better",
    "中性比较": r"not as loud|weaker|compared|previous|vs",
    "关键词误触": r"sound like|sounds like|static.*(?:pack|ship)|crisp.*(?:pack|box)",
    "评分冲突": r"",
    "极短评论": r"",
}


def main() -> None:
    df = pd.read_csv(VAL_CSV, encoding="utf-8")
    pos = df[df["sound_negative"] == 1]
    neg = df[df["sound_negative"] == 0]

    picks = []
    # 1) 明确音质差评 12 条
    picks += [("明确音质差评", i, 1) for i in
              pos.sample(n=12, random_state=42).index]
    # 2) 明确非音质 62 条
    picks += [("明确非音质", i, 0) for i in
              neg.sample(n=62, random_state=7).index]
    # 3) 边界案例：委婉/中性比较/含关键词非音质/极短 共 24 条
    bound = neg[~neg.index.isin([p[1] for p in picks])]
    euphemistic = bound[bound["text"].str.contains(
        r"expected|not as|fine for|acceptable|could be better",
        case=False, regex=True, na=False)]
    picks += [("边界-委婉表达", i, 0) for i in
              euphemistic.sample(n=min(8, len(euphemistic)),
                                 random_state=3).index]
    used = {p[1] for p in picks}
    neutral = bound[~bound.index.isin(used)]
    neutral = neutral[neutral["text"].str.contains(
        r"not as loud|weaker|compared|previous pair|vs\b",
        case=False, regex=True, na=False)]
    picks += [("边界-中性比较", i, 0) for i in
              neutral.sample(n=min(7, len(neutral)), random_state=3).index]
    used = {p[1] for p in picks}
    keyword_hit = bound[~bound.index.isin(used)]
    keyword_hit = keyword_hit[keyword_hit["text"].str.contains(
        r"sound like|sounds like|static|bass|treble|crisp",
        case=False, regex=True, na=False)]
    picks += [("边界-含关键词非音质", i, 0) for i in
              keyword_hit.sample(n=min(7, len(keyword_hit)), random_state=3).index]
    used = {p[1] for p in picks}
    short = bound[~bound.index.isin(used)]
    short = short[short["text"].str.len() <= 25]
    picks += [("边界-极短评论", i, 0) for i in
              short.sample(n=min(2, len(short)), random_state=3).index]
    # 4) 多语言 2 条（从非音质中找非英文）
    used = {p[1] for p in picks}
    non_en = neg[~neg.index.isin(used)]
    non_en = non_en[non_en["text"].str.contains(
        r"[àáâäèéêëìíîïòóôöùúûüñç¿¡]", regex=True, na=False)]
    picks += [("多语言-预期低置信", i, 0) for i in
              non_en.sample(n=min(2, len(non_en)), random_state=3).index]

    rows = []
    for label, idx, expected in picks:
        rows.append({
            "text": str(df.loc[idx, "text"]),
            "rating": 0,  # val_v2 无 rating 列，置空标记
            "期望标签": expected,
            "类别": label,
        })
    out = pd.DataFrame(rows)
    out = out.drop_duplicates(subset=["text"]).head(100)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"生成 {len(out)} 条 -> {OUT_CSV}")
    print(out["类别"].value_counts().to_string())
    print(out["期望标签"].value_counts().to_string())


if __name__ == "__main__":
    main()
