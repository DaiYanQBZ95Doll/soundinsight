# -*- coding: utf-8 -*-
# 本脚本用于模型验证：在指定标签集上输出准确率、F1、阈值扫描与混淆矩阵。
"""Smoke test: evaluate saved sound_model on a held-out validation split."""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score, precision_score,
                             recall_score)
from sklearn.model_selection import train_test_split
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

BASE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--csv", type=str,
                default=os.path.join(BASE, "labeled_llm.csv"))
ap.add_argument("--label", type=str, default="sound_negative_llm")
args = ap.parse_args()

tok = DistilBertTokenizer.from_pretrained(os.path.join(BASE, "sound_model"))
model = DistilBertForSequenceClassification.from_pretrained(
    os.path.join(BASE, "sound_model"))
model.eval()
with open(os.path.join(BASE, "sound_model", "threshold.json"),
          encoding="utf-8") as f:
    THR = float(json.load(f)["threshold"])

df = pd.read_csv(args.csv)
texts = df["text"].astype(str).tolist()
labels = df[args.label].astype(int).tolist()
print(f"csv: {args.csv} | label: {args.label}")
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

print("\nConfusion matrix at tuned threshold:")
pred_tuned = (probs >= THR).astype(int)
cm = confusion_matrix(y_va, pred_tuned, labels=[0, 1])
print(cm)
print(f"  TN={cm[0, 0]} FP={cm[0, 1]} FN={cm[1, 0]} TP={cm[1, 1]}")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
fig, ax = plt.subplots(figsize=(5, 4.5))
im = ax.imshow(cm, cmap="Blues")
ax.set_xticks([0, 1])
ax.set_yticks([0, 1])
ax.set_xticklabels(["音质正常(预测)", "音质负面(预测)"])
ax.set_yticklabels(["音质正常(实际)", "音质负面(实际)"])
for i in range(2):
    for j in range(2):
        ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=18)
ax.set_title(f"验证集混淆矩阵 (阈值={THR:.2f})")
fig.colorbar(im, ax=ax)
fig.tight_layout()
cm_png = os.path.join(BASE, "confusion_matrix.png")
plt.savefig(cm_png, dpi=150)
print(f"saved {cm_png} (threshold={THR})")

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
