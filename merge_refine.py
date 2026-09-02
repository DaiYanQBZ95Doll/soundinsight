# -*- coding: utf-8 -*-
# 本脚本用于数据提纯合并：生成三星补漏置信度分层报告，
# 并把 LLM 确认的高音正例合并进 labeled_llm.csv（合并前自动备份）。
import json
import os
import shutil
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CONF_RESULT = os.path.join(HERE, "conf_review_result.jsonl")
TREBLE_RESULT = os.path.join(HERE, "treble_result.jsonl")
LABELED_CSV = os.path.join(HERE, "labeled_llm.csv")
BACKUP_CSV = os.path.join(HERE, "labeled_llm_before_treble.csv")
TIER_MD = os.path.join(HERE, "confidence_tiered.md")
MID_REVIEW_CSV = os.path.join(HERE, "human_review_conf30.csv")


def main() -> None:
    df = pd.read_csv(LABELED_CSV, encoding="utf-8")

    # 一、置信度分层
    confs = []
    with open(CONF_RESULT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                confs.append(json.loads(line))
    high = [c for c in confs if c["confidence"] > 0.8]
    mid = [c for c in confs if 0.6 <= c["confidence"] <= 0.8]
    low = [c for c in confs if c["confidence"] < 0.6]
    lines = [
        "# 三星补漏正例置信度分层报告",
        "",
        f"复核样本总数：{len(confs)}",
        f"高置信（>0.8）：{len(high)} 条，直接保留",
        f"中置信（0.6-0.8）：{len(mid)} 条，抽 30 条人工验证",
        f"低置信（<0.6）：{len(low)} 条，标记待二次审核",
        "",
        "## 中置信抽样清单（前 30 条，供人工验证）",
    ]
    mid_sample = mid[:30]
    for c in mid_sample:
        txt = str(df.loc[c["id"], "text"])[:100]
        lines.append(f"- id={c['id']} conf={c['confidence']:.2f}: {txt}")
    lines.append("")
    lines.append("## 低置信清单（待二次审核）")
    for c in low:
        txt = str(df.loc[c["id"], "text"])[:80]
        lines.append(f"- id={c['id']} conf={c['confidence']:.2f}: {txt}")
    with open(TIER_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"置信度分层 -> {TIER_MD}")

    out = pd.DataFrame({
        "id": [c["id"] for c in mid_sample],
        "confidence": [c["confidence"] for c in mid_sample],
        "text": [str(df.loc[c["id"], "text"]) for c in mid_sample],
        "人工判定_留空": "",
    })
    out.to_csv(MID_REVIEW_CSV, index=False, encoding="utf-8-sig")
    print(f"中置信抽查文件 -> {MID_REVIEW_CSV}")

    # 二、高音正例合并
    trebles = []
    with open(TREBLE_RESULT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                trebles.append(json.loads(line))
    verified = [t for t in trebles if t["verdict"] == 1]
    treble_pos = [t for t in verified if "treble" in t.get("issues", [])]
    other_pos = [t for t in verified if "treble" not in t.get("issues", [])]
    print(f"高音候选确认正例: {len(verified)} | 含高音问题: {len(treble_pos)}"
          f" | 其他问题: {len(other_pos)}")

    shutil.copy2(LABELED_CSV, BACKUP_CSV)
    print(f"备份 -> {BACKUP_CSV}")

    n_new = 0
    for t in treble_pos:
        i = t["id"]
        if i not in df.index:
            continue
        if df.loc[i, "sound_negative_llm"] == 0:
            n_new += 1
        df.loc[i, "sound_negative_llm"] = 1
        for iss in t.get("issues", []):
            col = "issue_" + iss + "_llm"
            if col in df.columns:
                df.loc[i, col] = 1

    df.to_csv(LABELED_CSV, index=False, encoding="utf-8")
    n_pos = int(df["sound_negative_llm"].sum())
    n_treble = int(df["issue_treble_llm"].sum())
    print(f"合并完成: 新增高音正例 {n_new} 条 | 正例总数 {n_pos} "
          f"| 高音标签总数 {n_treble}")


if __name__ == "__main__":
    main()
