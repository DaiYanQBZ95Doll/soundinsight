# -*- coding: utf-8 -*-
# 本脚本用于最终二分类训练：基于 LLM 清洗后的标签训练 DistilBERT，
# 80/20 分层划分、阈值调优，输出指标并保存到 sound_model。
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_recall_curve)
from sklearn.model_selection import train_test_split
from torch.optim import AdamW
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_llm.csv")
MODEL_DIR = os.path.join(HERE, "distilbert-base-uncased")
OUT_DIR = os.path.join(HERE, "sound_model")

EPOCHS = 3
BATCH_SIZE = 16
LR = 2e-5
MAX_LEN = 128
SEED = 42
OVERSAMPLE_RATIO = 0.2


def main() -> None:
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}")

    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    texts = df["text"].astype(str).tolist()
    labels = df["sound_negative_llm"].astype(int).tolist()
    print(f"rows: {len(df)} | positives: {sum(labels)} ({sum(labels) / len(labels):.2%})")

    X_tr, X_va, y_tr, y_va = train_test_split(
        texts, labels, test_size=0.2, random_state=SEED, stratify=labels)
    print(f"train: {len(X_tr)} (pos {sum(y_tr)}) | val: {len(X_va)} (pos {sum(y_va)})")

    rng = np.random.RandomState(SEED)
    pos = [i for i, y in enumerate(y_tr) if y == 1]
    neg = [i for i, y in enumerate(y_tr) if y == 0]
    n_target = max(len(pos), int(OVERSAMPLE_RATIO * len(neg) / (1 - OVERSAMPLE_RATIO)))
    extra = rng.choice(pos, size=n_target - len(pos))
    idx = neg + pos + extra.tolist()
    rng.shuffle(idx)
    X_tr = [X_tr[i] for i in idx]
    y_tr = [y_tr[i] for i in idx]
    print(f"train oversampled: {len(X_tr)} (pos ratio {sum(y_tr) / len(y_tr):.2%})")

    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_DIR, num_labels=2).to(device)
    optimizer = AdamW(model.parameters(), lr=LR)

    def run(phase, train=True):
        model.train(train)
        X, y = (X_tr, y_tr) if train else (X_va, y_va)
        order = np.arange(len(X))
        if train:
            rng.shuffle(order)
        total, probs, gold = 0.0, [], []
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
            total += float(out.loss)
            probs.extend(torch.softmax(out.logits, -1)[:, 1].tolist())
            gold.extend(yb.tolist())
        return total / (len(order) // BATCH_SIZE + 1), np.asarray(probs), np.asarray(gold)

    best_f1, best_state = -1.0, None
    for ep in range(1, EPOCHS + 1):
        t0 = time.time()
        loss, _, _ = run("train", True)
        _, va_p, va_g = run("val", False)
        acc = accuracy_score(va_g, (va_p >= 0.5).astype(int))
        f1a = f1_score(va_g, (va_p >= 0.5).astype(int), zero_division=0)
        precision, recall, thrs = precision_recall_curve(va_g, va_p)
        f1s = 2 * precision * recall / (precision + recall + 1e-12)
        i = int(np.argmax(f1s))
        fb, fb_thr = float(f1s[i]), float(thrs[i]) if i < len(thrs) else 0.5
        print(f"[epoch {ep}] loss={loss:.4f} acc={acc:.4f} f1@0.5={f1a:.4f} "
              f"f1_best={fb:.4f} @thr={fb_thr:.4f} | {time.time() - t0:.0f}s",
              flush=True)
        if f1a >= best_f1:
            best_f1 = f1a
            best_state = {k: v.detach().cpu().clone()
                          for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        _, va_p, va_g = run("val", False)
    pred = (va_p >= 0.5).astype(int)
    acc = accuracy_score(va_g, pred)
    f1a = f1_score(va_g, pred, zero_division=0)
    precision, recall, thrs = precision_recall_curve(va_g, va_p)
    f1s = 2 * precision * recall / (precision + recall + 1e-12)
    i = int(np.argmax(f1s))
    fb, fb_thr = float(f1s[i]), float(thrs[i]) if i < len(thrs) else 0.5
    cm = confusion_matrix(va_g, pred)
    print(f"FINAL acc={acc:.4f} f1@0.5={f1a:.4f} f1_best={fb:.4f} @thr={fb_thr:.4f}")
    print(f"confusion matrix: {cm.tolist()}")

    os.makedirs(OUT_DIR, exist_ok=True)
    model.save_pretrained(OUT_DIR)
    tok.save_pretrained(OUT_DIR)
    with open(os.path.join(OUT_DIR, "threshold.json"), "w", encoding="utf-8") as f:
        json.dump({"threshold": fb_thr}, f)
    print(f"saved -> {OUT_DIR}")


if __name__ == "__main__":
    main()
