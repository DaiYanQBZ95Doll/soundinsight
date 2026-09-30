# -*- coding: utf-8 -*-
"""W1 变体 E：混合策略（短文本截断 + 长文本切窗 + **分档阈值**）。

## 动机（来自变体 A–D 的实测）

- A/B（截断 @128/@256）：截断桶（>128 token）召回 **51.2%**，且 256 相对 128 **零改善**
  （长文本中 39.3% 超过 256 token）；
- C（全量切窗 @0.5）：截断桶召回 **82.9%**，但整体精确率从 69.7% 掉到 47.7%
  （max 聚合抬高长文本分数分布）；在 tune 上改用单一全局阈值 0.8 后，短文本桶反而受损
  —— **一个全局阈值无法同时服务长文本与短文本**。

## 本变体做法

1. 对每条评论按 token 长度分档：**短档 ≤128**、**长档 >128**；
2. 短档用**截断推理**概率，长档用**切窗推理（取窗口最大概率）**概率；
3. **两档各自在 `val_v3_tune` 上选阈值**（网格搜索，目标是整体 F1 最大，
   并在并列时优先截断桶召回）；选出后**只在 `val_v3_test` 上报**（沿用 W6 协议）。

## 输出

- `v2/w1_probs_{tune,test}.csv`：逐行概率缓存（两种模式），供后续复用，避免重复占用 GPU；
- `v2/w1_hybrid_result.json`：选定阈值、test 整体与分桶指标、与 A/B/C 的对照；
- 控制台与 JSON 中同时给出**截断桶召回是否达到 DoD（≥70%）**的判定。

用法：
    python v2_w1_hybrid.py --model v2/model_maxlen128 [--skip-cache]
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import sys

import numpy as np
import torch
from sklearn.metrics import precision_recall_fscore_support
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_w1_longtext import load_csv_texts, predict  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TUNE = os.path.join(HERE, "val_v3_tune.csv")
TEST = os.path.join(HERE, "val_v3_test.csv")
SHORT_MAX = 128          # 分档边界（token）
SEG_LEN, STRIDE = 128, 64


def m(y, p, thr):
    pred = (np.asarray(p) >= thr).astype(int)
    pr, rc, f1, _ = precision_recall_fscore_support(
        y, pred, average="binary", zero_division=0)
    tp = int(((pred == 1) & (np.asarray(y) == 1)).sum())
    fp = int(((pred == 1) & (np.asarray(y) == 0)).sum())
    fn = int(((pred == 0) & (np.asarray(y) == 1)).sum())
    return {"thr": round(float(thr), 4), "P": round(float(pr) * 100, 1),
            "R": round(float(rc) * 100, 1), "F1": round(float(f1), 4),
            "TP": tp, "FP": fp, "FN": fn}


def probs_for(tag, path, tok, model, device, cache):
    """取两种模式的逐行概率（带 CSV 缓存，避免重复占用 GPU）。"""
    if os.path.isfile(cache):
        texts, labels, tl, ptr, pseg = [], [], [], [], []
        with open(cache, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                texts.append(r["text"])
                labels.append(int(r["label"]))
                tl.append(int(r["tokens"]))
                ptr.append(float(r["p_trunc"]))
                pseg.append(float(r["p_seg"]))
        print(f"[{tag}] 命中缓存 {os.path.basename(cache)}：n={len(texts)}")
        return texts, labels, tl, ptr, pseg
    texts, labels = load_csv_texts(path)
    tl = [len(tok(t, add_special_tokens=False)["input_ids"]) for t in texts]
    ptr = predict(model, tok, texts, SHORT_MAX, "truncate", SHORT_MAX, STRIDE, device)
    print(f"[{tag}] 截断推理完成；开始切窗推理（seg={SEG_LEN}, stride={STRIDE}）…")
    pseg = predict(model, tok, texts, SEG_LEN, "segment", SEG_LEN, STRIDE, device)
    with open(cache, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["text", "label", "tokens", "p_trunc", "p_seg"])
        for i in range(len(texts)):
            w.writerow([texts[i], labels[i], tl[i], f"{ptr[i]:.6f}", f"{pseg[i]:.6f}"])
    print(f"[{tag}] 概率已缓存 → {os.path.basename(cache)}")
    return texts, labels, tl, ptr, pseg


def hybrid_probs(tl, ptr, pseg, thr_short, thr_long):
    """混合概率：短档用截断概率、长档用切窗概率；返回"以阈值比较用"的等价分数。

    实现方式：直接把两档概率按各自阈值归一化到 0/1 —— 即返回布尔判定后再算指标，
    因此这里返回 (probs, thrs) 供 m() 使用：短档概率配 thr_short、长档配 thr_long。
    """
    out = np.array(ptr, dtype=float)
    for i, L in enumerate(tl):
        if L > SHORT_MAX:
            out[i] = pseg[i]
    return out, [thr_short if L <= SHORT_MAX else thr_long for L in tl]


def metrics_hybrid(y, probs, thrs):
    pred = np.array([1 if probs[i] >= thrs[i] else 0 for i in range(len(probs))])
    y = np.asarray(y)
    pr, rc, f1, _ = precision_recall_fscore_support(y, pred, average="binary",
                                                    zero_division=0)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    return {"P": round(float(pr) * 100, 1), "R": round(float(rc) * 100, 1),
            "F1": round(float(f1), 4), "TP": tp, "FP": fp, "FN": fn}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.path.join(HERE, "v2", "model_maxlen128"))
    ap.add_argument("--grid", default="0.5,0.6,0.7,0.8,0.9,0.95")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = DistilBertTokenizer.from_pretrained(args.model)
    model = DistilBertForSequenceClassification.from_pretrained(
        args.model).to(device).eval()
    grid = [float(x) for x in args.grid.split(",")]

    data = {}
    for tag, path in (("tune", TUNE), ("test", TEST)):
        cache = os.path.join(HERE, "v2", f"w1_probs_{tag}.csv")
        data[tag] = probs_for(tag, path, tok, model, device, cache)

    # ---- 在 tune 上做两档阈值网格搜索 ----
    _, y, tl, ptr, pseg = data["tune"]
    best = None
    for ts, tlg in itertools.product(grid, grid):
        probs, thrs = hybrid_probs(tl, ptr, pseg, ts, tlg)
        mt = metrics_hybrid(y, probs, thrs)
        # 长档召回作为并列时的优先项
        idx = [i for i, L in enumerate(tl) if L > SHORT_MAX and y[i] == 1]
        rec_long = (sum(1 for i in idx if probs[i] >= thrs[i]) / len(idx) * 100
                    if idx else 0.0)
        key = (mt["F1"], rec_long)
        if best is None or key > best[0]:
            best = (key, ts, tlg, mt, rec_long)
    _, ts, tlg, mt_tune, rec_tune = best
    print(f"[tune 选中] 短档阈值 {ts}／长档阈值 {tlg} → tune F1 {mt_tune['F1']}、"
          f"长档召回 {rec_tune:.1f}%")

    # ---- 在 test 上报 ----
    _, y2, tl2, ptr2, pseg2 = data["test"]
    probs2, thrs2 = hybrid_probs(tl2, ptr2, pseg2, ts, tlg)
    overall = metrics_hybrid(y2, probs2, thrs2)
    buckets = {}
    for lo, hi, name in ((0, 128, "≤128"), (129, 10 ** 9, ">128 token")):
        idx = [i for i, L in enumerate(tl2) if lo <= L <= hi]
        if not idx:
            continue
        sub_y = [y2[i] for i in idx]
        sub_p = np.array([probs2[i] for i in idx])
        sub_t = [thrs2[i] for i in idx]
        buckets[name] = {"n": len(idx), "pos": int(sum(sub_y)),
                         **metrics_hybrid(sub_y, sub_p, sub_t)}
        print(f"  桶 {name}: n={len(idx)} pos={sum(sub_y)} F1 {buckets[name]['F1']} "
              f"R {buckets[name]['R']}%")

    dod = {"truncated_bucket_recall": buckets.get(">128 token", {}).get("R"),
           "threshold": 70.0}
    dod["pass"] = (dod["truncated_bucket_recall"] or 0) >= dod["threshold"]
    print(f"[DoD] 截断桶召回 {dod['truncated_bucket_recall']}% vs 验收线 "
          f"{dod['threshold']}% → {'通过' if dod['pass'] else '未通过'}")

    out = {"protocol": "短档(≤128 token)截断 + 长档(>128 token)切窗 + 两档各自在 tune 选阈值",
           "model": os.path.relpath(args.model, HERE), "gen": "[v2]",
           "chosen": {"thr_short": ts, "thr_long": tlg, "tune_overall": mt_tune,
                      "tune_long_recall": round(rec_tune, 1)},
           "test_overall": overall, "test_buckets": buckets, "dod": dod}
    with open(os.path.join(HERE, "v2", "w1_hybrid_result.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("[写出] v2/w1_hybrid_result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
