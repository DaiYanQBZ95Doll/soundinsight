# -*- coding: utf-8 -*-
"""高音路径实验：把新筛出的在范围内正例并入，**复刻 train_multilabel.py 的同配置**重训，
在冻结测试集 val_v3_test 上比较逐类 F1（重点：treble）。

不带任何"已采纳"含义——**实验产物写往 v2/exp_treble/**，不触碰交付用的 multi_label_model/。

用法：python treble_experiment.py [--augment] [--epochs 4]
  · 不带 --augment：基线复跑（用同一实现，控制实现差异）
  · 带 --augment ：并入 135 条新正例（其中 69 条带 treble 标签）
"""
from __future__ import annotations

import argparse
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

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
BASE_MODEL = "distilbert-base-uncased"
CLASSES = ["bass", "clarity", "noise", "volume", "treble"]
SEED, EPOCHS, BS, LR, MAX_LEN = 42, 4, 16, 2e-5, 128


def load_train(augment: bool):
    texts, labels = [], []
    pos_idx = []
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8",
              errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    for i, r in enumerate(rows):
        if str(r.get("sound_negative_llm")) == "1":
            pos_idx.append(i)
    cand = json.load(open(os.path.join(HERE, "v2", "treble_candidates.json"),
                          encoding="utf-8"))
    new_idx = [int(x) for x in cand["train_split_new"]] if augment else []
    use = sorted(set(pos_idx) | set(new_idx))
    extra = f" + 新增 {len(new_idx)}" if augment else ""
    print(f"训练正例：原有 {len(pos_idx)}{extra} = {len(use)}")
    X = [str(rows[i].get("text") or "") for i in use]
    Y = []
    for i in use:
        Y.append([1 if str(rows[i].get(f"issue_{c}_llm")) == "1" else 0 for c in CLASSES])
    Y = np.array(Y)
    print("  逐类：" + "｜".join(f"{c} {int(Y[:, k].sum())}" for k, c in enumerate(CLASSES)))
    return X, Y


def load_test():
    """测试集＝`val_v3_test.csv`（冻结）；其标签列名为 `sound_negative`（非 `_llm` 后缀）。"""
    texts, Y = [], []
    with open(os.path.join(HERE, "val_v3_test.csv"), encoding="utf-8",
              errors="replace") as fh:
        for r in csv.DictReader(fh):
            if str(r.get("sound_negative")) != "1":
                continue
            texts.append(str(r.get("text") or ""))
            Y.append([1 if str(r.get(f"issue_{c}_llm")) == "1" else 0 for c in CLASSES])
    Y = np.array(Y)
    print(f"测试集（val_v3_test 正例）{len(texts)} 条｜逐类："
          + "｜".join(f"{c} {int(Y[:, k].sum())}" for k, c in enumerate(CLASSES)))
    return texts, Y


def prf(y, p):
    tp = int(((p == 1) & (y == 1)).sum())
    fp = int(((p == 1) & (y == 0)).sum())
    fn = int(((p == 0) & (y == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return round(prec, 4), round(rec, 4), round(f1, 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--augment", action="store_true")
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    args = ap.parse_args()
    tag = "aug" if args.augment else "base"
    out_dir = os.path.join(HERE, "v2", f"exp_treble_{tag}")
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={dev}｜tag={tag}｜epochs={args.epochs}")

    X, Y = load_train(args.augment)
    tok = DistilBertTokenizer.from_pretrained(BASE_MODEL)
    enc = tok(X, truncation=True, max_length=MAX_LEN, padding=True, return_tensors="pt")
    ds = TensorDataset(enc["input_ids"], enc["attention_mask"], torch.tensor(Y, dtype=torch.float))
    dl = DataLoader(ds, batch_size=BS, shuffle=True)
    torch.manual_seed(SEED)
    model = DistilBertForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=len(CLASSES),
        problem_type="multi_label_classification").to(dev)
    opt = AdamW(model.parameters(), lr=LR)
    t0 = time.time()
    for ep in range(args.epochs):
        model.train()
        tot = 0.0
        for ids, att, y in dl:
            ids, att, y = ids.to(dev), att.to(dev), y.to(dev)
            out = model(input_ids=ids, attention_mask=att, labels=y)
            out.loss.backward()
            opt.step()
            opt.zero_grad()
            tot += float(out.loss)
        print(f"  [epoch {ep+1}] loss={tot/max(len(dl),1):.4f}｜{time.time()-t0:.0f}s")
    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    print(f"[保存] {out_dir}（实验产物，不用于交付）")

    Xt, Yt = load_test()
    model.eval()
    probs = []
    with torch.no_grad():
        for i in range(0, len(Xt), 64):
            e = tok(Xt[i:i + 64], truncation=True, max_length=MAX_LEN, padding=True,
                    return_tensors="pt")
            probs.append(torch.sigmoid(model(**{k: v.to(dev) for k, v in e.items()}).logits)
                         .cpu().numpy())
    P = np.vstack(probs)

    print(f"\n=== 结果（{tag}）===")
    res = {"tag": tag, "epochs": args.epochs, "classes": {}, "macro_f1_at_0.5": None}
    for k, c in enumerate(CLASSES):
        prec, rec, f1 = prf(Yt[:, k], (P[:, k] >= 0.5).astype(int))
        res["classes"][c] = {"P": prec, "R": rec, "F1@0.5": f1,
                             "test_pos": int(Yt[:, k].sum())}
        print(f"  {c:<8} P {prec:.3f}｜R {rec:.3f}｜F1@0.5 {f1:.4f}（测试正例 {int(Yt[:, k].sum())}）")
    res["macro_f1_at_0.5"] = round(sum(v["F1@0.5"] for v in res["classes"].values()) / 5, 4)
    print(f"  宏 F1@0.5 = {res['macro_f1_at_0.5']}")
    json.dump(res, open(os.path.join(HERE, "v2", f"exp_treble_{tag}.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[写出] v2/exp_treble_{tag}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
