# -*- coding: utf-8 -*-
# 本脚本用于教师模型一致性对比：把 LLM 复核标签当作教师标准答案，
# 在复核样本上 80/20 划分，训练 DistilBERT 并在测试集上衡量其与教师答案的一致率。
import os
import sys

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from torch.optim import AdamW
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
LABELED = os.path.join(HERE, "labeled_llm.csv")
MODEL_DIR = os.path.join(HERE, "distilbert-base-uncased")

EPOCHS = 4
BATCH_SIZE = 16
LR = 2e-5
MAX_LEN = 128
SEED = 42


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    df = pd.read_csv(LABELED, encoding="utf-8")
    reviewed = df[df["sound_negative_llm"] != 0]  # LLM 确认为正例的样本
    pos_texts = reviewed["text"].astype(str).tolist()
    pos_labels = reviewed["sound_negative_llm"].astype(int).tolist()
    # 补入等量 LLM 未确认（规则误报）样本作为负例，标签为 0
    neg_mask = (df["sound_related"] == 1) & (df["rating"] <= 2) & \
        (df["sound_negative_llm"] == 0)
    neg_pool = df[neg_mask]
    n_neg = min(len(pos_texts), len(neg_pool))
    neg_df = neg_pool.sample(n=n_neg, random_state=SEED)
    texts = pos_texts[:n_neg] + neg_df["text"].astype(str).tolist()
    labels = [1] * n_neg + [0] * n_neg
    print(f"对比集: {len(texts)} (pos {sum(labels)}) | teacher=LLM 复核标签")

    X_tr, X_va, y_tr, y_va = train_test_split(
        texts, labels, test_size=0.2, random_state=SEED, stratify=labels)

    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_DIR, num_labels=2).to(device)
    optimizer = AdamW(model.parameters(), lr=LR)

    def run(X, y, train=True):
        model.train(train)
        order = np.arange(len(X))
        if train:
            np.random.shuffle(order)
        probs = []
        for b in range(0, len(order), BATCH_SIZE):
            ids = [order[j] for j in range(b, min(b + BATCH_SIZE, len(order)))]
            enc = tok([X[i] for i in ids], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            yb = torch.tensor([y[i] for i in ids], device=device)
            out = model(**enc, labels=yb)
            if train:
                optimizer.zero_grad()
                out.loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            probs.extend(torch.softmax(out.logits, -1)[:, 1].tolist())
        return np.asarray(probs)

    for ep in range(EPOCHS):
        run(X_tr, y_tr, True)
    va_p = run(X_va, y_va, False)
    pred = (va_p >= 0.5).astype(int)
    acc = accuracy_score(y_va, pred)
    f1 = f1_score(y_va, pred, zero_division=0)
    print(f"与教师答案一致率(acc)={acc:.4f} | f1={f1:.4f}")
    print(f"平均预测概率: 正例 {va_p[np.asarray(y_va) == 1].mean():.3f} | "
          f"负例 {va_p[np.asarray(y_va) == 0].mean():.3f}")


if __name__ == "__main__":
    main()
