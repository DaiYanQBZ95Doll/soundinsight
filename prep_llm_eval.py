# -*- coding: utf-8 -*-
# 本脚本用于批次 B 准备：从 val_v2 取全部 251 正例 + 749 分层负例（seed 42）
# 组成 1000 条评估子集，并用冻结小模型生成参考预测（供复核模式使用）。
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
VAL_CSV = os.path.join(HERE, "val_v2.csv")
MODEL_DIR = os.path.join(HERE, "sound_model")
OUT_JSONL = os.path.join(HERE, "llm_eval_input.jsonl")
PRED_JSONL = os.path.join(HERE, "llm_eval_small_preds.jsonl")


def main() -> None:
    va = pd.read_csv(VAL_CSV, encoding="utf-8", keep_default_na=False)
    pos = va[va["sound_negative"] == 1]
    neg = va[va["sound_negative"] == 0]
    neg_sample = neg.sample(n=749, random_state=42)
    subset = pd.concat([pos, neg_sample]).sample(frac=1, random_state=42)
    print(f"评估子集: {len(subset)} | 正例 {int(subset['sound_negative'].sum())}")

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for i, (idx, row) in enumerate(subset.iterrows()):
            f.write(json.dumps({
                "id": i,
                "label": int(row["sound_negative"]),
                "text": str(row["text"]),
            }, ensure_ascii=False) + "\n")
    print(f"写入 -> {OUT_JSONL}")

    # 小模型参考预测（复核模式用）
    with open(os.path.join(MODEL_DIR, "threshold.json"),
              encoding="utf-8") as f:
        thr = float(json.load(f)["threshold"])
    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(MODEL_DIR)
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    texts = subset["text"].astype(str).tolist()
    with open(PRED_JSONL, "w", encoding="utf-8") as f:
        with torch.no_grad():
            for b in range(0, len(texts), 64):
                enc = tok(texts[b:b + 64], padding=True, truncation=True,
                          max_length=128, return_tensors="pt")
                enc = {k: v.to(device) for k, v in enc.items()}
                probs = torch.softmax(model(**enc).logits, -1)[:, 1].cpu()
                for j, p in enumerate(probs):
                    i = b + j
                    f.write(json.dumps({
                        "id": i,
                        "pred": 1 if float(p) >= thr else 0,
                        "prob": round(float(p), 4),
                    }) + "\n")
    print(f"写入 -> {PRED_JSONL}")


if __name__ == "__main__":
    main()
