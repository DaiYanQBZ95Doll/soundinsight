# -*- coding: utf-8 -*-
"""量化"模型在四五星子集上的盲区"：同一批样本上，模型判正 vs LLM 复核的一致性。"""
from __future__ import annotations

import csv
import json
import os
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
MODEL = os.path.join(OUT, "model_maxlen256")
THR = json.load(open(os.path.join(OUT, "threshold.json"), encoding="utf-8"))["tuned"]

# LLM 复核结果
llm = {}
for line in open(os.path.join(OUT, "w4_review.jsonl"), encoding="utf-8", errors="replace"):
    try:
        r = json.loads(line)
    except ValueError:
        continue
    if "sound_negative" in r:
        llm[int(r["row_index"])] = int(r["sound_negative"])

rows = [r for r in csv.DictReader(open(os.path.join(OUT, "w4_candidates.csv"),
                                       encoding="utf-8", errors="replace"))
        if int(r["row_index"]) in llm]
print(f"样本 {len(rows)} 条（含 LLM 复核结果；来源=候选表按复核行号过滤）")
if not rows:
    print("[FAIL] 复核行号与候选表未匹配——检查 w4_review.jsonl 与 w4_candidates.csv 是否同批")
    raise SystemExit(1)

dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tok = DistilBertTokenizer.from_pretrained(MODEL)
model = DistilBertForSequenceClassification.from_pretrained(MODEL).to(dev).eval()
probs = predict(model, tok, [r["text"] for r in rows], 256, "truncate", 256, 64, dev)
pred = (np.array(probs) >= THR).astype(int)
y = np.array([llm[int(r["row_index"])] for r in rows])

tp = int(((pred == 1) & (y == 1)).sum())
fp = int(((pred == 1) & (y == 0)).sum())
fn = int(((pred == 0) & (y == 1)).sum())
tn = int(((pred == 0) & (y == 0)).sum())
print(f"阈值 {THR}｜模型 vs LLM：TP {tp}／FP {fp}／FN {fn}／TN {tn}")
print(f"  LLM 判正 {int(y.sum())} 条；模型判正 {int(pred.sum())} 条")
rec = tp / (tp + fn) * 100 if (tp + fn) else 0
prec = tp / (tp + fp) * 100 if (tp + fp) else 0
print(f"  → 模型在**这批真实正例**上的召回 **{rec:.1f}%**（{tp}/{tp+fn}），精确率 {prec:.1f}%")
print(f"  → 即：LLM 认定的音质差评中，有 **{fn} 条（{100-rec:.1f}%）模型判不出来**")

json.dump({"n": len(rows), "threshold": THR,
           "model_vs_llm": {"TP": tp, "FP": fp, "FN": fn, "TN": tn,
                            "llm_positives": int(y.sum()), "model_positives": int(pred.sum()),
                            "model_recall_on_llm_positives_pct": round(rec, 1),
                            "model_precision_pct": round(prec, 1)}},
          open(os.path.join(OUT, "model_vs_llm_on_w4_sample.json"), "w",
               encoding="utf-8"), ensure_ascii=False, indent=2)
print("[写出] v2/model_vs_llm_on_w4_sample.json")
