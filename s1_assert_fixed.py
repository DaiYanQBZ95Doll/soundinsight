# -*- coding: utf-8 -*-
"""修正的机械断言：文本可能**多处出现**（语料有 5,223 行重复），故判据必须是
「val_v3_test 每行的**全部**出现都在训练侧」才算真重叠；只要有一处落在留出侧，
即与该行的来源一致（不构成污染证据）。

输出三分类：真重叠（全部出现∈训练侧）／含留出出现（一致）／语料中找不到（异常）。
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))


def norm(t):
    return re.sub(r"\s+", " ", str(t).replace("\u3000", " ")).strip()


def h(t):
    return hashlib.sha256(norm(t).encode("utf-8", "replace")).hexdigest()


texts, labels = [], []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
        labels.append(int(float(r.get("sound_negative_llm") or 0)))
from sklearn.model_selection import train_test_split  # noqa: E402
tr, va = train_test_split(list(range(len(labels))), test_size=0.2, random_state=42,
                          stratify=labels)
train_set, hold_set = set(tr), set(va)
occ = {}
for i, t in enumerate(texts):
    occ.setdefault(h(t), []).append(i)

out = {}
for name in ("val_v3_test", "val_v3_tune"):
    rows = list(csv.DictReader(open(os.path.join(HERE, name + ".csv"),
                                   encoding="utf-8", errors="replace")))
    real_overlap, consistent, missing = [], 0, 0
    for r in rows:
        ids = occ.get(h(r.get("text") or ""))
        if not ids:
            missing += 1
        elif all(i in train_set for i in ids):
            real_overlap.append(ids)
        else:
            consistent += 1
    out[name] = {"rows": len(rows), "real_overlap": len(real_overlap),
                 "consistent_with_holdout": consistent, "not_found": missing,
                 "sample_overlap_text": [texts[i[0]][:90] for i in real_overlap[:3]]}
    print(f"{name}: {len(rows):,} 行｜**真重叠（全部出现∈训练侧）{len(real_overlap)}**｜"
          f"含留出出现 {consistent:,}｜语料中找不到 {missing}")
    for t in out[name]["sample_overlap_text"]:
        print(f"    · {t!r}")

ok = all(v["real_overlap"] == 0 for v in out.values())
print(f"\n修正后断言（真重叠 = 0）：**{'通过 ✓' if ok else '未通过 ✗'}**")
json.dump(out, open(os.path.join(HERE, "v2", "v3lite_assertion_fixed.json"), "w",
                    encoding="utf-8"), ensure_ascii=False, indent=2)
print("[写出] v2/v3lite_assertion_fixed.json")
