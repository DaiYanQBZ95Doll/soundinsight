# -*- coding: utf-8 -*-
# tune_per_class_threshold.py —— 逐类阈值调优的收益测量（只读，不改模型）
#
# 目的：给出"不动权重、只把统一阈值 0.5 换成逐类阈值"能带来多少提升，
# 为"高音归因修复方案"提供实测依据。
#
# 注意（如实披露）：阈值在同一验证划分上调优 → 指标偏乐观；正式落地应改用
# 交叉验证或独立划分选择阈值。本脚本只做收益量级测量，不产出对外指标。
import json
import os
import sys

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "multi_label_model")
CSV = os.path.join(HERE, "labeled_llm_before_treble.csv")
ISSUE_COLS = ["issue_bass_llm", "issue_clarity_llm", "issue_noise_llm",
              "issue_volume_llm", "issue_treble_llm"]
ISSUE_NAMES = ["低音", "清晰度", "杂音", "音量", "高音"]
SEED = 42
GRID = [round(x, 2) for x in np.arange(0.05, 0.96, 0.05)]


def main():
    df = pd.read_csv(CSV, encoding="utf-8", keep_default_na=False)
    sub = df[df["sound_negative_llm"].astype(int) == 1]
    texts = sub["text"].astype(str).tolist()
    Y = sub[ISSUE_COLS].astype(int).to_numpy()
    X_tr, X_va, Y_tr, Y_va = train_test_split(
        texts, Y, test_size=0.2, random_state=SEED,
        stratify=Y.argmax(axis=1))
    print(f"样本 {len(texts)}（训练 {len(X_tr)} / 验证 {len(X_va)}）")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_DIR).to(device)
    model.eval()
    probs = []
    with torch.no_grad():
        for b in range(0, len(X_va), 32):
            enc = tok(X_va[b:b + 32], padding=True, truncation=True,
                      max_length=128, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            probs.append(torch.sigmoid(model(**enc).logits).cpu().numpy())
    P = np.vstack(probs)

    print("\n统一阈值 0.5（当前线上行为）：")
    f1_unified = []
    for k, n in enumerate(ISSUE_NAMES):
        f1 = f1_score(Y_va[:, k], (P[:, k] >= 0.5).astype(int),
                      zero_division=0)
        f1_unified.append(f1)
        print(f"  {n:<4} F1 {f1:.4f}")
    print(f"  宏 F1 = {np.mean(f1_unified):.4f}")

    print("\n逐类最优阈值（在验证划分上网格搜索 0.05-0.95）：")
    best = {}
    f1_best = []
    for k, n in enumerate(ISSUE_NAMES):
        scores = [(f1_score(Y_va[:, k], (P[:, k] >= th).astype(int),
                            zero_division=0), th) for th in GRID]
        f1v, th = max(scores)
        best[n] = round(float(th), 2)
        f1_best.append(f1v)
        print(f"  {n:<4} 阈值 {th:.2f} → F1 {f1v:.4f}"
              f"（统一 0.5 时 {f1_unified[k]:.4f}）")
    print(f"  宏 F1（逐类阈值）= {np.mean(f1_best):.4f}"
          f"（统一 0.5 时 {np.mean(f1_unified):.4f}）")

    out = os.path.join(HERE, "per_class_thresholds_probe.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"note": "在验证划分上网格搜索，指标偏乐观，仅供收益量级参考",
                   "thresholds": best,
                   "macro_f1_unified_0.5": round(float(np.mean(f1_unified)), 4),
                   "macro_f1_per_class": round(float(np.mean(f1_best)), 4),
                   "per_class_f1_unified": [round(float(x), 4)
                                            for x in f1_unified],
                   "per_class_f1_best": [round(float(x), 4)
                                         for x in f1_best]},
                  f, ensure_ascii=False, indent=1)
    print(f"\n已保存 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
