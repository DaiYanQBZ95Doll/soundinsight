# -*- coding: utf-8 -*-
# 本脚本用于中置信人工验证结果处置：人工判定为 1 的样本保留，
# 判定为 0 的样本从正例降级，并更新置信度分层报告。
import json
import os
import shutil
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CONF_RESULT = os.path.join(HERE, "conf_review_result.jsonl")
LABELED_CSV = os.path.join(HERE, "labeled_llm.csv")
BACKUP_CSV = os.path.join(HERE, "labeled_llm_before_mid_demote.csv")
TIER_MD = os.path.join(HERE, "confidence_tiered.md")

CONFIRMED_IDS = {50050, 77225, 97174}


def main() -> None:
    confs = []
    with open(CONF_RESULT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                confs.append(json.loads(line))
    mid = [c for c in confs if 0.6 <= c["confidence"] < 0.8]
    mid_ids = {c["id"] for c in mid}
    print(f"中置信样本共 {len(mid_ids)} 条")

    df = pd.read_csv(LABELED_CSV, encoding="utf-8")
    before = int(df["sound_negative_llm"].sum())
    demoted = []
    for i in mid_ids:
        if i in df.index and df.loc[i, "sound_negative_llm"] == 1:
            if i not in CONFIRMED_IDS:
                df.loc[i, "sound_negative_llm"] = 0
                demoted.append(int(i))
    after = int(df["sound_negative_llm"].sum())
    shutil.copy2(LABELED_CSV, BACKUP_CSV)
    df.to_csv(LABELED_CSV, index=False, encoding="utf-8")
    print(f"降级 {len(demoted)} 条: {demoted}")
    print(f"正例 {before} -> {after}")

    lines = [
        "# 三星补漏正例置信度分层报告",
        "",
        f"复核样本总数：{len(confs)}",
        f"高置信（≥0.8）：{len([c for c in confs if c['confidence'] >= 0.8])} 条，直接保留",
        f"中置信（[0.60, 0.80)）：{len(mid)} 条，已人工验证",
        f"低置信（<0.6）：{len([c for c in confs if c['confidence'] < 0.6])} 条，标记待二次审核",
        "",
        "## 中置信人工验证结论",
        f"人工判定 8 条中确认 3 条（准确率 37.5%），低于 60% 质量线。",
        f"确认保留: {sorted(CONFIRMED_IDS)}",
        f"降级为非正例: {demoted}",
        "已按验证结果更新 labeled_llm.csv，备份为 "
        "labeled_llm_before_mid_demote.csv。",
        "冻结口径 1257 与全部实验数字不受影响（中置信样本均属三星补漏扩展部分）。",
    ]
    with open(TIER_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"更新 -> {TIER_MD}")


if __name__ == "__main__":
    main()
