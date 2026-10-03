# -*- coding: utf-8 -*-
"""① 用**本地**品类模型（v2/model_scope）重测 40 条人工告警上的精确率增益；
② 生成 **100 条分层人工验证卡**（Arm A 触发 50 ＋ Arm B 未触发 50），
   抽样框 = 闸门内 ∧ 本地品类判耳机（即**出厂实际服务的总体**）。

Arm A 测**精确率**；Arm B 测**召回**（未触发里有没有真音质抱怨）。
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
HP = {"headphone", "earbud", "headset"}
CATS = ["headphone", "earbud", "headset", "speaker", "soundbar", "other_audio",
        "cable", "non_audio", "unclear"]
SEED = 20261009


def load_mod(n, p):
    spec = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


import torch  # noqa: E402
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer  # noqa: E402

mgs = load_mod("mgs", os.path.join(HERE, "make_gold_set.py"))
texts = []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))

dev = "cuda" if torch.cuda.is_available() else "cpu"
stok = DistilBertTokenizer.from_pretrained(os.path.join(HERE, "v2", "model_scope"))
smod = DistilBertForSequenceClassification.from_pretrained(
    os.path.join(HERE, "v2", "model_scope")).to(dev).eval()


def scope_of(idx_list):
    out = []
    with torch.no_grad():
        for b in range(0, len(idx_list), 64):
            batch = [texts[i] for i in idx_list[b:b + 64]]
            e = stok(batch, padding=True, truncation=True, max_length=192, return_tensors="pt")
            e = {k: v.to(dev) for k, v in e.items()}
            out += [CATS[k] for k in smod(**e).logits.argmax(-1).cpu().tolist()]
    return out


# ---------- ① 本地品类模型在 40 条人工告警上的增益 ----------
att, cur = {}, None
for ln in open(os.path.join(HERE, "docs/gold_set/answer_sheet_attribution.md"),
               encoding="utf-8", errors="replace"):
    t = ln.strip()
    m = re.match(r"^#{2,4}\s*(B\d{2})\b", t)
    if m:
        cur = m.group(1)
        continue
    if cur and "归因（决策方填" in t:
        mm = re.search(r"`([^`]*)`", t)
        att[cur] = 1 if re.search(r"[1-5]", mm.group(1) if mm else "") else 0
gc, cur = {}, None
for ln in open(os.path.join(HERE, "docs/gold_set/answer_sheet_clean_alerts.md"),
               encoding="utf-8", errors="replace"):
    t = ln.strip()
    m = re.match(r"^#{2,4}\s*(K\d{3})\b", t)
    if m:
        cur = m.group(1)
        continue
    if cur and "判定（决策方填" in t:
        mm = re.search(r"`([^`]*)`", t)
        gc[cur] = (mm.group(1) if mm else "").strip()
items = []
with open(os.path.join(HERE, "docs/gold_set/attribution_test.csv"),
          encoding="utf-8-sig", errors="replace") as fh:
    for r in csv.DictReader(fh):
        if r["臂"] == "B" and r["编号"] in att:
            items.append({"uid": r["编号"], "i": int(r["row_index"]), "y": att[r["编号"]]})
with open(os.path.join(HERE, "docs/gold_set/clean_alerts.csv"),
          encoding="utf-8-sig", errors="replace") as fh:
    for r in csv.DictReader(fh):
        if r["臂"] == "alert" and r["编号"] in gc:
            items.append({"uid": r["编号"], "i": int(r["row_index"]),
                          "y": 1 if "1" in gc[r["编号"]] else 0})
for x, c in zip(items, scope_of([x["i"] for x in items])):
    x["scope"] = c
k_all = sum(x["y"] for x in items)
hp = [x for x in items if x["scope"] in HP]
k_hp = sum(x["y"] for x in hp)
print(f"① 本地品类模型在 40 条人工告警上：全部 {k_all}/{len(items)} = "
      f"{k_all/len(items)*100:.1f}%｜**仅耳机家族 {k_hp}/{len(hp)} = "
      f"{k_hp/max(1,len(hp))*100:.1f}%**")

# ---------- ② 100 条分层验证卡（出厂总体 = 闸门内 ∧ 品类判耳机）----------
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
judged = set()
for it in json.load(open(os.path.join(HERE, "v2", "gold_set_key.json"),
                         encoding="utf-8"))["items"]:
    judged.add(it["row_index"])
judged |= set(json.load(open(os.path.join(HERE, "v2", "s1_add100_ids.json"),
                             encoding="utf-8")).get("row_index", []))
for f in ("docs/gold_set/s5_clean_probe.csv", "docs/gold_set/clean_alerts.csv",
          "docs/gold_set/vocab_test.csv", "docs/gold_set/attribution_test.csv"):
    with open(os.path.join(HERE, f), encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if str(r.get("row_index", "")).strip():
                judged.add(int(r["row_index"]))
pool = [i for i in range(len(texts))
        if i not in judged and len(texts[i]) >= 40 and mgs.RX.search(texts[i])]
rng = random.Random(SEED)
rng.shuffle(pool)
pool = pool[:4000]
sc = scope_of(pool)
served = [i for i, c in zip(pool, sc) if c in HP]
print(f"② 出厂总体（闸门内 ∧ 品类判耳机）候选：{len(served):,} 条")
sc2 = scope_of(served)
rwe = load_mod("rwe", os.path.join(HERE, "realworld_eval.py"))
probs = rwe.predict([texts[i] for i in served], cfg["bin_model_dir"], 128)
fired = [i for i, p in zip(served, probs) if p >= float(cfg.get("tier_low", 0.5))]
notf = [i for i, p in zip(served, probs) if p < float(cfg.get("tier_low", 0.5))]
rng.shuffle(fired)
rng.shuffle(notf)
armA, armB = fired[:50], notf[:50]
print(f"   Arm A（触发）{len(armA)} 条｜Arm B（未触发）{len(armB)} 条")
