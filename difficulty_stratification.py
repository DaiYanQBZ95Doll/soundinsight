# -*- coding: utf-8 -*-
"""分层分析：模型在"规则可捞"与"只能靠开采"的正例上表现是否不同。

动机：v1 的叙事说"RLCA 把正例从 63 条扩到 1,280 条（20×）"。但**开采来的正例是否被模型学会了**？
若模型在"规则捞不到"的那部分上召回显著更低，说明：
  · 开采确实带来了规则与模型都难的样本（有价值，但也解释了模型的能力上限）；
  · 反之则说明开采只是把容易的样本变多了。

口径：用 `label_v3.py` 的一阶筛选词表（`SOUND_KEYWORDS`，23 词，词边界匹配）把
`val_v3_test` 的正例分为两组：
  · A 组「规则可捞」：文本含任一关键词（规则初筛就会把它送进 LLM 复核）；
  · B 组「只能靠开采」：不含任何关键词（**只能**通过三星/四五星补漏或 LLM 复核才发现）。
数据：`v2/w5_probs_test.csv`（v2 候选模型的缓存概率）+ `val_v3_test.csv`（标签与文本）。
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SOUND_KEYWORDS = [
    "sound", "audio", "bass", "treble", "clarity", "muffled", "distortion",
    "static", "hiss", "crisp", "muddy", "volume", "pitch", "frequency",
    "crackling", "popping", "sibilance", "tinny", "boomy", "hollow",
    "scratchy", "buzzing", "rattling",
]
RX = re.compile(r"\b(?:" + "|".join(map(re.escape, SOUND_KEYWORDS)) + r")\b", re.I)
THR = 0.6          # v2 调优档（与 w5_final 一致）


def prf(y, pred):
    tp = sum(1 for a, b in zip(y, pred) if a == 1 and b == 1)
    fp = sum(1 for a, b in zip(y, pred) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(y, pred) if a == 1 and b == 0)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"TP": tp, "FP": fp, "FN": fn, "P": round(p * 100, 1),
            "R": round(r * 100, 1), "F1": round(f, 4)}


def main() -> int:
    probs, labels, texts = [], [], []
    with open(os.path.join(HERE, "v2", "w5_probs_test.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            texts.append(r["text"])
            labels.append(int(r["label"]))
            probs.append(float(r["prob"]))
    if not probs:
        print("[等待] 缺少 v2/w5_probs_test.csv")
        return 0
    pred = [1 if p >= THR else 0 for p in probs]
    groups = {"A 规则可捞（含一阶关键词）": [], "B 只能靠开采（不含关键词）": []}
    for i, t in enumerate(texts):
        groups["A 规则可捞（含一阶关键词）" if RX.search(t) else "B 只能靠开采（不含关键词）"].append(i)

    print(f"val_v3_test：n={len(labels)}，正例 {sum(labels)}；阈值 {THR}")
    out = {}
    for name, idx in groups.items():
        y = [labels[i] for i in idx]
        pr = [pred[i] for i in idx]
        n_pos = sum(y)
        m = prf(y, pr)
        out[name] = {"n": len(idx), "pos": n_pos, **m}
        print(f"\n[{name}] n={len(idx)}（正例 {n_pos}，占全部正例 "
              f"{n_pos/max(sum(labels),1)*100:.1f}%）")
        print(f"    整体口径 P {m['P']}%／R {m['R']}%／F1 {m['F1']}")
        if n_pos:
            rec = sum(1 for a, b in zip(y, pr) if a == 1 and b == 1) / n_pos * 100
            print(f"    **正例召回 {rec:.1f}%**（{m['TP']}/{n_pos}）")

    a, b = out["A 规则可捞（含一阶关键词）"], out["B 只能靠开采（不含关键词）"]
    rec_a = a["TP"] / a["pos"] * 100 if a["pos"] else 0
    rec_b = b["TP"] / b["pos"] * 100 if b["pos"] else 0
    print(f"\n[对照] 正例召回：A 组 {rec_a:.1f}%（{a['TP']}/{a['pos']}） vs "
          f"B 组 {rec_b:.1f}%（{b['TP']}/{b['pos']}）→ 差 {rec_a-rec_b:+.1f}pp")

    md = [f"# 分层分析：模型在「规则可捞」与「只能靠开采」正例上的表现", "",
          f"> 数据：`val_v3_test`（n={len(labels)}，正例 {sum(labels)}）+ v2 候选模型缓存概率；阈值 **{THR}**（v2 调优档）。",
          f"> 分组：按 `label_v3.py` 的一阶筛选词表（23 词，词边界）是否命中。", "",
          "| 组 | 样本 n | 正例数 | 占全部正例 | 正例召回 | P | R | F1 |",
          "|---|---|---|---|---|---|---|---|"]
    for name, d in out.items():
        rec = d["TP"] / d["pos"] * 100 if d["pos"] else 0
        md.append(f"| {name} | {d['n']} | {d['pos']} | "
                  f"{d['pos']/max(sum(labels),1)*100:.1f}% | **{rec:.1f}%** | "
                  f"{d['P']}% | {d['R']}% | {d['F1']} |")
    md += ["", "## 读法（这一页回答什么问题）", "",
           f"1. **A 组（规则可捞）**是规则初筛就能送进复核的正例，模型召回 **{rec_a:.1f}%**；",
           f"2. **B 组（只能靠开采）**是规则**一个字都捞不到**的正例（如全部用委婉表达），"
           f"模型召回 **{rec_b:.1f}%** —— 两组差 **{rec_a-rec_b:+.1f}pp**；",
           "3. 若 B 组召回明显更低：说明**开采带来的正是规则与模型都难的样本**——"
           "它既解释了模型的能力上限，也说明开采做的是「补盲区」而不是「凑数」；",
           "4. 若两组接近：说明模型学到的是语义而非关键词，开采主要扩大了覆盖面。",
           "",
           "## 边界", "",
           "- 分组是**代理**（用一阶关键词近似「规则能否捞到」），真实管线还含 LLM 复核环节；",
           "- 样本量有限（B 组正例较少），百分比差异需按二项波动解读，不做过强结论。"]
    open(os.path.join(HERE, "docs", "difficulty_stratification.md"), "w",
         encoding="utf-8", newline="\n").write("\n".join(md) + "\n")
    json.dump({"threshold": THR, "groups": out,
               "recall_gap_pp": round(rec_a - rec_b, 1), "gen": "[v2]"},
              open(os.path.join(HERE, "difficulty_stratification.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[写出] docs/difficulty_stratification.md / .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
