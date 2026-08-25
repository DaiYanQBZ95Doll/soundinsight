# -*- coding: utf-8 -*-
# 本脚本用于模型验证：在验证集上输出准确率、F1 与阈值扫描结果，并给出示例预测。
"""Smoke test: evaluate saved sound_model on the held-out validation split."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (accuracy_score, classification_report,
                             f1_score, precision_score, recall_score)
from sklearn.model_selection import train_test_split
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

BASE = os.path.dirname(os.path.abspath(__file__))
tok = DistilBertTokenizer.from_pretrained(os.path.join(BASE, "sound_model"))
model = DistilBertForSequenceClassification.from_pretrained(
    os.path.join(BASE, "sound_model"))
model.eval()
with open(os.path.join(BASE, "sound_model", "threshold.json"),
          encoding="utf-8") as f:
    THR = float(json.load(f)["threshold"])

df = pd.read_csv(os.path.join(BASE, "labeled_data_final.csv"))
texts = df["text"].astype(str).tolist()
labels = df["sound_negative"].astype(int).tolist()
_, X_va, _, y_va = train_test_split(texts, labels, test_size=0.2,
                                    random_state=42, stratify=labels)

probs = []
for i in range(0, len(X_va), 32):
    enc = tok(X_va[i:i + 32], padding=True, truncation=True, max_length=128,
              return_tensors="pt")
    with torch.no_grad():
        probs.extend(torch.softmax(model(**enc).logits, -1)[:, 1].tolist())
probs = np.asarray(probs)
print(f"val n={len(y_va)} pos={sum(y_va)}")
print("\nthreshold sweep on validation set:")
print(f"{'thr':>6} {'acc':>7} {'prec':>7} {'rec':>7} {'f1':>7} {'pred_pos':>8}")
for thr in [0.5, 0.2, 0.1, 0.05, 0.01, 0.001]:
    pred = (probs >= thr).astype(int)
    print(f"{thr:>6.3f} {accuracy_score(y_va, pred):>7.4f} "
          f"{precision_score(y_va, pred, zero_division=0):>7.4f} "
          f"{recall_score(y_va, pred, zero_division=0):>7.4f} "
          f"{f1_score(y_va, pred, zero_division=0):>7.4f} "
          f"{int(pred.sum()):>8}")

print("\nSample predictions on real reviews:")
for text in [
    "The sound quality is terrible, the bass is muddy and there is constant "
    "static.",
    "Great battery life and very comfortable fit.",
    "Sounds crackle and hiss constantly, completely unusable.",
]:
    enc = tok(text, padding=True, truncation=True, max_length=128,
              return_tensors="pt")
    with torch.no_grad():
        p = float(torch.softmax(model(**enc).logits, -1)[0, 1])
    print(f"  [{p:.1%}] {text[:70]}")
