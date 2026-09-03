# -*- coding: utf-8 -*-
# 本脚本用于修正置信度分层：中置信区间改为 [0.60, 0.80)，
# conf=0.80 的样本移入高置信，仅重新生成 confidence_tiered.md 与抽查文件。
import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CONF_RESULT = os.path.join(HERE, "conf_review_result.jsonl")
LABELED_CSV = os.path.join(HERE, "labeled_llm.csv")
TIER_MD = os.path.join(HERE, "confidence_tiered.md")
MID_REVIEW_CSV = os.path.join(HERE, "human_review_conf30.csv")


def main() -> None:
    df = pd.read_csv(LABELED_CSV, encoding="utf-8")
    confs = []
    with open(CONF_RESULT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                confs.append(json.loads(line))

    high = [c for c in confs if c["confidence"] >= 0.8]
    mid = [c for c in confs if 0.6 <= c["confidence"] < 0.8]
    low = [c for c in confs if c["confidence"] < 0.6]
    print(f"高置信(>=0.8): {len(high)} | 中置信([0.6,0.8)): {len(mid)} | "
          f"低置信(<0.6): {len(low)}")

    lines = [
        "# 三星补漏正例置信度分层报告",
        "",
        f"复核样本总数：{len(confs)}",
        f"高置信（≥0.8）：{len(high)} 条，直接保留",
        f"中置信（[0.60, 0.80)）：{len(mid)} 条，抽 30 条人工验证",
        f"低置信（<0.6）：{len(low)} 条，标记待二次审核",
        "",
        "## 中置信抽样清单（供人工验证）",
    ]
    for c in mid:
        txt = str(df.loc[c["id"], "text"])[:100]
        lines.append(f"- id={c['id']} conf={c['confidence']:.2f}: {txt}")
    lines.append("")
    lines.append("## 低置信清单（待二次审核）")
    for c in low:
        txt = str(df.loc[c["id"], "text"])[:80]
        lines.append(f"- id={c['id']} conf={c['confidence']:.2f}: {txt}")
    with open(TIER_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    out = pd.DataFrame({
        "id": [c["id"] for c in mid],
        "confidence": [c["confidence"] for c in mid],
        "text": [str(df.loc[c["id"], "text"]) for c in mid],
        "人工判定_留空": "",
    })
    out.to_csv(MID_REVIEW_CSV, index=False, encoding="utf-8-sig")
    print(f"已更新 -> {TIER_MD} 与 {MID_REVIEW_CSV}")


if __name__ == "__main__":
    main()
