# -*- coding: utf-8 -*-
"""W6：生成 val_v3_tune / val_v3_test 划分（**用 v2 当前标签**，并保留 v1 标签供对照）。

为什么需要（冻结清单 §二 W6、`docs/v2_acceptance_benchmark.md` §四）：
v1 的阈值是在**同一集合**上网格搜索并报数（`distilbert_cv.py:90`），构成从未披露的
乐观偏置（缺憾 A1-8）。v2 起必须把"选阈值"与"报指标"分开。

**口径（v1.1 更正，2026-09-30）**：
初版直接用 `val_v2.csv` 的**冻结 v1 标签**对半切。复核后确认：v1 标签与现行
`labeled_llm.csv` 在同一批 20,000 条文本上**仅 6 条不一致、4 条缺失**（实测），
即标签基本稳定；但 v2 的指标仍应以**现行标签**为准，故本版：
- 取 val_v2 的 20,000 条**文本**（保持与 v1 评测集同一批样本，便于对照）；
- 标签改用**现行标签集**（`labeled_llm.csv` 的 `sound_negative_llm` 与五类 `issue_*_llm`），
  按文本连接取得（实测命中 19,996/20,000，未命中 4 条剔除并计数）；
- 以**现行标签**分层、seed 42、test_size=0.5 对半切；
- 输出列：`text, sound_negative, v1_label, issue_bass_llm, issue_clarity_llm,
  issue_noise_llm, issue_volume_llm, issue_treble_llm`（`v1_label` 仅作对照，不参与训练/选阈值）；
- manifest 记录两代标签的计数与漂移量。

> 更正留痕：本文件初版 docstring 曾写"val_v2 的 73 条漏报中 71 条在现行标签集下已不是
> 正例"。该说法来自 `v2_w17_failure_stats.py` 一处**取反错误**，经直接测量推翻：
> 实际为 **72/73 仍为正例（真实漏检）**、FP 侧 91/91 仍为负例（真实误报）。
> 两处均已修正。

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
VAL_CSV = os.path.join(HERE, "val_v2.csv")
LLM_CSV = os.path.join(HERE, "labeled_llm.csv")
TUNE_CSV = os.path.join(HERE, "val_v3_tune.csv")
TEST_CSV = os.path.join(HERE, "val_v3_test.csv")
MANIFEST = os.path.join(HERE, "v2", "w6_split_manifest.json")
SEED = 42
ISSUES = ("issue_bass_llm", "issue_clarity_llm", "issue_noise_llm",
          "issue_volume_llm", "issue_treble_llm")
COLS = ["text", "sound_negative", "v1_label"] + list(ISSUES)


def main() -> int:
    # 1) v1 冻结集的文本与标签
    v1_texts, v1_labels = [], []
    with open(VAL_CSV, encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            v1_texts.append(str(row["text"]))
            v1_labels.append(int(float(row["sound_negative"])))

    # 2) 现行标签集：文本 → (label, issues)
    cur = {}
    with open(LLM_CSV, encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            t = str(row["text"])
            if t in cur:
                continue
            cur[t] = (int(float(row.get("sound_negative_llm") or 0)),
                      [int(float(row.get(c) or 0)) for c in ISSUES])

    texts, labels, issues, v1_kept, missing = [], [], [], [], 0
    for t, v1l in zip(v1_texts, v1_labels):
        got = cur.get(t) or cur.get(t.strip())
        if not got:
            missing += 1
            continue
        texts.append(t)
        labels.append(got[0])
        issues.append(got[1])
        v1_kept.append(v1l)

    n_pos = sum(labels)
    n_pos_v1 = sum(v1_kept)
    print(f"样本 {len(texts)}（未命中现行标签 {missing} 条已剔除）")
    print(f"现行标签正例 {n_pos}；同一批文本的 v1 标签正例 {n_pos_v1}")
    drift = sum(1 for a, b in zip(labels, v1_kept) if a != b)
    print(f"两代标签不一致：{drift} 条（{drift / max(len(labels), 1) * 100:.2f}%）")

    idx = np.arange(len(texts))
    i_tr, i_te = train_test_split(idx, test_size=0.5, random_state=SEED,
                                  stratify=labels)

    def dump(path, indices):
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(COLS)
            for i in indices:
                w.writerow([texts[i], labels[i], v1_kept[i]] + issues[i])
        pos = sum(labels[i] for i in indices)
        per_class = [sum(issues[i][j] for i in indices) for j in range(len(ISSUES))]
        print(f"  -> {os.path.basename(path)}: {len(indices)} 行，正例 {pos}，"
              f"五类正例 {per_class}")
        return {"file": os.path.basename(path), "n": len(indices), "pos": int(pos),
                "pos_per_class": per_class,
                "v1_pos_same_rows": int(sum(v1_kept[i] for i in indices))}

    a = dump(TUNE_CSV, i_tr)
    b = dump(TEST_CSV, i_te)

    manifest = {
        "purpose": "W6：阈值选择与指标报告分离（消除 A1-8 同集选阈值的乐观偏置）",
        "label_generation": "[v2]（现行 labeled_llm 的 sound_negative_llm 与 issue_*_llm）",
        "sample_source": f"{os.path.basename(VAL_CSV)} 的 20,000 条文本（与 v1 评测集同批样本）",
        "label_join": {"method": "按 text 精确连接（含 strip 兜底）",
                       "matched": len(texts), "missing_dropped": missing},
        "drift_vs_v1": {"rows_with_different_label": drift,
                        "pct": round(drift / max(len(labels), 1) * 100, 2),
                        "v1_pos": int(n_pos_v1), "v2_pos": int(n_pos)},
        "seed": SEED, "test_size": 0.5, "stratify": "sound_negative（现行标签）",
        "roles": {"val_v3_tune": "只用于选阈值/校准/早停等一切调参",
                  "val_v3_test": "只用于报告最终指标；不得用于任何选择"},
        "columns": COLS,
        "tune": a, "test": b,
        "caveat": "对半切后每侧正例约 120 条，单点指标噪声更大（A2-14）；"
                  "结论须报双侧与样本量，不得只报更优侧。v1_label 列仅供对照，不参与调参。",
        "v1_reference": "v1 的历史指标须在 val_v2.csv（冻结 v1 标签）上计算，不与本文件混比",
    }
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(f"[写出] {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
