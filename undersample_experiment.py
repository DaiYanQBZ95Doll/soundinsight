# -*- coding: utf-8 -*-
"""决定性实验（回应红队刺 3）：把 v2 的训练配方改成**与 v1 一致的 1:10 欠采样**，
在同一个 val_v3_test 上评估——以分离"窗口/标签"与"训练配方"两个变量。

对照矩阵（全部在 val_v3_test 上、阈值均在 val_v3_tune 上按同一规则选）：
  A. v1 权重（复赛产品模型）              —— 已算得 0.8043@自身阈值（**疑镜像泄漏**，见下）
  B. v2 权重（全部训练行，无欠采样）        —— 已算得 0.7220
  C. 本次重训（1:10 欠采样 + max_len 256） —— 待测

产出：`v2/exp_undersample.json`（实验，不替换交付权重）
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time

import numpy as np
import torch
from sklearn.model_selection import train_test_split
from torch.optim import AdamW
from torch.utils.data import DataLoader, TensorDataset
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_w1_longtext import predict  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "distilbert-base-uncased"
SEED, EPOCHS, BS, LR, MAX_LEN, NEG_RATIO = 42, 3, 16, 2e-5, 256, 10


def f1_from(y, pred):
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return (2 * p * r / (p + r) if p + r else 0.0), p, r


def boot(y, prob, thr, n=2000, seed=42):
    rng = np.random.default_rng(seed)
    v = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        v.append(f1_from(y[i], (prob[i] >= thr).astype(int))[0])
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def main() -> int:
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={dev}｜欠采样 1:{NEG_RATIO}｜max_len={MAX_LEN}｜epochs={EPOCHS}")
    texts, labels = [], []
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8",
              errors="replace") as fh:
        for r in csv.DictReader(fh):
            texts.append(str(r.get("text") or ""))
            labels.append(int(r.get("sound_negative_llm") or 0))
    idx = list(range(len(texts)))
    i_tr, _ = train_test_split(idx, test_size=0.2, random_state=SEED, stratify=labels)
    pos = [i for i in i_tr if labels[i] == 1]
    neg_all = [i for i in i_tr if labels[i] == 0]
    rng = np.random.default_rng(SEED)
    neg = list(rng.choice(neg_all, size=min(len(pos) * NEG_RATIO, len(neg_all)),
                          replace=False))
    use = pos + [int(x) for x in neg]
    rng.shuffle(use)
    print(f"训练集：正例 {len(pos):,} + 负例 {len(neg):,}（1:{NEG_RATIO}）")

    tok = DistilBertTokenizer.from_pretrained(BASE)
    enc = tok([texts[i] for i in use], truncation=True, max_length=MAX_LEN,
              padding=True, return_tensors="pt")
    ds = TensorDataset(enc["input_ids"], enc["attention_mask"],
                       torch.tensor([labels[i] for i in use]))
    dl = DataLoader(ds, batch_size=BS, shuffle=True)
    torch.manual_seed(SEED)
    model = DistilBertForSequenceClassification.from_pretrained(BASE, num_labels=2).to(dev)
    opt = AdamW(model.parameters(), lr=LR)
    t0 = time.time()
    for ep in range(EPOCHS):
        model.train()
        tot = 0.0
        for ids, att, y in dl:
            ids, att, y = ids.to(dev), att.to(dev), y.to(dev)
            out = model(input_ids=ids, attention_mask=att, labels=y)
            out.loss.backward()
            opt.step()
            opt.zero_grad()
            tot += float(out.loss)
        print(f"  [epoch {ep+1}] loss={tot/max(len(dl),1):.4f}（{time.time()-t0:.0f}s）")

    def rows(path):
        with open(os.path.join(HERE, path), encoding="utf-8", errors="replace") as fh:
            rs = list(csv.DictReader(fh))
        return [r["text"] for r in rs], np.array([int(r["sound_negative"]) for r in rs])

    tu_t, tu_y = rows("val_v3_tune.csv")
    te_t, te_y = rows("val_v3_test.csv")
    p_tu = np.array(predict(model, tok, tu_t, MAX_LEN, "truncate", MAX_LEN, 64, dev))
    p_te = np.array(predict(model, tok, te_t, MAX_LEN, "truncate", MAX_LEN, 64, dev))
    grid = np.arange(0.05, 0.96, 0.05)
    best = float(max(grid, key=lambda t: f1_from(tu_y, (p_tu >= t).astype(int))[0]))
    out = {"recipe": f"1:{NEG_RATIO} 欠采样", "max_len": MAX_LEN, "epochs": EPOCHS,
           "train_pos": len(pos), "train_neg": len(neg), "thr_tuned_on_tune": round(best, 2)}
    for label, thr in (("at_0.5", 0.5), ("at_tuned", best)):
        f1, pr, rc = f1_from(te_y, (p_te >= thr).astype(int))
        lo, hi = boot(te_y, p_te, thr)
        out[label] = {"thr": round(float(thr), 3), "F1": round(f1, 4),
                      "P": round(pr, 4), "R": round(rc, 4),
                      "F1_ci95": [round(lo, 4), round(hi, 4)]}
        print(f"  [欠采样 v2] {label} thr={thr:.2f} → F1 {f1:.4f}"
              f"（95% CI {lo:.4f}–{hi:.4f}）｜P {pr:.3f}｜R {rc:.3f}")
    json.dump(out, open(os.path.join(HERE, "v2", "exp_undersample.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[写出] v2/exp_undersample.json（实验产物，不替换交付权重）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
