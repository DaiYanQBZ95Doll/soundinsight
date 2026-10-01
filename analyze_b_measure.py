# -*- coding: utf-8 -*-
"""B-测量结果分析：长文本桶与高音桶的 LLM 判正产出、执行方（AI）分类、以及对预注册判定的含义。

纪律：分类主体＝执行方（AI），**未经人工复核**；所有 LLM 率一律标「LLM 口径，未经人工校准」。
"""
from __future__ import annotations

import collections
import csv
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = "v2"


def load(layer):
    recs = []
    p = os.path.join(OUT, f"review_{layer}.jsonl")
    for line in open(p, encoding="utf-8", errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if "sound_negative" in r:
            recs.append(r)
    return recs


def corpus_texts():
    texts = {}
    with open("labeled_llm.csv", encoding="utf-8", errors="replace") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            texts[i] = str(r.get("text") or "")
    return texts


texts = corpus_texts()
result = {}
for layer in ("longtext", "treble"):
    recs = load(layer)
    pos = [r for r in recs if int(r["sound_negative"]) == 1]
    cls = collections.Counter()
    for r in pos:
        for c in (r.get("classes") or []):
            cls[c] += 1
    words = [r.get("words", 0) for r in recs]
    result[layer] = {"reviewed": len(recs), "positives": len(pos),
                     "rate": round(len(pos) / max(len(recs), 1), 4),
                     "class_dist": dict(cls),
                     "median_words": sorted(words)[len(words) // 2] if words else 0}
    print(f"=== {layer} ===")
    print(f"  复核 {len(recs):,} 条｜LLM 判正 {len(pos):,}"
          f"（{len(pos)/max(len(recs),1)*100:.2f}%）｜中位词数 {result[layer]['median_words']}")
    print(f"  类别分布（判正条目）：{dict(cls.most_common())}")
    print("  判正样例（前 6 条，供人工/AI 分类判据参考）：")
    for r in pos[:6]:
        t = texts.get(int(r["row_index"]), "").replace("\n", " ")
        print(f"    [{r['row_index']}] {str(r.get('why'))[:60]}")
        print(f"        {t[:170]}")

# ---- 对预注册判定的含义 ----
print("\n=== 对预注册判定线的含义 ===")
lt = result["longtext"]
print(f"  长文本桶：LLM 判正 {lt['positives']:,} 条 → 这批**候选新增正例**"
      f"（其中相当比例为跨品类，需分类过滤）")
print(f"  高音桶：LLM 判正 {result['treble']['positives']:,} 条 → 高音类候选补充")
print("  说明：判定线（长文本召回 ≥72%／高音 F1 ≥0.62）需**并入重训后**才能测量；")
print("        本页只给出候选产出，不构成达标结论。")

json.dump({"longtext": result["longtext"], "treble": result["treble"],
           "note": "LLM 口径，未经人工校准；分类主体为执行方（AI）",
           "cost": {"treble_usd": 0.1365, "longtext_usd": 1.2731,
                    "total_usd": round(0.1365 + 1.2731, 4),
                    "unit_usd_per_1k": 0.14}},
          open(os.path.join(OUT, "b_measure_results.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\n[写出] v2/b_measure_results.json")
