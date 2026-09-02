# -*- coding: utf-8 -*-
# 本脚本用于 PR 曲线：最终模型在 val_v2 上输出概率，计算 AUC-PR 并保存 pr_curve.png。
import json
import os
import sys

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, precision_recall_curve
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "sound_model")
VAL_CSV = os.path.join(HERE, "val_v2.csv")
OUT_PNG = os.path.join(HERE, "pr_curve.png")

with open(os.path.join(MODEL_DIR, "threshold.json"), encoding="utf-8") as f:
    THR = float(json.load(f)["threshold"])


def main() -> None:
    device = torch.device("cpu")  # 让出 GPU 给学习曲线任务
    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(MODEL_DIR)
    model.eval()

    va = pd.read_csv(VAL_CSV, encoding="utf-8")
    X_va = va["text"].astype(str).tolist()
    y_va = np.asarray(va["sound_negative"].astype(int))

    probs = []
    with torch.no_grad():
        for b in range(0, len(X_va), 64):
            enc = tok(X_va[b:b + 64], padding=True, truncation=True,
                      max_length=128, return_tensors="pt")
            probs.append(torch.softmax(model(**enc).logits, -1)
                         [:, 1].numpy())
    probs = np.concatenate(probs)
    auc = float(average_precision_score(y_va, probs))
    precision, recall, _ = precision_recall_curve(y_va, probs)

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(recall, precision, color="#c0392b", linewidth=2)
    ax.fill_between(recall, precision, alpha=0.15, color="#c0392b")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title(f"PR 曲线（val_v2，AUC-PR = {auc:.4f}）")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    plt.savefig(OUT_PNG, dpi=150)
    print(f"AUC-PR = {auc:.4f}")
    print(f"保存 -> {OUT_PNG}")


if __name__ == "__main__":
    main()
