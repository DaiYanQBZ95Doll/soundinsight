# -*- coding: utf-8 -*-
# 本脚本用于多标签问题归因训练：基于 LLM 复核的问题类别标签，
# 用 DistilBERT 多标签分类识别音质问题（低音/清晰度/杂音/音量/高音），保存到 multi_label_model。
import json
import os
import sys

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from torch.optim import AdamW
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_llm.csv")
MODEL_DIR = os.path.join(HERE, "distilbert-base-uncased")
OUT_DIR = os.path.join(HERE, "multi_label_model")

ISSUE_COLS = ["issue_bass_llm", "issue_clarity_llm", "issue_noise_llm",
              "issue_volume_llm", "issue_treble_llm"]
ISSUE_NAMES = ["低音", "清晰度", "杂音", "音量", "高音"]

EPOCHS = 4
BATCH_SIZE = 16
LR = 2e-5
MAX_LEN = 128
SEED = 42


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    sub = df[df["sound_negative_llm"] == 1]
    texts = sub["text"].astype(str).tolist()
    Y = sub[ISSUE_COLS].astype(int).to_numpy()
    print(f"多标签样本: {len(texts)}")
    for name, col in zip(ISSUE_NAMES, ISSUE_COLS):
        print(f"  {name}: {int(sub[col].sum())}")

    X_tr, X_va, Y_tr, Y_va = train_test_split(
        texts, Y, test_size=0.2, random_state=SEED,
        stratify=Y.argmax(axis=1))

    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_DIR, num_labels=len(ISSUE_COLS),
        problem_type="multi_label_classification").to(device)
    optimizer = AdamW(model.parameters(), lr=LR)

    def run(X, Y, train=True):
        model.train(train)
        order = np.arange(len(X))
        if train:
            np.random.shuffle(order)
        total, probs = 0.0, []
        for b in range(0, len(order), BATCH_SIZE):
            ids = [order[j] for j in range(b, min(b + BATCH_SIZE, len(order)))]
            enc = tok([X[i] for i in ids], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            yb = torch.tensor(Y[ids], dtype=torch.float, device=device)
            out = model(**enc, labels=yb)
            if train:
                optimizer.zero_grad()
                out.loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            total += float(out.loss)
            probs.append(torch.sigmoid(out.logits).detach().cpu().numpy())
        return total / (len(order) // BATCH_SIZE + 1), np.vstack(probs)

    for ep in range(EPOCHS):
        loss, _ = run(X_tr, Y_tr, True)
        _, va_p = run(X_va, Y_va, False)
        pred = (va_p >= 0.5).astype(int)
        fs = [f1_score(Y_va[:, k], pred[:, k], zero_division=0)
              for k in range(len(ISSUE_COLS))]
        macro = float(np.mean(fs))
        print(f"[epoch {ep + 1}] loss={loss:.4f} macro_f1={macro:.4f} "
              + " ".join(f"{n}={v:.2f}" for n, v in zip(ISSUE_NAMES, fs)),
              flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    model.save_pretrained(OUT_DIR)
    tok.save_pretrained(OUT_DIR)
    with open(os.path.join(OUT_DIR, "issue_labels.json"), "w",
              encoding="utf-8") as f:
        json.dump({"columns": ISSUE_COLS, "names": ISSUE_NAMES}, f,
                  ensure_ascii=False)
    print(f"saved -> {OUT_DIR}")


if __name__ == "__main__":
    main()
