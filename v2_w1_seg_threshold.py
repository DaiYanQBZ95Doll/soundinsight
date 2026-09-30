# -*- coding: utf-8 -*-
"""W1 变体 C 的阈值重调：切窗推理的分数分布上移，必须在 tune 上重选阈值。

背景（2026-09-30 实测）：
- `max_len=128` 截断推理：val_v3_test 整体 F1@0.5 0.7077；截断桶（>128 token）召回 51.2%；
- 同模型**切窗推理**（seg=128/stride=64，取窗口最大概率）：**截断桶召回升到 82.9%**，
  但整体精确率从 69.7% 掉到 47.7%（FP 40 → 115）——因为"取最大"抬高了长文本的分数，
  0.5 这个阈值不再适用。

本脚本按既定协议处理该问题：**阈值只在 `val_v3_tune` 上选，指标只在 `val_v3_test` 上报**。
输出：`v2/w1_seg_threshold.json` + 控制台对比表（截断推理 vs 切窗推理，各自的最优阈值与 test 指标）。

用法：python v2_w1_seg_threshold.py --model v2/model_maxlen128 --seg-len 128 --stride 64
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import torch
from sklearn.metrics import precision_recall_fscore_support
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_w1_longtext import BUCKETS, load_csv_texts, predict  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TUNE = os.path.join(HERE, "val_v3_tune.csv")
TEST = os.path.join(HERE, "val_v3_test.csv")


def metrics(y, p, thr):
    pred = (np.asarray(p) >= thr).astype(int)
    pr, rc, f1, _ = precision_recall_fscore_support(
        y, pred, average="binary", zero_division=0)
    tp = int(((pred == 1) & (np.asarray(y) == 1)).sum())
    fp = int(((pred == 1) & (np.asarray(y) == 0)).sum())
    fn = int(((pred == 0) & (np.asarray(y) == 1)).sum())
    return {"thr": round(float(thr), 4), "P": round(float(pr) * 100, 1),
            "R": round(float(rc) * 100, 1), "F1": round(float(f1), 4),
            "TP": tp, "FP": fp, "FN": fn}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.path.join(HERE, "v2", "model_maxlen128"))
    ap.add_argument("--seg-len", type=int, default=128)
    ap.add_argument("--stride", type=int, default=64)
    ap.add_argument("--grid", default="0.3,0.4,0.5,0.6,0.7,0.8,0.9,0.95,0.9744,0.99")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = DistilBertTokenizer.from_pretrained(args.model)
    model = DistilBertForSequenceClassification.from_pretrained(
        args.model).to(device).eval()
    grid = [float(x) for x in args.grid.split(",")]

    out = {"protocol": "阈值在 val_v3_tune 上选、指标在 val_v3_test 上报",
           "model": os.path.relpath(args.model, HERE),
           "mode": f"segment(seg={args.seg_len},stride={args.stride})", "gen": "[v2]"}
    probs = {}
    for tag, path in (("tune", TUNE), ("test", TEST)):
        texts, labels = load_csv_texts(path)
        tl = [len(tok(t, add_special_tokens=False)["input_ids"]) for t in texts]
        pr = predict(model, tok, texts, args.seg_len, "segment",
                     args.seg_len, args.stride, device)
        probs[tag] = {"y": labels, "p": pr, "len": tl}
        print(f"{tag}: n={len(texts)} 正例={sum(labels)}")

    # 1) 在 tune 上选阈值
    best = None
    for thr in grid:
        m = metrics(probs["tune"]["y"], probs["tune"]["p"], thr)
        if best is None or m["F1"] > best["F1"]:
            best = m
    print(f"[tune 选中阈值] {best['thr']}（tune F1 {best['F1']}）")

    # 2) 在 test 上报（切窗 + 该阈值），并与截断推理对照
    row_seg = metrics(probs["test"]["y"], probs["test"]["p"], best["thr"])
    row_seg_05 = metrics(probs["test"]["y"], probs["test"]["p"], 0.5)
    print(f"[test/切窗@{best['thr']}] P {row_seg['P']}% R {row_seg['R']}% "
          f"F1 {row_seg['F1']} (TP{row_seg['TP']}/FP{row_seg['FP']}/FN{row_seg['FN']})")
    print(f"[test/切窗@0.5 ] P {row_seg_05['P']}% R {row_seg_05['R']}% "
          f"F1 {row_seg_05['F1']}")

    # 分桶（用选中阈值）
    buckets = {}
    for lo, hi, name in BUCKETS:
        idx = [k for k, L in enumerate(probs["test"]["len"]) if lo <= L <= hi]
        if not idx:
            continue
        y = [probs["test"]["y"][k] for k in idx]
        p = [probs["test"]["p"][k] for k in idx]
        if sum(1 for v in y if v == 1) == 0:
            buckets[name] = {"n": len(idx), "pos": 0}
            continue
        buckets[name] = {"n": len(idx), "pos": int(sum(y)),
                         **metrics(y, p, best["thr"])}
        print(f"    桶 {name}: n={len(idx)} pos={sum(y)} F1 {buckets[name]['F1']} "
              f"R {buckets[name]['R']}%")

    out.update({"tune_best": best, "test_at_tuned": row_seg,
                "test_at_0.5": row_seg_05, "test_buckets": buckets})
    with open(os.path.join(HERE, "v2", "w1_seg_threshold.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("[写出] v2/w1_seg_threshold.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
