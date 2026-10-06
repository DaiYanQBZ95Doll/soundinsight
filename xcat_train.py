# -*- coding: utf-8 -*-
"""跨品类试点：音箱音质抱怨模型（底座＝出厂判别器，验证"音频域能否迁移"）。

评价：冻结留出集（612 条／正例 47）上的 P/R/F1@0.5–0.9；人工锚＝mini 金标（确认率 96.6%）。
"""
from __future__ import annotations

import csv
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = json.load(open(os.path.join(HERE, "v2", "xcat_speaker_split.json"), encoding="utf-8"))
OUT = os.path.join(HERE, "v2", "model_xcat_speaker")
BASE = os.path.join(HERE, "sound_model")

texts = []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
pos = set()
for line in open(os.path.join(HERE, "v2", "p1_labels.jsonl"), encoding="utf-8",
                 errors="replace"):
    try:
        rec = json.loads(line)
    except ValueError:
        continue
    if int(rec.get("sound_complaint") or 0) == 1:
        pos.add(int(rec["row_index"]))
got, _ = None, None
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("rio", os.path.join(HERE, "rulings_io.py"))
rio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rio)
meta = json.load(open(os.path.join(HERE, "v2", "xcat_mini_ids.json"), encoding="utf-8"))
got, _amb = rio.read_judgements(os.path.join(HERE, "docs/gold_set/answer_sheet_xcat_mini.md"))
for u, i in zip(meta["ids"], meta["row_index"]):
    if got.get(u) == "0":
        pos.discard(i)

tr = SPLIT["train_row_index"]
te = SPLIT["holdout_row_index"]
y = {i: (1 if i in pos else 0) for i in tr + te}
print(f"训练 {len(tr):,}（正例 {sum(y[i] for i in tr)}）｜留出 {len(te):,}"
      f"（正例 {sum(y[i] for i in te)}）")

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch.optim import AdamW  # noqa: E402
from torch.utils.data import DataLoader, TensorDataset  # noqa: E402
from transformers import (DistilBertForSequenceClassification,  # noqa: E402
                          DistilBertTokenizer)

dev = "cuda" if torch.cuda.is_available() else "cpu"
tok = DistilBertTokenizer.from_pretrained(BASE)
enc = tok([texts[i] for i in tr], truncation=True, max_length=256, padding=True,
          return_tensors="pt")
dl = DataLoader(TensorDataset(enc["input_ids"], enc["attention_mask"],
                              torch.tensor([y[i] for i in tr])), batch_size=16, shuffle=True)
torch.manual_seed(42)
model = DistilBertForSequenceClassification.from_pretrained(BASE, num_labels=2).to(dev)
opt = AdamW(model.parameters(), lr=1.5e-5)
EPOCHS = 4
print(f"训练（{dev}，{EPOCHS} epochs，{len(dl)} steps/epoch，底座＝出厂判别器）", flush=True)
for ep in range(EPOCHS):
    model.train()
    tot = 0.0
    for k, (ids, att, yy) in enumerate(dl, 1):
        ids, att, yy = ids.to(dev), att.to(dev), yy.to(dev)
        o = model(input_ids=ids, attention_mask=att, labels=yy)
        o.loss.backward()
        opt.step()
        opt.zero_grad()
        tot += float(o.loss)
    print(f"[epoch {ep+1}] mean loss={tot/max(len(dl),1):.4f}", flush=True)
os.makedirs(OUT, exist_ok=True)
model.save_pretrained(OUT)
tok.save_pretrained(OUT)
print(f"[保存] {OUT}", flush=True)

# 评测（冻结留出集）
model.eval()
probs = []
with torch.no_grad():
    for b in range(0, len(te), 64):
        e = tok([texts[i] for i in te[b:b + 64]], padding=True, truncation=True,
                max_length=256, return_tensors="pt")
        e = {k: v.to(dev) for k, v in e.items()}
        probs += torch.softmax(model(**e).logits, -1)[:, 1].cpu().tolist()
yv = [y[i] for i in te]


def prf(thr):
    tp = sum(1 for p, t in zip(probs, yv) if p >= thr and t == 1)
    fp = sum(1 for p, t in zip(probs, yv) if p >= thr and t == 0)
    fn = sum(1 for p, t in zip(probs, yv) if p < thr and t == 1)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"P": round(p * 100, 1), "R": round(r * 100, 1), "F1": round(f, 4),
            "TP": tp, "FP": fp, "FN": fn}


res = {str(t): prf(t) for t in (0.5, 0.7, 0.9)}
for t, v in res.items():
    print(f"  @{t}：P {v['P']}／R {v['R']}／F1 {v['F1']}（TP {v['TP']}／FP {v['FP']}／FN {v['FN']}）")
json.dump({"generation": "xcat-speaker", "holdout": len(te), "pos": sum(yv),
           "metrics": res, "base": "sound_model（出厂判别器）",
           "human_anchor": "mini 金标确认率 96.6%（n=29）"},
          open(os.path.join(HERE, "v2", "xcat_speaker_eval.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[写出] v2/xcat_speaker_eval.json")
