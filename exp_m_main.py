# -*- coding: utf-8 -*-
"""本文方法 M：在**冻结划分**上从零微调 DistilBERT（二分类：是否音质抱怨）。

关键设计：
  · 底座＝**本地未微调的** ./distilbert-base-uncased（255 MB）——**绝不**用竞赛期微调权重当底座，
    否则旧划分的语料会污染新 test 侧；
  · 数据＝v2/thesis_split.json 的 train/val/test（主标签 sound_negative_llm）；
  · 变体（消融 A2）：
      --variant base ：仅用 train 划分
      --variant hard ：额外注入**硬负例**（P1 标注中 sound_complaint=0 但被闸门命中、
                       且属"功能故障提及声音/弱褒奖"的条目）——即竞赛期"判别器"思路；
  · 固定种子；保存 val/test 概率供统一评测台与 McNemar 使用。

用法：python exp_m_main.py --variant hard --epochs 3
产物：v2/model_thesis_{base,hard}/、v2/exp_m{base,hard}_{val,test}.json、*_config.json
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch.utils.data import DataLoader, Dataset  # noqa: E402
from transformers import (DistilBertForSequenceClassification,  # noqa: E402
                          DistilBertTokenizer)

HARD_TYPES = ("功能故障", "弱褒奖", "无抱怨")   # P1 的 types 字段关键字


def load_hard_negative_indices() -> set[int]:
    """P1 中 sound_complaint=0 且属功能故障/弱褒奖的条目（用作硬负例）。"""
    idx = set()
    p = os.path.join(HERE, "v2", "p1_labels.jsonl")
    if not os.path.isfile(p):
        return idx
    for line in open(p, encoding="utf-8", errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if str(r.get("sound_complaint")) != "0":
            continue
        types = str(r.get("types") or "")
        if any(k in types for k in HARD_TYPES):
            try:
                idx.add(int(r["row_index"]))
            except (KeyError, ValueError):
                pass
    return idx


class DS(Dataset):
    def __init__(self, texts, labels, tok, max_len):
        self.enc = tok(texts, padding=True, truncation=True, max_length=max_len,
                       return_tensors="pt")
        self.y = torch.tensor(labels, dtype=torch.long)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        return {k: v[i] for k, v in self.enc.items()}, self.y[i]


def predict(model, tok, texts, dev, max_len=256, bs=64):
    model.eval()
    out = []
    with torch.no_grad():
        for b in range(0, len(texts), bs):
            e = tok(texts[b:b + bs], padding=True, truncation=True, max_length=max_len,
                    return_tensors="pt")
            e = {k: v.to(dev) for k, v in e.items()}
            out += torch.softmax(model(**e).logits, -1)[:, 1].cpu().tolist()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["base", "hard"], default="hard")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max_len", type=int, default=256)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    random.seed(a.seed)
    np.random.seed(a.seed)
    torch.manual_seed(a.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(a.seed)

    sp = json.load(open(os.path.join(HERE, "v2", "thesis_split.json"), encoding="utf-8"))
    texts, labels = {}, {}
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            texts[i] = r["text"]
            labels[i] = 1 if str(r.get("sound_negative_llm")) == "1" else 0

    tr_idx = list(sp["row_index"]["train"])
    hard = load_hard_negative_indices()
    if a.variant == "hard":
        extra = [i for i in sorted(hard) if i in texts and labels.get(i) == 0]
        tr_idx = tr_idx + extra
        print(f"  硬负例注入 {len(extra)} 条（P1: 功能故障/弱褒奖且闸门内）")
    else:
        print("  不使用硬负例")

    Xtr = [texts[i] for i in tr_idx]
    ytr = [labels[i] for i in tr_idx]
    Xva = [texts[i] for i in sp["row_index"]["val"]]
    Xte = [texts[i] for i in sp["row_index"]["test"]]
    print(f"  train {len(Xtr)}（正 {sum(ytr)}）｜val {len(Xva)}｜test {len(Xte)}")

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    base = os.path.join(HERE, "distilbert-base-uncased")
    tok = DistilBertTokenizer.from_pretrained(base)
    model = DistilBertForSequenceClassification.from_pretrained(base, num_labels=2).to(dev)
    print(f"  底座 {os.path.relpath(base, HERE)}（未微调）｜设备 {dev}")

    ds = DS(Xtr, ytr, tok, a.max_len)
    dl = DataLoader(ds, batch_size=a.batch, shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr)
    t0 = time.time()
    for ep in range(a.epochs):
        model.train()
        tot = 0.0
        for xb, yb in dl:
            xb = {k: v.to(dev) for k, v in xb.items()}
            yb = yb.to(dev)
            out = model(**xb, labels=yb)
            out.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            opt.zero_grad()
            tot += float(out.loss)
        print(f"    epoch {ep+1}/{a.epochs}｜loss {tot/max(1,len(dl)):.4f}"
              f"｜{time.time()-t0:.0f}s")

    outdir = os.path.join(HERE, "v2", f"model_thesis_{a.variant}")
    model.save_pretrained(outdir)
    tok.save_pretrained(outdir)
    pv = predict(model, tok, Xva, dev, a.max_len)
    pt = predict(model, tok, Xte, dev, a.max_len)
    json.dump({str(i): float(p) for i, p in zip(sp["row_index"]["val"], pv)},
              open(os.path.join(HERE, "v2", f"exp_m{a.variant}_val.json"), "w",
                   encoding="utf-8"))
    json.dump({str(i): float(p) for i, p in zip(sp["row_index"]["test"], pt)},
              open(os.path.join(HERE, "v2", f"exp_m{a.variant}_test.json"), "w",
                   encoding="utf-8"))
    json.dump({"variant": a.variant, "base": "distilbert-base-uncased（本地未微调）",
               "epochs": a.epochs, "lr": a.lr, "batch": a.batch, "max_len": a.max_len,
               "seed": a.seed, "n_train": len(Xtr), "n_pos": int(sum(ytr)),
               "hard_negatives": (len(tr_idx) - len(sp["row_index"]["train"])
                                  if a.variant == "hard" else 0),
               "train_seconds": round(time.time() - t0, 1), "device": dev},
              open(os.path.join(HERE, "v2", f"exp_m{a.variant}_config.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  [写出] v2/model_thesis_{a.variant}/、exp_m{a.variant}_{{val,test}}.json"
          f"｜训练 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
