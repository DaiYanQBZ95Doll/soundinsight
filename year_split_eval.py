# -*- coding: utf-8 -*-
# 本脚本用于 D 批次年份分桶实测：val_v2 按评论年份分桶，
# 用冻结模型计算各年份桶的 F1@0.5，为 Q6 数据时效性提供真实证据。
import json
import os
import sys

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import f1_score
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "sound_model")
VAL_CSV = os.path.join(HERE, "val_v2.csv")
EXPANDED_CSV = os.path.join(HERE, "electronics_expanded.csv")


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_DIR).to(device)
    model.eval()
    with open(os.path.join(MODEL_DIR, "threshold.json"),
              encoding="utf-8") as f:
        thr = float(json.load(f)["threshold"])

    va = pd.read_csv(VAL_CSV, encoding="utf-8", keep_default_na=False)
    exp = pd.read_csv(EXPANDED_CSV, encoding="utf-8", keep_default_na=False)
    exp["text_stripped"] = exp["text"].astype(str).str.strip()
    ts_map = dict(zip(exp["text_stripped"],
                      pd.to_datetime(exp["timestamp"], unit="ms", utc=True,
                                     errors="coerce")))
    va["year"] = va["text"].str.strip().map(ts_map).dt.year
    covered = int(va["year"].notna().sum())
    print(f"val_v2 时间戳匹配覆盖: {covered}/{len(va)}")

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
    va["pred"] = pred

    print("\n年份分桶 F1@0.5（阈值 0.9744）:")
    for year in sorted(va["year"].dropna().unique()):
        sub = va[va["year"] == year]
        f1 = f1_score(sub["sound_negative"], sub["pred"], zero_division=0)
        print(f"  {int(year)}: n={len(sub)}, pos={int(sub['sound_negative'].sum())}, "
              f"F1={f1:.4f}")
    overall = f1_score(va["sound_negative"], va["pred"], zero_division=0)
    print(f"  全部: n={len(va)}, F1={overall:.4f}")


if __name__ == "__main__":
    main()
