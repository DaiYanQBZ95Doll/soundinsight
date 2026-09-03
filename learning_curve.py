# -*- coding: utf-8 -*-
# 本脚本用于学习曲线：不同正例数量下训练 DistilBERT，固定验证集 val_v2 评估，
# 每个数据量跑两次取平均，绘制 F1@0.5 学习曲线保存为 learning_curve.png。
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from torch.optim import AdamW
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "distilbert-base-uncased")
INPUT_CSV = os.path.join(HERE, "labeled_llm.csv")
VAL_CSV = os.path.join(HERE, "val_v2.csv")
OUT_PNG = os.path.join(HERE, "learning_curve.png")

POS_COUNTS = [100, 300, 500, 800, 1000, 1257]
RUN_SEEDS = [42, 7]
EPOCHS = 3
BATCH_SIZE = 16
LR = 2e-5
MAX_LEN = 128
NEG_RATIO = 10
# 训练池使用高音补捞前的标签集（1257 正例口径），与 val_v2 同源同划分，
# 保证训练池正例恰为 1006 条且与验证集零重叠
INPUT_CSV = os.path.join(HERE, "labeled_llm_before_treble.csv")
RESULTS_JSON = os.path.join(HERE, "learning_curve_results.json")


def evaluate(model, tok, X, y, device):
    model.eval()
    probs = []
    with torch.no_grad():
        for b in range(0, len(X), 32):
            enc = tok(X[b:b + 32], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            probs.append(torch.softmax(model(**enc).logits, -1)
                         [:, 1].cpu().numpy())
    probs = np.concatenate(probs)
    pred = (probs >= 0.5).astype(int)
    return f1_score(y, pred, zero_division=0)


def train_once(X, y, seed, device):
    torch.manual_seed(seed)
    np.random.seed(seed)
    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_DIR, num_labels=2).to(device)
    optimizer = AdamW(model.parameters(), lr=LR)
    rng = np.random.RandomState(seed)
    order = np.arange(len(X))
    for _ in range(EPOCHS):
        model.train()
        rng.shuffle(order)
        for b in range(0, len(order), BATCH_SIZE):
            ids = [order[j] for j in range(b, min(b + BATCH_SIZE, len(order)))]
            enc = tok([X[i] for i in ids], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            yb = torch.tensor([y[i] for i in ids], device=device)
            out = model(**enc, labels=yb)
            optimizer.zero_grad()
            out.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
    return model, tok


def main() -> None:
    import argparse

    global POS_COUNTS, RUN_SEEDS
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", type=str, default="",
                    help="逗号分隔的数据点，缺省跑全部")
    ap.add_argument("--seeds", type=str, default="",
                    help="逗号分隔的种子，缺省 42,7")
    args = ap.parse_args()
    if args.points:
        POS_COUNTS = [int(p) for p in args.points.split(",")]
    if args.seeds:
        RUN_SEEDS = [int(s) for s in args.seeds.split(",")]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device} | points={POS_COUNTS} seeds={RUN_SEEDS}")

    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    va = pd.read_csv(VAL_CSV, encoding="utf-8")
    X_va = va["text"].astype(str).tolist()
    y_va = va["sound_negative"].astype(int).tolist()

    texts = df["text"].astype(str).tolist()
    labels = df["sound_negative_llm"].astype(int).tolist()
    X_tr_full, X_va_full, y_tr_full, y_va_full = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels)
    pos_all = [i for i, y in enumerate(y_tr_full) if y == 1]
    neg_all = [i for i, y in enumerate(y_tr_full) if y == 0]
    print(f"训练池: {len(X_tr_full)} (pos {len(pos_all)}) | "
          f"val_v2: {len(X_va)} (pos {sum(y_va)})")

    results = {}
    for n in POS_COUNTS:
        f1s = []
        for seed in RUN_SEEDS:
            rng = np.random.RandomState(seed)
            if n <= len(pos_all):
                pos = rng.choice(pos_all, size=n, replace=False)
            else:
                # 训练正例不足 N 时，从训练池正例有放回重采样补齐，
                # 验证集 val_v2 严格独立，绝不混入训练数据；
                # 训练池正例恰为 1006 条，1257 档实际使用的不重复正例 ≤ 1006
                pos = rng.choice(pos_all, size=n, replace=True)
            X_sub = ([X_tr_full[i] for i in pos] +
                     [X_tr_full[i] for i in rng.choice(
                         neg_all, size=n * NEG_RATIO, replace=False)])
            y_sub = [1] * n + [0] * (n * NEG_RATIO)
            combined = list(zip(X_sub, y_sub))
            rng.shuffle(combined)
            X_sub = [c[0] for c in combined]
            y_sub = [c[1] for c in combined]
            t0 = time.time()
            model, tok = train_once(X_sub, y_sub, seed, device)
            f1 = evaluate(model, tok, X_va, y_va, device)
            f1s.append(f1)
            print(f"n={n} seed={seed} f1@0.5={f1:.4f} "
                  f"({time.time() - t0:.0f}s)", flush=True)
        results[n] = (float(np.mean(f1s)), float(np.std(f1s)))

    import json

    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump({str(n): results[n] for n in results}, f, indent=2)
    print(f"结果已存 -> {RESULTS_JSON}")

    xs = list(results.keys())
    means = [results[n][0] for n in xs]
    stds = [results[n][1] for n in xs]

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.errorbar(xs, means, yerr=stds, marker="o", capsize=4, color="#1b5fd8")
    for x, m in zip(xs, means):
        ax.text(x, m + 0.008, f"{m:.3f}", ha="center", fontsize=9)
    ax.set_xlabel("正例数量")
    ax.set_ylabel("验证集 F1@0.5（val_v2）")
    ax.set_title("学习曲线：正例数量对音质差评识别 F1 的影响")
    ax.set_xlim(0, 1350)
    ax.annotate("所有数据量均严格使用独立验证集 val_v2",
                xy=(1257, means[-1]), xytext=(850, means[-1] - 0.03),
                fontsize=8, arrowprops=dict(arrowstyle="->", color="gray"))
    fig.tight_layout()
    plt.savefig(OUT_PNG, dpi=150)
    print(f"保存 -> {OUT_PNG}")
    for n in xs:
        print(f"n={n}: mean={results[n][0]:.4f} std={results[n][1]:.4f}")


if __name__ == "__main__":
    main()
