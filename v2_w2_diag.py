# -*- coding: utf-8 -*-
"""诊断：冻结多标签模型在 val_v3_test 上的逐类概率分布与预测数。"""
import csv
import sys

import numpy as np
import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ISSUES = ("issue_bass_llm", "issue_clarity_llm", "issue_noise_llm",
          "issue_volume_llm", "issue_treble_llm")
NAMES = ("低音", "清晰度", "杂音", "音量", "高音")

texts, Y = [], []
with open("val_v3_test.csv", encoding="utf-8", errors="replace") as fh:
    for row in csv.DictReader(fh):
        texts.append(str(row["text"]))
        Y.append([int(float(row.get(c) or 0)) for c in ISSUES])
Y = np.array(Y)
print(f"test n={len(texts)}；各类正例 {Y.sum(axis=0).tolist()}")

tok = DistilBertTokenizer.from_pretrained("multi_label_model")
model = DistilBertForSequenceClassification.from_pretrained(
    "multi_label_model").eval()
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(dev)
P = []
with torch.no_grad():
    for i in range(0, len(texts), 64):
        enc = tok(texts[i:i + 64], truncation=True, max_length=128,
                  padding=True, return_tensors="pt").to(dev)
        P.append(torch.sigmoid(model(**enc).logits).cpu().numpy())
P = np.vstack(P)

print("\n类别     标签正例  概率均值  概率P95  概率最大  >0.5 的条数  >0.3 的条数")
for j, n in enumerate(NAMES):
    col = P[:, j]
    print(f"{n:<8} {Y[:, j].sum():>7}  {col.mean():>8.4f}  "
          f"{np.percentile(col, 95):>7.4f}  {col.max():>8.4f}  "
          f"{(col > 0.5).sum():>11}  {(col > 0.3).sum():>11}")

# 正例上的概率（模型是否给正例高分）
print("\n正例样本上的平均概率（若远低于 0.5，说明模型与当前标签不匹配）：")
for j, n in enumerate(NAMES):
    pos = Y[:, j] == 1
    if pos.sum() == 0:
        continue
    print(f"  {n:<6} 正例 {pos.sum():>3} 条，平均概率 {P[pos, j].mean():.4f}，"
          f"最高 {P[pos, j].max():.4f}，>0.5 的比例 {(P[pos, j] > 0.5).mean() * 100:.1f}%")
