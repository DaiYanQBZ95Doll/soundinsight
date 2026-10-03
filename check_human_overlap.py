# -*- coding: utf-8 -*-
"""修正版：S4 的 row_index 取自 v2/s1_add100_ids.json（其 CSV 无该列）。"""
from __future__ import annotations

import csv
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 42

texts, labels = [], []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for row in csv.DictReader(fh):
        texts.append(str(row["text"]))
        labels.append(int(float(row.get("sound_negative_llm") or 0)))
from sklearn.model_selection import train_test_split  # noqa: E402
tr_idx, va_idx = train_test_split(list(range(len(labels))), test_size=0.2,
                                  random_state=SEED, stratify=labels)
train_set, holdout = set(tr_idx), set(va_idx)
print(f"语料 {len(labels):,}（正例 {sum(labels)}）｜训练侧 {len(train_set):,}｜留出侧 {len(holdout):,}")

human = {}
for it in json.load(open(os.path.join(HERE, "v2", "gold_set_key.json"),
                         encoding="utf-8"))["items"]:
    human[it["id"]] = it["row_index"]
s4 = json.load(open(os.path.join(HERE, "v2", "s1_add100_ids.json"), encoding="utf-8"))
for k, ridx in enumerate(s4.get("row_index", []), 1):
    human[f"S4-{k:03d}"] = ridx
with open(os.path.join(HERE, "docs/gold_set/s5_clean_probe.csv"),
          encoding="utf-8-sig", errors="replace") as fh:
    for r in csv.DictReader(fh):
        ridx = str(r.get("row_index", "")).strip()
        if ridx:
            human[r["编号"]] = int(ridx)
print(f"人工条目 {len(human)} 条（含 row_index 映射）")

in_train = [u for u, i in human.items() if i in train_set]
in_hold = [u for u, i in human.items() if i in holdout]
print(f"\n训练侧（模型见过）**{len(in_train)}** 条（{len(in_train)/len(human)*100:.1f}%）")
print(f"留出侧（干净）  **{len(in_hold)}** 条（{len(in_hold)/len(human)*100:.1f}%）")
by = {}
for u, i in human.items():
    s = u.split("-")[0] if "-" in u else u[0]
    d = by.setdefault(s, [0, 0])
    d[0 if i in train_set else 1] += 1
print("\n分层（训练侧/留出侧）：" + "｜".join(f"{s} {a}/{b}" for s, (a, b) in sorted(by.items())))

json.dump({"seed": SEED, "train_side": sorted(in_train), "holdout_side": sorted(in_hold)},
          open(os.path.join(HERE, "v2", "human_overlap_split.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\n[写出] v2/human_overlap_split.json")
