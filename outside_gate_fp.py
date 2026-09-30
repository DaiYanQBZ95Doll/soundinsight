# -*- coding: utf-8 -*-
"""闸门外（不含一阶关键词）评论的模型判正率测量。

为什么测这个：
- 上一轮发现「评测集继承关键词闸门」——`val_v3_test` 的 8,687 条**闸门外**评论标签全为 0，
  且**闸门外的真阳性率从未测量**（因为标签管线本身就把它们排除了）。
- 本测量给出**可定义、可复算**的替代量：**模型在这批"闸门外"评论上的判正率**。
  由于这批行的标签全为 0，判正即误报 → 该比率就是「**闸门外误报率**」；
  同时它回答一个产品决策问题：**若把闸门从"关键词"改为"模型直判"，会新增多少被判正的评论**
  （新增量 ≈ 该比率 × 闸门外语料量）。

口径：模型 = v2 候选（`v2/model_maxlen256`），阈值 = v2 调优档（0.6）；
      闸门 = `label_v3.py` 的一阶筛选词表（23 词，词边界）；数据 = `val_v3_test`（n=10,000）。

输出：控制台 + `v2/outside_gate_fp.json` + `docs/outside_gate_fp.md`
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import sys

import numpy as np
import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_w1_longtext import predict  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v2")
TEST = os.path.join(HERE, "val_v3_test.csv")
MODEL = os.path.join(OUT, "model_maxlen256")
THR = 0.6
MAX_LEN = 256
SOUND_KEYWORDS = [
    "sound", "audio", "bass", "treble", "clarity", "muffled", "distortion",
    "static", "hiss", "crisp", "muddy", "volume", "pitch", "frequency",
    "crackling", "popping", "sibilance", "tinny", "boomy", "hollow",
    "scratchy", "buzzing", "rattling",
]
RX = re.compile(r"\b(?:" + "|".join(map(re.escape, SOUND_KEYWORDS)) + r")\b", re.I)


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - r) / d), min(1.0, (c + r) / d)


def main() -> int:
    texts, labels, probs = [], [], []
    with open(os.path.join(OUT, "w5_probs_test.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            texts.append(r["text"])
            labels.append(int(r["label"]))
            probs.append(float(r["prob"]))
    inside = [i for i, t in enumerate(texts) if RX.search(t)]
    outside = [i for i, t in enumerate(texts) if not RX.search(t)]
    print(f"val_v3_test n={len(texts)}：闸门内 {len(inside)}（{len(inside)/len(texts)*100:.1f}%）、"
          f"闸门外 {len(outside)}（{len(outside)/len(texts)*100:.1f}%）")

    # 闸门外：模型直判（该批标签全为 0 → 判正即误报）
    texts_out = [texts[i] for i in outside]
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = DistilBertTokenizer.from_pretrained(MODEL)
    model = DistilBertForSequenceClassification.from_pretrained(MODEL).to(dev).eval()
    print(f"模型 {os.path.relpath(MODEL, HERE)}｜阈值 {THR}｜device {dev}｜"
          f"对闸门外 {len(texts_out)} 条做推理…")
    p_out = np.array(predict(model, tok, texts_out, MAX_LEN, "truncate", MAX_LEN, 64, dev))
    flag = (p_out >= THR).astype(int)
    k, n = int(flag.sum()), len(flag)
    lo, hi = wilson(k, n)
    print(f"\n[闸门外] 模型判正 {k}/{n} = {k/n*100:.2f}%（Wilson 95% CI {lo*100:.2f}–{hi*100:.2f}%）"
          f"　← 该批标签全为 0，故即**闸门外误报率**")

    # 闸门内对照（同一口径）
    p_in = np.array([probs[i] for i in inside])
    y_in = np.array([labels[i] for i in inside])
    fin = (p_in >= THR).astype(int)
    fp_in = int(((fin == 1) & (y_in == 0)).sum())
    n_in_neg = int((y_in == 0).sum())
    print(f"[闸门内] 误报 {fp_in}/{n_in_neg} = {fp_in/n_in_neg*100:.2f}%（对照）")

    # 产品含义：闸门若改为模型直判，新增判正量（按语料比例外推）+ 精确率对照
    corpus = 100000
    outside_share = len(outside) / len(texts)
    est_new = k / n * corpus * outside_share
    est_new_lo, est_new_hi = lo * corpus * outside_share, hi * corpus * outside_share
    # 精确率对照（在 val_v3_test 上直接算，不靠外推）：
    #   有闸门：判正 = 闸门内 TP+FP；无闸门：再并入闸门外判正（全为 FP）
    tp_in = int(((fin == 1) & (y_in == 1)).sum())
    flagged_with_gate = tp_in + fp_in
    flagged_without = flagged_with_gate + k
    prec_gate = tp_in / flagged_with_gate * 100 if flagged_with_gate else 0
    prec_nogate = tp_in / flagged_without * 100 if flagged_without else 0
    print(f"\n[产品含义] 若把闸门改为**模型直判**：在闸门外语料（≈{corpus*outside_share:,.0f} 条）上"
          f"预计新增判正 ≈ **{est_new:,.0f}** 条（95% CI {est_new_lo:,.0f}–{est_new_hi:,.0f}）")
    print(f"           精确率对照（val_v3_test 直接算）：**有闸门 {prec_gate:.1f}%**"
          f"（TP {tp_in}／判正 {flagged_with_gate}）→ **去闸门 {prec_nogate:.1f}%**"
          f"（再并入 {k} 条闸门外误报）；召回不变（闸门外无正例标签）")

    json.dump({"model": "v2/model_maxlen256", "threshold": THR, "gen": "[v2]",
               "inside": {"n": len(inside), "share": round(len(inside)/len(texts), 4),
                          "fp": fp_in, "fp_rate": round(fp_in/n_in_neg, 4)},
               "outside": {"n": n, "share": round(outside_share, 4), "flagged": k,
                           "fp_rate": round(k/n, 4), "wilson95": [round(lo, 4), round(hi, 4)]},
               "gate_removal_estimate": {"new_flags": round(est_new, 0),
                                         "ci95": [round(est_new_lo, 0), round(est_new_hi, 0)],
                                         "precision_with_gate_pct": round(prec_gate, 1),
                                         "precision_without_gate_pct": round(prec_nogate, 1),
                                         "note": "新增判正全部为误报（闸门外无正例标签）；召回不变"}},
              open(os.path.join(OUT, "outside_gate_fp.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    md = [f"# 闸门外评论的模型判正率（覆盖盲区的定量化）", "",
          f"> 模型 `v2/model_maxlen256`｜阈值 **{THR}**｜数据 `val_v3_test`（n={len(texts)}）",
          f"> 闸门定义：`label_v3.py` 一阶筛选词表（23 词，词边界）", "",
          "## 一、结果", "",
          "| 分组 | 条数 | 占语料 | 模型判正 | 比率 | Wilson 95% CI | 性质 |",
          "|---|---|---|---|---|---|---|",
          f"| **闸门内**（含关键词） | {len(inside)} | {len(inside)/len(texts)*100:.1f}% | "
          f"— | 误报 {fp_in/n_in_neg*100:.2f}% | — | 有标签，可评估 |",
          f"| **闸门外**（不含关键词） | {n} | {outside_share*100:.1f}% | **{k}** | "
          f"**{k/n*100:.2f}%** | {lo*100:.2f}–{hi*100:.2f}% | 标签全为 0 → 判正即误报 |",
          "",
          "## 二、它回答了什么", "",
          f"1. **闸门外的模型判正率只有 {k/n*100:.2f}%**（{k}/{n}，Wilson 95% CI "
          f"{lo*100:.2f}–{hi*100:.2f}%）——模型对「不含音质关键词」的评论**基本不判负**"
          f"（对照：闸门内误报率 {fp_in/n_in_neg*100:.2f}%）；",
          f"2. **若把闸门从关键词改为模型直判**：预计新增判正 ≈ **{est_new:,.0f}** 条"
          f"（95% CI {est_new_lo:,.0f}–{est_new_hi:,.0f}），且**全部为误报**（该批无正例标签）、"
          f"**召回不变**；精确率在 `val_v3_test` 上由 **{prec_gate:.1f}%** 变为 "
          f"**{prec_nogate:.1f}%**（TP {tp_in}，判正 {flagged_with_gate}→{flagged_without}）"
          f"→ 代价很小但收益也为零（没有证据表明闸门外有正例被找回），**本轮不建议去闸门**；",
          "3. **这仍然不等于「闸门外没有真阳性」**：本测量用的是**在闸门内数据上训练**的模型，"
          "它在闸门外的行为属**分布外推断**；只有 LLM 复核（无关键词抽样）才能定论。",
          "",
          "## 三、边界（必读）", "",
          "- 闸门外的 8,687 条在本项目标签体系内**全为负例**（因为标签管线不标注它们），"
          "因此本页的「判正」只能解释为误报，**不能**推断出「闸门外真阳性率」；",
          "- 模型在分布外（无关键词文本）的校准未知，故比率只作**量级参考**；",
          "- 结论**不外推**到其它语料或其它阈值。"]
    open(os.path.join(HERE, "docs", "outside_gate_fp.md"), "w",
         encoding="utf-8", newline="\n").write("\n".join(md) + "\n")
    print("[写出] v2/outside_gate_fp.json、docs/outside_gate_fp.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
