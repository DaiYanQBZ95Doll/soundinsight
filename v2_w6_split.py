# -*- coding: utf-8 -*-
"""W6：生成 val_v3_tune / val_v3_test（**从当前标签集的留出划分中抽取，保证无泄漏**）。

## 为什么不能再用 val_v2 的文本（2026-09-30 实测发现）

`val_v2.csv` 是早期用"当时的 `labeled_llm.csv` + seed 42 + 20% 分层"生成的留出集。
此后 `labeled_llm.csv` 被重建（RLCA 高音补捞、中置信剔除、时间戳考古重排），**行序已变**，
于是"用当前文件复算同一划分"得到的训练集与 val_v2 **大量重叠**：

    实测：val_v2 的 20,000 条文本中 **15,891 条（79.5%）** 落在当前 80% 训练划分内，
    其中正例 **198/251（78.9%）**。

后果：在 val_v2 上评估"用当前 labeled_llm 训练的模型"会因**记忆**而虚高
（实测一次 max_len=256 训练即得到 F1@0.5 = 0.9126，远高于 v1 的 0.6241 —— 该数字已作废）。

## 本版口径（无泄漏）

- 数据源：**当前** `labeled_llm.csv`（100,000 行，正例 1,280）；
- 先按 seed 42、test_size=0.2、`stratify=sound_negative_llm` 划出 **20,000 条留出集**（与训练集互斥）；
- 再把留出集按 seed 42 对半切成 `val_v3_tune` / `val_v3_test`（各约 10,000 条、正例约 128）；
- 输出列：`text, sound_negative, issue_*_llm`（现行标签）；
- manifest 记录：划分参数、计数、**与 val_v2 的重叠核查结果**（用于留痕该次泄漏发现）。

**与 v1 的可比性**：v1 的 0.6871/0.6241 是在 val_v2 上得到的；本划分是**不同样本集**，
两代数字**不可直比**（与 `docs/v2_acceptance_benchmark.md` §四 的"双验证集并列声明"一致）。

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
LLM_CSV = os.path.join(HERE, "labeled_llm.csv")
VAL_V2 = os.path.join(HERE, "val_v2.csv")
TUNE_CSV = os.path.join(HERE, "val_v3_tune.csv")
TEST_CSV = os.path.join(HERE, "val_v3_test.csv")
MANIFEST = os.path.join(HERE, "v2", "w6_split_manifest.json")
SEED = 42
ISSUES = ("issue_bass_llm", "issue_clarity_llm", "issue_noise_llm",
          "issue_volume_llm", "issue_treble_llm")
COLS = ["text", "sound_negative"] + list(ISSUES)


def main() -> int:
    texts, labels, issues = [], [], []
    with open(LLM_CSV, encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            texts.append(str(row["text"]))
            labels.append(int(float(row.get("sound_negative_llm") or 0)))
            issues.append([int(float(row.get(c) or 0)) for c in ISSUES])
    print(f"当前标签集：{len(texts)} 行，正例 {sum(labels)}")

    idx = np.arange(len(texts))
    i_tr, i_ho = train_test_split(idx, test_size=0.2, random_state=SEED,
                                  stratify=labels)
    print(f"留出集 {len(i_ho)} 行（正例 {sum(labels[i] for i in i_ho)}）；"
          f"训练集 {len(i_tr)} 行（正例 {sum(labels[i] for i in i_tr)}）")

    # 与 val_v2 的重叠核查（留痕该次泄漏发现）
    ho_texts = {texts[i] for i in i_ho}
    tr_texts = {texts[i] for i in i_tr}
    v2_texts, v2_pos = [], []
    with open(VAL_V2, encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            t = str(row["text"])
            v2_texts.append(t)
            if str(row["sound_negative"]).strip() == "1":
                v2_pos.append(t)
    overlap_train = sum(1 for t in v2_texts if t in tr_texts)
    overlap_holdout = sum(1 for t in v2_texts if t in ho_texts)
    pos_overlap_train = sum(1 for t in v2_pos if t in tr_texts)
    print(f"[泄漏核查] val_v2 文本落在**当前训练集**：{overlap_train}/{len(v2_texts)}"
          f"（{overlap_train / len(v2_texts) * 100:.1f}%）"
          f"；其中正例 {pos_overlap_train}/{len(v2_pos)}"
          f"（{pos_overlap_train / max(len(v2_pos), 1) * 100:.1f}%）")
    print(f"[泄漏核查] val_v2 文本落在**当前留出集**：{overlap_holdout}/{len(v2_texts)}"
          f"（{overlap_holdout / len(v2_texts) * 100:.1f}%）")

    i_ho = np.array(i_ho)
    y_ho = [labels[i] for i in i_ho]
    i_tune, i_test = train_test_split(i_ho, test_size=0.5, random_state=SEED,
                                      stratify=y_ho)

    def dump(path, indices):
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(COLS)
            for i in indices:
                w.writerow([texts[i], labels[i]] + issues[i])
        pos = sum(labels[i] for i in indices)
        per = [sum(issues[i][j] for i in indices) for j in range(len(ISSUES))]
        print(f"  -> {os.path.basename(path)}: {len(indices)} 行，正例 {pos}，五类 {per}")
        return {"file": os.path.basename(path), "n": len(indices), "pos": int(pos),
                "pos_per_class": per}

    a = dump(TUNE_CSV, i_tune)
    b = dump(TEST_CSV, i_test)

    manifest = {
        "purpose": "W6：阈值选择与指标报告分离（消除 A1-8 同集选阈值的乐观偏置）",
        "v1_1_correction": "初版从 val_v2 文本取样；实测发现 val_v2 与当前训练划分重叠 "
                           "79.5%（正例 78.9%），会造成记忆虚高，故改为从**当前标签集的"
                           "留出划分**取样。",
        "label_generation": "[v2]（当前 labeled_llm.csv）",
        "source": os.path.basename(LLM_CSV),
        "source_n": len(texts), "source_pos": int(sum(labels)),
        "holdout_n": int(len(i_ho)), "holdout_pos": int(sum(y_ho)),
        "train_n": int(len(i_tr)), "train_pos": int(sum(labels[i] for i in i_tr)),
        "seed": SEED, "holdout_fraction": 0.2, "split_within_holdout": 0.5,
        "leak_check_vs_val_v2": {
            "val_v2_n": len(v2_texts),
            "in_current_train": overlap_train,
            "in_current_train_pct": round(overlap_train / len(v2_texts) * 100, 1),
            "pos_in_current_train": pos_overlap_train,
            "pos_in_current_train_pct": round(pos_overlap_train / max(len(v2_pos), 1) * 100, 1),
            "in_current_holdout": overlap_holdout,
            "conclusion": "val_v2 不再是当前标签集的有效留出集；v1 数字只在 val_v2 上有效，"
                          "两代不可直比",
        },
        "roles": {"val_v3_tune": "只用于选阈值/校准/早停等一切调参",
                  "val_v3_test": "只用于报告最终指标；不得用于任何选择"},
        "columns": COLS,
        "tune": a, "test": b,
        "caveat": "留出集正例约 256 条，对半切后每侧约 128 条，单点指标噪声大（A2-14）；"
                  "结论须报双侧与样本量。",
    }
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(f"[写出] {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
