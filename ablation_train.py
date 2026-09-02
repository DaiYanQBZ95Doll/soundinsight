# -*- coding: utf-8 -*-
# 本脚本用于消融实验训练：支持 A 无采样、B class_weight 平衡、C Focal Loss 三种模式，
# 验证集固定为 val_v2.csv，产出训练日志、混淆矩阵与配置到指定实验目录。
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_recall_curve, precision_score,
                             recall_score)
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
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

EPOCHS = 3
BATCH_SIZE = 16
LR = 2e-5
MAX_LEN = 128
SEED = 42
FOCAL_GAMMA = 2.0
FOCAL_ALPHA = 0.25


def focal_loss(logits, targets):
    ce = F.cross_entropy(logits, targets, reduction="none")
    pt = torch.exp(-ce)
    alpha_t = torch.where(targets == 1, FOCAL_ALPHA, 1 - FOCAL_ALPHA)
    return (alpha_t * ((1 - pt) ** FOCAL_GAMMA) * ce).mean()


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
    y = np.asarray(y)
    pred = (probs >= 0.5).astype(int)
    precision, recall, thrs = precision_recall_curve(y, probs)
    f1s = 2 * precision * recall / (precision + recall + 1e-12)
    i = int(np.argmax(f1s))
    return {
        "acc": float(accuracy_score(y, pred)),
        "f1_05": float(f1_score(y, pred, zero_division=0)),
        "f1_best": float(f1s[i]),
        "thr_best": float(thrs[i]) if i < len(thrs) else 0.5,
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "cm": confusion_matrix(y, pred, labels=[0, 1]),
        "probs": probs,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["A", "B", "C"])
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    outdir = os.path.join(HERE, args.outdir)
    os.makedirs(outdir, exist_ok=True)

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"mode={args.mode} | device={device} | outdir={outdir}")

    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    texts = df["text"].astype(str).tolist()
    labels = df["sound_negative_llm"].astype(int).tolist()
    X_tr, X_va, y_tr, y_va = train_test_split(
        texts, labels, test_size=0.2, random_state=SEED, stratify=labels)
    va_fixed = pd.read_csv(VAL_CSV, encoding="utf-8")
    X_va = va_fixed["text"].astype(str).tolist()
    y_va = va_fixed["sound_negative"].astype(int).tolist()
    assert sum(y_va) == 251, "val_v2 正例数异常"
    print(f"train(全量): {len(X_tr)} (pos {sum(y_tr)}) | "
          f"val_v2: {len(X_va)} (pos {sum(y_va)})")

    if args.mode != "A":
        rng = np.random.RandomState(SEED)
        pos = [i for i, y in enumerate(y_tr) if y == 1]
        neg = [i for i, y in enumerate(y_tr) if y == 0]
        neg_keep = rng.choice(neg, size=len(pos) * 10, replace=False)
        idx = neg_keep.tolist() + pos
        rng.shuffle(idx)
        X_tr = [X_tr[i] for i in idx]
        y_tr = [y_tr[i] for i in idx]
    print(f"train(实际): {len(X_tr)} (pos {sum(y_tr)})")

    class_weights = None
    if args.mode == "B":
        cw = compute_class_weight("balanced", classes=np.array([0, 1]),
                                  y=np.asarray(y_tr))
        class_weights = torch.tensor(cw, dtype=torch.float, device=device)
        print(f"class_weight: {cw.tolist()}")

    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_DIR, num_labels=2).to(device)
    optimizer = AdamW(model.parameters(), lr=LR)

    log_lines = []
    def log(msg):
        print(msg, flush=True)
        log_lines.append(msg)

    final_metrics = None
    for ep in range(1, EPOCHS + 1):
        model.train()
        rng = np.random.RandomState(SEED)
        order = np.arange(len(X_tr))
        rng.shuffle(order)
        total, steps, t0 = 0.0, 0, time.time()
        for b in range(0, len(order), BATCH_SIZE):
            ids = [order[j] for j in range(b, min(b + BATCH_SIZE, len(order)))]
            enc = tok([X_tr[i] for i in ids], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            yb = torch.tensor([y_tr[i] for i in ids], device=device)
            out = model(**enc)
            if args.mode == "C":
                loss = focal_loss(out.logits, yb)
            elif class_weights is not None:
                loss = F.cross_entropy(out.logits, yb, weight=class_weights)
            else:
                loss = F.cross_entropy(out.logits, yb)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total += float(loss)
            steps += 1
            if steps % 200 == 0:
                log(f"  batch {steps} ({time.time() - t0:.0f}s)")
        m = evaluate(model, tok, X_va, y_va, device)
        log(f"[epoch {ep}] loss={total / max(steps, 1):.4f} "
            f"acc={m['acc']:.4f} f1@0.5={m['f1_05']:.4f} "
            f"f1_best={m['f1_best']:.4f} @thr={m['thr_best']:.4f} | "
            f"{time.time() - t0:.0f}s")
        final_metrics = m

    m = final_metrics
    log(f"FINAL acc={m['acc']:.4f} f1@0.5={m['f1_05']:.4f} "
        f"f1_best={m['f1_best']:.4f} prec={m['precision']:.4f} "
        f"rec={m['recall']:.4f}")
    log(f"confusion matrix: {m['cm'].tolist()}")

    with open(os.path.join(outdir, "training_output.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(5, 4.5))
    im = ax.imshow(m["cm"], cmap="Blues")
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["音质正常(预测)", "音质负面(预测)"])
    ax.set_yticklabels(["音质正常(实际)", "音质负面(实际)"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(int(m["cm"][i, j])), ha="center",
                    va="center", fontsize=18)
    ax.set_title(f"消融{args.mode} 验证集混淆矩阵")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    plt.savefig(os.path.join(outdir, "confusion_matrix.png"), dpi=150)
    plt.close(fig)

    config = {
        "mode": args.mode,
        "loss": "focal(gamma=2,alpha=0.25)" if args.mode == "C"
                else ("cross_entropy+class_weight_balanced"
                      if args.mode == "B" else "cross_entropy"),
        "batch_size": BATCH_SIZE, "lr": LR, "epochs": EPOCHS,
        "max_len": MAX_LEN, "seed": SEED,
        "train_rows": len(X_tr), "train_pos": int(sum(y_tr)),
        "val_rows": len(X_va), "val_pos": int(sum(y_va)),
        "acc": m["acc"], "f1_05": m["f1_05"], "f1_best": m["f1_best"],
        "thr_best": m["thr_best"], "precision": m["precision"],
        "recall": m["recall"], "cm": m["cm"].tolist(),
    }
    with open(os.path.join(outdir, "config.json"), "w",
              encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"实验完成 -> {outdir}")


if __name__ == "__main__":
    main()
