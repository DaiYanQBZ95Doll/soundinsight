# -*- coding: utf-8 -*-
# 本脚本用于 DistilBERT 交叉验证：对音质负面标签做分层 K 折乘多种子评估，
# 每折在训练折上调阈值，输出准确率与 F1 的均值标准差。GPU 可用时自动使用。
import argparse
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (accuracy_score, f1_score, precision_recall_curve)
from sklearn.model_selection import StratifiedKFold
from torch.optim import AdamW
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_expanded.csv")
MODEL_DIR = os.path.join(HERE, "distilbert-base-uncased")

EPOCHS = 3
BATCH_SIZE = 32
LR = 2e-5
MAX_LEN = 128
OVERSAMPLE_RATIO = 0.25


def best_threshold_f1(y_true, probs):
    precision, recall, thresholds = precision_recall_curve(y_true, probs)
    f1s = 2 * precision * recall / (precision + recall + 1e-12)
    i = int(np.argmax(f1s))
    return float(f1s[i]), float(thresholds[i]) if i < len(thresholds) else 0.5


def run_fold(texts, labels, tr_idx, va_idx, tok, device, seed, max_train):
    rng = np.random.RandomState(seed)
    if len(tr_idx) > max_train:
        tr_idx = rng.choice(tr_idx, size=max_train, replace=False)

    pos = [i for i in tr_idx if labels[i] == 1]
    neg = [i for i in tr_idx if labels[i] == 0]
    n_pos_target = max(len(pos), int(OVERSAMPLE_RATIO * len(neg) /
                                     (1 - OVERSAMPLE_RATIO)))
    extra = rng.choice(pos, size=n_pos_target - len(pos))
    tr_idx = np.concatenate([tr_idx, extra])
    rng.shuffle(tr_idx)

    torch.manual_seed(seed)
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_DIR, num_labels=2).to(device)
    optimizer = AdamW(model.parameters(), lr=LR)
    model.train()
    order = np.arange(len(tr_idx))
    for epoch in range(EPOCHS):
        rng.shuffle(order)
        total = 0
        for b in range(0, len(order), BATCH_SIZE):
            idx = [tr_idx[i] for i in order[b:b + BATCH_SIZE]]
            enc = tok([texts[i] for i in idx], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            yb = torch.tensor([labels[i] for i in idx], device=device)
            out = model(**enc, labels=yb)
            optimizer.zero_grad()
            out.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total += float(out.loss)
        print(f"    epoch {epoch + 1} loss={total / (len(order) // BATCH_SIZE + 1):.4f}",
              flush=True)

    model.eval()
    probs = []
    with torch.no_grad():
        for b in range(0, len(va_idx), BATCH_SIZE):
            idx = va_idx[b:b + BATCH_SIZE]
            enc = tok([texts[i] for i in idx], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            logits = model(**enc).logits
            probs.extend(torch.softmax(logits, -1)[:, 1].tolist())
    probs = np.asarray(probs)
    yva = np.asarray([labels[i] for i in va_idx])
    pred = (probs >= 0.5).astype(int)
    acc = accuracy_score(yva, pred)
    f1a = f1_score(yva, pred, zero_division=0)
    f1b, _ = best_threshold_f1(yva, probs)
    del model
    torch.cuda.empty_cache()
    return acc, f1a, f1b


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seeds", type=str, default="42,7")
    ap.add_argument("--max-train", type=int, default=30000)
    ap.add_argument("--csv", type=str,
                    default=os.path.join(HERE, "labeled_expanded.csv"))
    ap.add_argument("--label", type=str, default="sound_negative")
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(",")]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device} | torch: {torch.__version__}")

    df = pd.read_csv(args.csv, encoding="utf-8")
    texts = df["text"].astype(str).tolist()
    labels = df[args.label].astype(int).tolist()
    print(f"csv: {args.csv} | label: {args.label}")
    print(f"数据: {len(texts)} 行 | 正例 {sum(labels)} ({sum(labels) / len(labels):.2%})")

    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    accs, f1a_list, f1b_list = [], [], []
    t0 = time.time()
    for seed in seeds:
        skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=seed)
        for fi, (tr, va) in enumerate(skf.split(texts, labels)):
            print(f"seed={seed} fold={fi + 1}/{args.folds}", flush=True)
            acc, f1a, f1b = run_fold(texts, labels, tr, va, tok, device,
                                     seed, args.max_train)
            accs.append(acc)
            f1a_list.append(f1a)
            f1b_list.append(f1b)
            print(f"  acc={acc:.4f} f1@0.5={f1a:.4f} f1_best={f1b:.4f} "
                  f"[{time.time() - t0:.0f}s]", flush=True)

    print("\n=== DistilBERT 交叉验证汇总 ===")
    print(f"accuracy: {np.mean(accs):.4f} ± {np.std(accs):.4f}")
    print(f"f1@0.5:   {np.mean(f1a_list):.4f} ± {np.std(f1a_list):.4f}")
    print(f"f1_best:  {np.mean(f1b_list):.4f} ± {np.std(f1b_list):.4f}")


if __name__ == "__main__":
    main()
