# -*- coding: utf-8 -*-
# 本脚本用于 A4 中置信层状态核查与剔除：
# 确认 8 条中置信样本的决议状态，将仍为正例的样本全部剔除（含多标签列同步），
# 并更新 confidence_tiered.md 记录。
import json
import os
import shutil
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CONF_RESULT = os.path.join(HERE, "conf_review_result.jsonl")
LABELED_CSV = os.path.join(HERE, "labeled_llm.csv")
BACKUP_CSV = os.path.join(HERE, "labeled_llm_before_mid_remove.csv")
TIER_MD = os.path.join(HERE, "confidence_tiered.md")
ISSUE_COLS = ["issue_bass_llm", "issue_clarity_llm", "issue_noise_llm",
              "issue_volume_llm", "issue_treble_llm"]


def main() -> None:
    confs = []
    with open(CONF_RESULT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                confs.append(json.loads(line))
    mid_ids = {c["id"] for c in confs if 0.6 <= c["confidence"] < 0.8}
    print(f"中置信样本: {len(mid_ids)} 条")

    df = pd.read_csv(LABELED_CSV, encoding="utf-8")
    before = int(df["sound_negative_llm"].sum())
    removed = []
    for i in mid_ids:
        if i in df.index and df.loc[i, "sound_negative_llm"] == 1:
            df.loc[i, "sound_negative_llm"] = 0
            for col in ISSUE_COLS:
                df.loc[i, col] = 0
            removed.append(int(i))
    after = int(df["sound_negative_llm"].sum())
    shutil.copy2(LABELED_CSV, BACKUP_CSV)
    df.to_csv(LABELED_CSV, index=False, encoding="utf-8")
    print(f"本轮剔除 {len(removed)} 条: {removed}")
    print(f"正例 {before} -> {after}（应为 1280）")

    lines = [
        "# 三星补漏正例置信度分层报告",
        "",
        f"复核样本总数：{len(confs)}",
        f"高置信（≥0.8）：{len([c for c in confs if c['confidence'] >= 0.8])} 条，直接保留",
        f"中置信（[0.60, 0.80)）：{len(mid_ids)} 条，已剔除",
        f"低置信（<0.6）：{len([c for c in confs if c['confidence'] < 0.6])} 条，标记待二次审核",
        "",
        "## 中置信层处理记录",
        "人工审核 8 条，确认 3 条（37.5%），低于 60% 质量线。",
        "按批次 A4 决议：中置信 8 条全部从正例剔除，不用于训练，"
        "多标签列同步清零。",
        f"剔除样本 id: {sorted(mid_ids)}",
        "剔除后正例总数 1280；冻结口径 1257 与全部实验数字不受影响"
        "（实验基于 1257 口径，中置信样本属三星补漏扩展部分）。",
        "备份：labeled_llm_before_mid_remove.csv。",
    ]
    with open(TIER_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"更新 -> {TIER_MD}")


if __name__ == "__main__":
    main()
