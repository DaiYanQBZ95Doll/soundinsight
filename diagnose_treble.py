# -*- coding: utf-8 -*-
# diagnose_treble.py —— 高音（treble）归因失效的机制诊断
#
# 说明：不改动任何模型或标签，只做"只读"诊断：
#   1. 定位冻结多标签模型对应的标签版本（1257 口径）
#   2. 复现训练脚本的 80/20 划分（同 seed、同 stratify 逻辑）
#   3. 用冻结模型在验证划分上推理，给出逐类 F1 与高音的概率分布
#   4. 量化标签语义重叠（高音 vs 清晰度）与关键词证据
import json
import os
import re
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
ISSUE_COLS = ["issue_bass_llm", "issue_clarity_llm", "issue_noise_llm",
              "issue_volume_llm", "issue_treble_llm"]
ISSUE_NAMES = ["低音", "清晰度", "杂音", "音量", "高音"]
SEED = 42
TREBLE_WORDS = re.compile(
    r"\b(treble|high[- ]?end|highs?|shrill|harsh|piercing|tinny|sibilant)\b",
    re.I)
CLARITY_WORDS = re.compile(
    r"\b(muffl\w*|muddy|mud\b|clear\w*|clarity|distort\w*|dull|veiled|"
    r"garbled|unclear)\b", re.I)


def candidate_files():
    fs = ["labeled_llm.csv", "labeled_llm_before_treble.csv",
          "labeled_llm_before_mid_demote.csv",
          "labeled_llm_before_mid_remove.csv"]
    out = []
    for f in fs:
        p = os.path.join(HERE, f)
        if os.path.isfile(p):
            out.append(p)
    return out


def main():
    print("=" * 70)
    print("高音归因失效诊断（只读，不训练）")
    print("=" * 70)

    print("\n[1] 候选标签版本与类别分布")
    chosen = None
    for p in candidate_files():
        d = pd.read_csv(p, encoding="utf-8", keep_default_na=False)
        s = d[d["sound_negative_llm"].astype(int) == 1]
        counts = [int(s[c].astype(int).sum()) for c in ISSUE_COLS]
        print(f"  {os.path.basename(p):<38} 正例 {len(s):>5}  "
              + "  ".join(f"{n} {c}" for n, c in zip(ISSUE_NAMES, counts)))
        if len(s) == 1257 and counts[4] == 84:
            chosen = (p, s)
    if chosen is None:
        print("  未找到 1257/高音 84 的版本，退出")
        return 1
    path, sub = chosen
    print(f"  → 冻结多标签模型对应版本：{os.path.basename(path)}")

    texts = sub["text"].astype(str).tolist()
    Y = sub[ISSUE_COLS].astype(int).to_numpy()

    print("\n[2] 复现 80/20 划分（seed=42，stratify=Y.argmax(axis=1)）")
    X_tr, X_va, Y_tr, Y_va = train_test_split(
        texts, Y, test_size=0.2, random_state=SEED,
        stratify=Y.argmax(axis=1))
    print(f"  训练 {len(X_tr)} 条 / 验证 {len(X_va)} 条")
    for k, n in enumerate(ISSUE_NAMES):
        print(f"  {n:<4} 训练正例 {int(Y_tr[:, k].sum()):>4} | "
              f"验证正例 {int(Y_va[:, k].sum()):>3}")

    print("\n[3] 用冻结模型推理验证划分")
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
    pred = (P >= 0.5).astype(int)

    print("\n  逐类指标（验证划分）：")
    f1s = []
    for k, n in enumerate(ISSUE_NAMES):
        y, pr = Y_va[:, k], pred[:, k]
        tp = int(((y == 1) & (pr == 1)).sum())
        fp = int(((y == 0) & (pr == 1)).sum())
        fn = int(((y == 1) & (pr == 0)).sum())
        f1 = f1_score(y, pr, zero_division=0)
        f1s.append(f1)
        print(f"  {n:<4} F1 {f1:.4f} | TP {tp} FP {fp} FN {fn} | "
              f"预测为正 {int(pr.sum())} 条")
    print(f"  宏 F1（五类）= {np.mean(f1s):.4f}；"
          f"剔除高音后四类宏 F1 = {np.mean(f1s[:4]):.4f}")

    print("\n  高音概率分布（验证划分全部样本）：")
    pt = P[:, 4]
    qs = np.percentile(pt, [50, 90, 95, 99, 100])
    print(f"    中位 {qs[0]:.4f} | P90 {qs[1]:.4f} | P95 {qs[2]:.4f} | "
          f"P99 {qs[3]:.4f} | 最大 {qs[4]:.4f}")
    print(f"    概率≥0.5 的样本数：{int((pt >= 0.5).sum())}")
    tv = Y_va[:, 4] == 1
    if tv.sum():
        print(f"    高音正例（{int(tv.sum())} 条）概率："
              f"最大 {pt[tv].max():.4f}，均值 {pt[tv].mean():.4f}；"
              f"其中≥0.5 的 {int((pt[tv] >= 0.5).sum())} 条")

    print("\n[4] 只调阈值能否救回高音（验证划分）")
    print("  阈值   预测为正   TP  FP  FN    F1")
    best = (0.0, -1.0)
    for th in (0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50):
        pr = (P[:, 4] >= th).astype(int)
        y = Y_va[:, 4]
        tp = int(((y == 1) & (pr == 1)).sum())
        fp = int(((y == 0) & (pr == 1)).sum())
        fn = int(((y == 1) & (pr == 0)).sum())
        f1 = f1_score(y, pr, zero_division=0)
        if f1 > best[1]:
            best = (th, f1)
        print(f"  {th:.2f}   {int(pr.sum()):>8}   {tp:>3} {fp:>3} {fn:>3}  {f1:.4f}")
    print(f"  → 阈值降到 {best[0]:.2f} 时高音 F1 最高可达 {best[1]:.4f}"
          f"（仍远低于其他四类）")

    print("\n[5] 标签语义重叠证据（1257 口径全量）")
    tre = sub["issue_treble_llm"].astype(int) == 1
    cla = sub["issue_clarity_llm"].astype(int) == 1
    print(f"  高音正例 {int(tre.sum())} 条；其中同时标了清晰度 "
          f"{int((tre & cla).sum())} 条（{int((tre & cla).sum()) / max(int(tre.sum()), 1) * 100:.1f}%）")
    print(f"  清晰度正例 {int(cla.sum())} 条；其中同时标了高音 "
          f"{int((tre & cla).sum())} 条（{int((tre & cla).sum()) / max(int(cla.sum()), 1) * 100:.1f}%）")
    tw = sub["text"].astype(str).str.contains(TREBLE_WORDS)
    cw = sub["text"].astype(str).str.contains(CLARITY_WORDS)
    print(f"  含高音关键词的评论 {int(tw.sum())} 条 → 其中标为高音 "
          f"{int((tw & tre).sum())} 条（漏标 {int((tw & ~tre).sum())} 条）")
    print(f"  标为高音但正文含清晰度关键词的 "
          f"{int((tre & cw).sum())} 条 / {int(tre.sum())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
