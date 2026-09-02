# -*- coding: utf-8 -*-
# 本脚本用于 RoBERTa-base 1 折快速验证：小训练集训练两轮，固定验证集评估，
# 输出 F1@0.5 与调优 F1，并与 DistilBERT 对比。OOM 时自动降 batch 加梯度累积。
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (accuracy_score, f1_score, precision_recall_curve)
from torch.optim import AdamW
from transformers import (RobertaForSequenceClassification, RobertaTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "roberta-base")
TRAIN_CSV = os.path.join(HERE, "train_quick.csv")
VAL_CSV = os.path.join(HERE, "val_v2.csv")

EPOCHS = 2
LR = 2e-5
MAX_LEN = 128
SEED = 42
MEM_LIMIT = 7.5e9  # 显存超过 7.5GB 立即停止


def train_one_pass(model, tok, X, y, optimizer, device, batch_size, accum):
    model.train()
    rng = np.random.RandomState(SEED)
    order = np.arange(len(X))
    rng.shuffle(order)
    total_loss, steps = 0.0, 0
    optimizer.zero_grad()
    for b in range(0, len(order), batch_size):
        ids = [order[j] for j in range(b, min(b + batch_size, len(order)))]
        enc = tok([X[i] for i in ids], padding=True, truncation=True,
                  max_length=MAX_LEN, return_tensors="pt")
        enc = {k: v.to(device) for k, v in enc.items()}
        yb = torch.tensor([y[i] for i in ids], device=device)
        out = model(**enc, labels=yb)
        (out.loss / accum).backward()
        steps += 1
        if steps % accum == 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            optimizer.zero_grad()
        total_loss += float(out.loss)
        if torch.cuda.memory_reserved() > MEM_LIMIT:
            raise MemoryError("GPU 显存超过 7.5GB，按规则停止")
    return total_loss / max(steps, 1)


def evaluate(model, tok, X, y, device):
    model.eval()
    probs = []
    with torch.no_grad():
        for b in range(0, len(X), 16):
            enc = tok(X[b:b + 16], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            probs.append(torch.softmax(model(**enc).logits, -1)
                         [:, 1].cpu().numpy())
    probs = np.concatenate(probs)
    y = np.asarray(y)
    pred = (probs >= 0.5).astype(int)
    acc = accuracy_score(y, pred)
    f1a = f1_score(y, pred, zero_division=0)
    precision, recall, thrs = precision_recall_curve(y, probs)
    f1s = 2 * precision * recall / (precision + recall + 1e-12)
    i = int(np.argmax(f1s))
    f1b = float(f1s[i])
    thr = float(thrs[i]) if i < len(thrs) else 0.5
    return acc, f1a, f1b, thr


def main() -> None:
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}")

    tr = pd.read_csv(TRAIN_CSV, encoding="utf-8")
    va = pd.read_csv(VAL_CSV, encoding="utf-8")
    X_tr, y_tr = tr["text"].astype(str).tolist(), tr["sound_negative"].tolist()
    X_va, y_va = va["text"].astype(str).tolist(), va["sound_negative"].tolist()
    print(f"train_quick: {len(X_tr)} (pos {sum(y_tr)}) | "
          f"val_v2: {len(X_va)} (pos {sum(y_va)})")

    tok = RobertaTokenizer.from_pretrained(MODEL_DIR)
    model = RobertaForSequenceClassification.from_pretrained(
        MODEL_DIR, num_labels=2).to(device)
    optimizer = AdamW(model.parameters(), lr=LR)

    configs = [(8, 1), (4, 2)]  # OOM 时降 batch 并梯度累积
    for bs, accum in configs:
        try:
            for ep in range(1, EPOCHS + 1):
                t0 = time.time()
                loss = train_one_pass(model, tok, X_tr, y_tr, optimizer,
                                      device, bs, accum)
                acc, f1a, f1b, thr = evaluate(model, tok, X_va, y_va, device)
                print(f"[epoch {ep}] bs={bs} accum={accum} loss={loss:.4f} | "
                      f"val acc={acc:.4f} f1@0.5={f1a:.4f} "
                      f"f1_best={f1b:.4f} @thr={thr:.4f} | "
                      f"{time.time() - t0:.0f}s", flush=True)
            break
        except (torch.cuda.OutOfMemoryError, MemoryError) as e:
            print(f"bs={bs} 失败: {e}；切换下一档配置", flush=True)
            torch.cuda.empty_cache()
            if isinstance(e, MemoryError):
                raise
            model = RobertaForSequenceClassification.from_pretrained(
                MODEL_DIR, num_labels=2).to(device)
            optimizer = AdamW(model.parameters(), lr=LR)

    acc, f1a, f1b, thr = evaluate(model, tok, X_va, y_va, device)
    print(f"\n=== RoBERTa-base 快速验证结果 ===")
    print(f"val acc={acc:.4f} | F1@0.5={f1a:.4f} | 调优F1={f1b:.4f} "
          f"@thr={thr:.4f}")
    print("DistilBERT 对照: F1@0.5=0.6241 | 调优F1=0.6871 @thr=0.9744")
    if f1b >= 0.72:
        verdict = "RoBERTa 显著优于 DistilBERT：立即启动全量训练"
    elif f1b >= 0.68:
        verdict = "差距不大：保留 DistilBERT，RoBERTa 作为基座对比写入文档"
    else:
        verdict = "低于 0.68：DistilBERT 选型正确，RoBERTa 作为消融基座对比"
    print(f"决策: {verdict}")


if __name__ == "__main__":
    main()
