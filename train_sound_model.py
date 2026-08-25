# -*- coding: utf-8 -*-
# 本脚本用于模型训练：自动下载基座模型，对标注数据做小样本微调，输出验证集指标并保存模型与阈值。
"""Step 2: fine-tune DistilBERT for sound_negative binary classification."""
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
import requests
import torch
from sklearn.metrics import accuracy_score, f1_score, precision_recall_curve
from sklearn.model_selection import train_test_split
from torch.optim import AdamW
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer, get_linear_schedule_with_warmup)

BASE_DIR = Path(__file__).resolve().parent
LABELED_CSV = BASE_DIR / "labeled_data_final.csv"
MODEL_DIR = BASE_DIR / "distilbert-base-uncased"
OUT_DIR = BASE_DIR / "sound_model"

EPOCHS = 3
BATCH_SIZE = 16
LR = 2e-5
MAX_LEN = 128
SEED = 42
OVERSAMPLE_POS_RATIO = 0.2  # oversample positives to ~20% of train set

BASE_MODEL_FILES = [
    "config.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.txt",
    "model.safetensors",
]
HF_BASE = "https://huggingface.co/distilbert-base-uncased/resolve/main/"
MS_BASE = ("https://modelscope.cn/api/v1/models/AI-ModelScope/"
           "distilbert-base-uncased/repo?FilePath=")


def ensure_base_model() -> None:
    """Download the base model if the local directory is missing.

    Tries Hugging Face first, falls back to the ModelScope mirror.
    """
    if MODEL_DIR.is_dir() and (MODEL_DIR / "model.safetensors").exists():
        print("base model found locally:", MODEL_DIR)
        return
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    sources = [("HuggingFace", HF_BASE), ("ModelScope", MS_BASE)]
    for name in BASE_MODEL_FILES:
        dst = MODEL_DIR / name
        if dst.exists() and dst.stat().st_size > 1000:
            continue
        for src_name, base in sources:
            try:
                r = requests.get(base + name, timeout=180, stream=True)
                if r.status_code != 200:
                    continue
                with open(dst, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                print(f"downloaded {name} from {src_name} "
                      f"({dst.stat().st_size / (1 << 20):.1f} MB)")
                break
            except Exception as e:  # noqa: BLE001 - try the next source
                print(f"  {src_name} failed for {name}: "
                      f"{type(e).__name__}")
        else:
            raise RuntimeError(
                f"cannot download {name}; check network or place the base "
                f"model files in {MODEL_DIR} manually")


def main() -> None:
    ensure_base_model()

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("device:", device, "| torch:", torch.__version__)

    df = pd.read_csv(LABELED_CSV, encoding="utf-8")
    print("rows:", len(df), "| positives:", int(df["sound_negative"].sum()))

    texts = df["text"].astype(str).tolist()
    labels = df["sound_negative"].astype(int).tolist()

    X_tr, X_va, y_tr, y_va = train_test_split(
        texts, labels, test_size=0.2, random_state=SEED, stratify=labels
    )
    print(f"train: {len(X_tr)} (pos {sum(y_tr)}), val: {len(X_va)} "
          f"(pos {sum(y_va)})")

    # Oversample positive training examples to fight class imbalance
    pos_idx = [i for i, y in enumerate(y_tr) if y == 1]
    neg_idx = [i for i, y in enumerate(y_tr) if y == 0]
    n_pos_target = max(
        len(pos_idx), int(OVERSAMPLE_POS_RATIO * len(neg_idx) /
                          (1 - OVERSAMPLE_POS_RATIO))
    )
    extra = np.random.choice(pos_idx, size=n_pos_target - len(pos_idx))
    train_idx = neg_idx + pos_idx + extra.tolist()
    np.random.shuffle(train_idx)
    X_tr = [X_tr[i] for i in train_idx]
    y_tr = [y_tr[i] for i in train_idx]
    print(f"train after oversampling: {len(X_tr)} (pos {sum(y_tr)}, "
          f"ratio {sum(y_tr) / len(y_tr):.2%})")

    tok = DistilBertTokenizer.from_pretrained(str(MODEL_DIR))
    model = DistilBertForSequenceClassification.from_pretrained(
        str(MODEL_DIR), num_labels=2
    ).to(device)

    def enc(texts_batch):
        return tok(texts_batch, padding=True, truncation=True,
                   max_length=MAX_LEN, return_tensors="pt")

    optimizer = AdamW(model.parameters(), lr=LR)
    steps = (len(X_tr) + BATCH_SIZE - 1) // BATCH_SIZE * EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(0.06 * steps), num_training_steps=steps
    )

    def run_epoch(phase):
        is_train = phase == "train"
        model.train(is_train)
        X, y = (X_tr, y_tr) if is_train else (X_va, y_va)
        order = np.arange(len(X))
        if is_train:
            np.random.shuffle(order)
        total_loss, preds, gold, probs = 0.0, [], [], []
        n_batches = (len(order) + BATCH_SIZE - 1) // BATCH_SIZE
        t0 = time.time()
        for b in range(n_batches):
            idx = order[b * BATCH_SIZE:(b + 1) * BATCH_SIZE]
            enc_in = enc([X[i] for i in idx])
            enc_in = {k: v.to(device) for k, v in enc_in.items()}
            yb = torch.tensor([y[i] for i in idx], device=device)
            out = model(**enc_in, labels=yb)
            loss = out.loss
            if is_train:
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
            total_loss += float(loss)
            preds.extend(out.logits.argmax(-1).tolist())
            probs.extend(torch.softmax(out.logits, -1)[:, 1].tolist())
            gold.extend(yb.tolist())
            if is_train and (b + 1) % 40 == 0:
                print(f"  batch {b + 1}/{n_batches}, "
                      f"{time.time() - t0:.0f}s elapsed", flush=True)
        acc = accuracy_score(gold, preds)
        f1 = f1_score(gold, preds, zero_division=0)
        return total_loss / n_batches, acc, f1, gold, probs

    best_f1, best_state = -1.0, None
    va_gold, va_probs = None, None
    for epoch in range(1, EPOCHS + 1):
        t0 = time.time()
        tr_loss, tr_acc, tr_f1, _, _ = run_epoch("train")
        va_loss, va_acc, va_f1, va_gold, va_probs = run_epoch("val")
        print(f"[epoch {epoch}] train loss={tr_loss:.4f} acc={tr_acc:.4f} "
              f"f1={tr_f1:.4f} | val loss={va_loss:.4f} acc={va_acc:.4f} "
              f"f1={va_f1:.4f} | {time.time() - t0:.0f}s", flush=True)
        if va_f1 >= best_f1:
            best_f1 = va_f1
            best_state = {k: v.detach().cpu().clone()
                          for k, v in model.state_dict().items()}

    # Threshold tuning on validation probabilities (maximize F1)
    va_gold = np.asarray(va_gold)
    va_probs = np.asarray(va_probs)
    precision, recall, thresholds = precision_recall_curve(va_gold, va_probs)
    f1s = 2 * precision * recall / (precision + recall + 1e-12)
    best_i = int(np.argmax(f1s))
    best_thr = float(thresholds[best_i]) if best_i < len(thresholds) else 0.5
    tuned_f1 = float(f1s[best_i])
    print(f"threshold tuning: best_threshold={best_thr:.3f} "
          f"(val f1 {tuned_f1:.4f})")

    model.load_state_dict(best_state)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUT_DIR))
    tok.save_pretrained(str(OUT_DIR))
    with open(OUT_DIR / "threshold.json", "w", encoding="utf-8") as f:
        json.dump({"threshold": best_thr}, f)
    print(f"model saved -> {OUT_DIR} (best val f1 {best_f1:.4f}, "
          f"tuned f1 {tuned_f1:.4f}, threshold {best_thr:.3f})")
    print(f"FINAL val accuracy={va_acc:.4f} f1={va_f1:.4f} "
          f"(tuned {tuned_f1:.4f})")


if __name__ == "__main__":
    main()
