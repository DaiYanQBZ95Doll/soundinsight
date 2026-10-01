# -*- coding: utf-8 -*-
"""高音路径的候选筛选：从 355 条 LLM 判正中筛出「耳机/耳塞」在范围内的条目。
规则（机械、可复算）：文本须出现耳机类词；再统计 LLM 给的 classes 分布。
输出：`v2/treble_candidates.json`（含 train/holdout 划分归属，防泄漏）
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from sklearn.model_selection import train_test_split  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 42
HP = re.compile(r"\b(earbuds?|ear\s?buds?|earphones?|headphones?|headsets?|in-?ear|"
                r"on-?ear|over-?ear|airpods?|iems?|buds?|earpieces?)\b", re.I)

texts, labels = [], []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
        labels.append(int(r.get("sound_negative_llm") or 0))
idx = list(range(len(texts)))
i_tr, i_ho = train_test_split(idx, test_size=0.2, random_state=SEED, stratify=labels)
train_set, holdout_set = set(i_tr), set(i_ho)
print(f"划分重建：train {len(i_tr):,}（正例 {sum(labels[i] for i in i_tr)}）｜"
      f"holdout {len(i_ho):,}（正例 {sum(labels[i] for i in i_ho)}）")

pos = []
for line in open(os.path.join(HERE, "v2", "review_treble.jsonl"), encoding="utf-8",
                 errors="replace"):
    try:
        r = json.loads(line)
    except ValueError:
        continue
    if int(r.get("sound_negative") or 0) == 1:
        pos.append(r)
print(f"高音桶 LLM 判正 {len(pos)} 条")

in_scope = [r for r in pos if HP.search(texts[int(r["row_index"])])]
print(f"耳机规则命中（在范围内）{len(in_scope)} 条｜未命中（跨品类/非耳机）{len(pos)-len(in_scope)} 条")
tr_new = [r for r in in_scope if int(r["row_index"]) in train_set]
ho_new = [r for r in in_scope if int(r["row_index"]) in holdout_set]
print(f"  其中落在 **训练划分** {len(tr_new)} 条（可用于重训）；落在 **留出划分** {len(ho_new)} 条"
      f"（**不得**用于训练；若属实说明测试集有噪声，单列报告）")

cls = {}
for r in tr_new:
    for c in (r.get("classes") or []):
        cls[c] = cls.get(c, 0) + 1
print(f"  训练侧新增正例的类别分布：{cls}")
n_treble_new = sum(1 for r in tr_new if "treble" in (r.get("classes") or []))
print(f"  其中带 treble 类标签的：{n_treble_new} 条")

# 现有标签集里 treble 类的正例数（对照）
cur_treble = 0
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        if int(r.get("sound_negative_llm") or 0) == 1:
            issues = str(r.get("issues") or r.get("issues_llm") or "")
            if "treble" in issues.lower() or "高音" in issues:
                cur_treble += 1
print(f"  现有标签集带 treble 的正例（近似统计）：{cur_treble} 条")

json.dump({"llm_positive": len(pos), "in_scope": len(in_scope),
           "train_split_new": [int(r["row_index"]) for r in tr_new],
           "holdout_split_new": [int(r["row_index"]) for r in ho_new],
           "train_class_dist": cls, "train_treble_tagged": n_treble_new,
           "current_treble_positives_approx": cur_treble,
           "rule": "耳机规则 = 文本含 earbud/earphone/headphone/headset/bud/airpod 等词（机械可复算）",
           "caveat": "LLM 口径，未经人工校准；筛选规则为机械规则，非人工判定"},
          open(os.path.join(HERE, "v2", "treble_candidates.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[写出] v2/treble_candidates.json")
