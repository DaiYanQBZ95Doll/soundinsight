# -*- coding: utf-8 -*-
"""生成"偏向探针"（bias probe）：随机子集 + **只给原文**（无翻译、无解析）的重判卡。
用途：与你在完整答题卡上的判定对比，**量化"我的翻译与解析对你的判读影响了多少"**。
设计：确定性随机（固定种子），子集与条件写入 v2/bias_probe_ids.json，可复现。
"""
import csv
import hashlib
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GDIR = os.path.join(HERE, "docs", "gold_set")
N_DEFAULT = 40
SEED = 20261002

rows = list(csv.DictReader(open(os.path.join(GDIR, "assisted_worksheet.csv"),
                                encoding="utf-8-sig", errors="replace")))
rnd = random.Random(SEED)
probe = rnd.sample(rows, min(N_DEFAULT, len(rows)))
ids = [r["编号"] for r in probe]
json.dump({"seed": SEED, "n": len(ids), "ids": ids,
           "condition": "原文 only（无翻译、无解析）",
           "purpose": "量化执行方提供的翻译/解析对决策方判读的锚定影响"},
          open(os.path.join(HERE, "v2", "bias_probe_ids.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

out = ["# 偏向探针 · 重判卡（**只给原文**）", "",
       f"> 共 {len(ids)} 条（固定种子 {SEED} 随机抽取，可复现）｜生成 `make_bias_probe.py`", "",
       "> **为什么有这张卡**：完整答题卡里含执行方给的**翻译与解析**；其中「声音」一栏与判据"
       "（是否在说音质）高度相关，可能**锚定**你的判读。",
       "> 本卡**只给英文原文**——请**只依据原文**再判一次（不看翻译、不看解析）。",
       "> 两卡对比即可量化：**我的材料把你的判读推动了多少、往哪个方向推**。", "",
       "> 编码：**1 = 是**（在说耳机/耳塞/头戴的音质）｜**0 = 不是**｜**2 = 无法判断**", ""]
for i, r in enumerate(probe, 1):
    out += [f"## {r['编号']}　P{i:02d}", "", f"**原文**：{r['原文']}", "",
            "**重判（只看原文）**：`___`", ""]
out += ["---", "",
        "> 填完这条与主卡后：`python score_bias_probe.py`（对比两次判定的逐条差异与 κ）"]
open(os.path.join(GDIR, "bias_probe_sheet.md"), "w", encoding="utf-8", newline="\n").write(
    "\n".join(out) + "\n")
print(f"  [写出] docs/gold_set/bias_probe_sheet.md（{len(ids)} 条，只给原文）")
print(f"  [写出] v2/bias_probe_ids.json（种子 {SEED}）")
print(f"  说明：抽取集合 = {', '.join(ids[:8])} …")
