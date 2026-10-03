# -*- coding: utf-8 -*-
"""核查 LLM 类列覆盖率（`issue_*_llm`），并据此重算"LLM vs 人工"（只在有 LLM 类标签的条目上）。
"""
from __future__ import annotations

import csv
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
COLS = ("issue_bass_llm", "issue_clarity_llm", "issue_noise_llm",
        "issue_volume_llm", "issue_treble_llm")
meta = json.load(open(os.path.join(HERE, "v2", "attribution_ids.json"), encoding="utf-8"))
rows = list(csv.DictReader(open(os.path.join(HERE, "labeled_llm.csv"),
                                encoding="utf-8", errors="replace")))
uids = meta["armA"] + meta["armB"]
ridx = meta["row_index"]
n_pos = 0
for u, i in zip(uids, ridx):
    r = rows[i]
    vals = [str(r.get(c, "")).strip() for c in COLS]
    if any(v not in ("", "0", "0.0", "False") for v in vals):
        n_pos += 1
print(f"50 条中**有 LLM 类标签**的：{n_pos} 条（其余为空——LLM 未给类，故无法比较）")
have = [(u, i) for u, i in zip(uids, ridx)
        if any(str(rows[i].get(c, "")).strip() not in ("", "0", "0.0", "False") for c in COLS)]
print("  有标签的编号：", [u for u, _i in have][:20])
# 冻结评测集里正例的类覆盖（0.8273 的评测面）
vt = list(csv.DictReader(open(os.path.join(HERE, "val_v3_test.csv"),
                              encoding="utf-8", errors="replace")))
cov = sum(1 for r in vt if str(r.get("sound_negative_llm", "")).strip() == "1"
          and any(str(r.get(c, "")).strip() not in ("", "0", "0.0", "False") for c in COLS))
pos = sum(1 for r in vt if str(r.get("sound_negative_llm", "")).strip() == "1")
print(f"val_v3_test 正例 {pos} 条中，带 LLM 类标签的 {cov} 条")
print("⇒ 归因指标（0.8273）的评测面 = **有 LLM 类标签的正例**，其规模远小于全部正例。")
json.dump({"with_llm_classes": len(have), "ids": [u for u, _i in have],
           "val_v3_test_pos_with_classes": cov, "val_v3_test_pos": pos},
          open(os.path.join(HERE, "v2", "attribution_llm_coverage.json"), "w",
               encoding="utf-8"), ensure_ascii=False, indent=2)
