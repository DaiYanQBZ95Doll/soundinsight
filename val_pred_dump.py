# -*- coding: utf-8 -*-
# Batch C 前置：用冻结模型对 val_v2 全量推理一次，保存
# 概率/预测/长度/标签 到 val_preds_dump.csv，供 C1/C3/C4 复用（GPU 任务串行）。
import json
import os
import sys

import numpy as np
import pandas as pd
import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "sound_model")
VAL_CSV = os.path.join(HERE, "val_v2.csv")
OUT_CSV = os.path.join(HERE, "val_preds_dump.csv")


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device}")
    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_DIR).to(device)
    model.eval()
    with open(os.path.join(MODEL_DIR, "threshold.json"),
              encoding="utf-8") as f:
        thr = float(json.load(f)["threshold"])
    print(f"threshold={thr}")

    va = pd.read_csv(VAL_CSV, encoding="utf-8", keep_default_na=False)
    texts = va["text"].astype(str).tolist()
    labels = va["sound_negative"].astype(int).to_numpy()

    probs = []
    with torch.no_grad():
        for b in range(0, len(texts), 64):
            enc = tok(texts[b:b + 64], padding=True, truncation=True,
                      max_length=128, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            probs.append(torch.softmax(model(**enc).logits, -1)
                         [:, 1].cpu().numpy())
    probs = np.concatenate(probs)
    pred = (probs >= thr).astype(int)

    out = pd.DataFrame({
        "text": texts,
        "sound_negative": labels,
        "prob": probs,
        "pred": pred,
        "len_chars": [len(t) for t in texts],
        "len_words": [len(t.split()) for t in texts],
    })
    out.to_csv(OUT_CSV, index=False, encoding="utf-8")
    tp = int(((pred == 1) & (labels == 1)).sum())
    fp = int(((pred == 1) & (labels == 0)).sum())
    fn = int(((pred == 0) & (labels == 1)).sum())
    tn = int(((pred == 0) & (labels == 0)).sum())
    print(f"n={len(out)} pos={int(labels.sum())}")
    print(f"TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"saved -> {OUT_CSV}")


if __name__ == "__main__":
    main()
