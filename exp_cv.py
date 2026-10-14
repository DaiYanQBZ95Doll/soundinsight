# -*- coding: utf-8 -*-
"""K 折交叉验证：为**每一个**闸门内条目取得袋外（out-of-fold）预测，解决留出集功效不足。

动机（2026-10-14 实测）：留出测试集只有 1,264 条 / 120 正例，B2 与本文方法的 McNemar
p=0.129（**未观察到显著差异**）——不是方法无差，而是**功效不足**。用 5 折 CV 让 12,621 条
全部进入配对比较（正例约 1,200），显著提升检验功效。

用法：
    python exp_cv.py --method b2 --folds 5          # TF-IDF + LogReg（快）
    python exp_cv.py --method m  --folds 5          # DistilBERT（每折约 17 分钟）
产物：v2/cv_{method}_oof.json（{row_index: prob}）、v2/cv_{method}_summary.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

import numpy as np  # noqa: E402


def folds_of(pool, k, seed=42):
    """按内容哈希排序后轮流分折（与行序无关，可复现）。"""
    order = sorted(pool, key=lambda i: hashlib.sha1(f"cv{seed}:{i}".encode()).hexdigest())
    return [order[j::k] for j in range(k)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["b2", "m"], required=True)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=3)
    a = ap.parse_args()

    sp = json.load(open(os.path.join(HERE, "v2", "thesis_split.json"), encoding="utf-8"))
    texts, labels = {}, {}
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            texts[i] = r["text"]
            labels[i] = 1 if str(r.get("sound_negative_llm")) == "1" else 0
    pool = [i for k in ("train", "val", "test") for i in sp["row_index"][k]]
    print(f"  CV 池：{len(pool):,} 条（正例 {sum(labels[i] for i in pool):,}）｜{a.folds} 折")
    fold_list = folds_of(pool, a.folds)
    oof = {}
    t0 = time.time()
    for f, test_idx in enumerate(fold_list, 1):
        train_idx = [i for i in pool if i not in set(test_idx)]
        ytr = np.array([labels[i] for i in train_idx])
        if a.method == "b2":
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression
            vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True,
                                  strip_accents="unicode", max_features=400000)
            Xtr = vec.fit_transform([texts[i] for i in train_idx])
            Xte = vec.transform([texts[i] for i in test_idx])
            clf = LogisticRegression(class_weight="balanced", C=4.0, max_iter=3000,
                                     solver="liblinear")
            clf.fit(Xtr, ytr)
            p = clf.predict_proba(Xte)[:, 1]
        else:
            import torch
            from transformers import (DistilBertForSequenceClassification,
                                      DistilBertTokenizer)
            dev = "cuda" if torch.cuda.is_available() else "cpu"
            torch.manual_seed(42)
            base = os.path.join(HERE, "distilbert-base-uncased")
            tok = DistilBertTokenizer.from_pretrained(base)
            model = DistilBertForSequenceClassification.from_pretrained(
                base, num_labels=2).to(dev)
            from torch.utils.data import DataLoader
            enc = tok([texts[i] for i in train_idx], padding=True, truncation=True,
                      max_length=256, return_tensors="pt")
            ds = torch.utils.data.TensorDataset(enc["input_ids"], enc["attention_mask"],
                                                torch.tensor([labels[i] for i in train_idx]))
            dl = DataLoader(ds, batch_size=32, shuffle=True)
            opt = torch.optim.AdamW(model.parameters(), lr=2e-5)
            model.train()
            for ep in range(a.epochs):
                for ids, am, yb in dl:
                    out = model(input_ids=ids.to(dev), attention_mask=am.to(dev),
                                labels=yb.to(dev))
                    out.loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    opt.step()
                    opt.zero_grad()
                print(f"    折 {f} epoch {ep+1}/{a.epochs}｜{time.time()-t0:.0f}s")
            model.eval()
            p = []
            with torch.no_grad():
                for b in range(0, len(test_idx), 64):
                    e = tok([texts[i] for i in test_idx[b:b + 64]], padding=True,
                            truncation=True, max_length=256, return_tensors="pt")
                    e = {k: v.to(dev) for k, v in e.items()}
                    p += torch.softmax(model(**e).logits, -1)[:, 1].cpu().tolist()
        for i, q in zip(test_idx, p):
            oof[str(i)] = float(q)
        print(f"  折 {f}/{a.folds} 完成（{len(test_idx)} 条）｜累计 {time.time()-t0:.0f}s")

    json.dump(oof, open(os.path.join(HERE, "v2", f"cv_{a.method}_oof.json"), "w",
                        encoding="utf-8"))
    # 在 OOF 预测上算整体指标（与留出集同一套口径）
    y = [labels[int(i)] for i in oof]
    p = [oof[i] for i in oof]
    tp = sum(1 for a_, b_ in zip(y, p) if a_ == 1 and b_ >= 0.5)
    fp = sum(1 for a_, b_ in zip(y, p) if a_ == 0 and b_ >= 0.5)
    fn = sum(1 for a_, b_ in zip(y, p) if a_ == 1 and b_ < 0.5)
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    F1 = 2 * P * R / (P + R) if P + R else 0.0
    print(f"\n[CV-OOF 整体] n={len(y):,}｜正例 {sum(y)}｜P {P*100:.1f}%｜R {R*100:.1f}%"
          f"｜F1 {F1*100:.1f}%｜TP{tp}/FP{fp}/FN{fn}")
    json.dump({"method": a.method, "folds": a.folds, "n": len(y), "pos": int(sum(y)),
               "P": round(P, 4), "R": round(R, 4), "F1": round(F1, 4),
               "tp": tp, "fp": fp, "fn": fn, "seconds": round(time.time() - t0, 1)},
              open(os.path.join(HERE, "v2", f"cv_{a.method}_summary.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  [写出] v2/cv_{a.method}_oof.json、cv_{a.method}_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
