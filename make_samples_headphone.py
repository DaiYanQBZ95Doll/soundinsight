# -*- coding: utf-8 -*-
"""重建演示样例：**耳机卖家的真实导出**（替代原先"全语料混合"的测试集）。

动机（round-04 Qwen 盲读 B3-3）：原先例的 5 个典型案例里 0 个是耳机（平板/功放/音箱），
把文档自认的"跨品类误报"缺陷放大成了门面。

设计：
  · 抽样框＝语料中**品类判为耳机家族**的评论（本地品类模型，留出段精确率 0.885）；
  · 构成＝**20 条提到音频词汇**（触发闸门，含若干音质抱怨）＋**80 条不含音频词汇**（走"未判定"）；
  · 保留原样例列结构（text / rating / 期望标签 / 类别），rating 用**语料真实评分**；
  · 种子固定，可复现。
"""
from __future__ import annotations

import collections
import csv
import importlib.util
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261015
CATS = ["headphone", "earbud", "headset", "speaker", "soundbar", "other_audio",
        "cable", "non_audio", "unclear"]
HP = {"headphone", "earbud", "headset"}


def load_mod(n, p):
    spec = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


import torch  # noqa: E402
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer  # noqa: E402

mgs = load_mod("mgs", os.path.join(HERE, "make_gold_set.py"))
texts, ratings, llm_pos = [], [], []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
        ratings.append(str(r.get("rating") or ""))
        llm_pos.append(int(float(r.get("sound_negative_llm") or 0)))
gate = [bool(mgs.RX.search(t)) for t in texts]
print(f"语料 {len(texts):,}｜闸门内 {sum(gate):,}")

dev = "cuda" if torch.cuda.is_available() else "cpu"
tok = DistilBertTokenizer.from_pretrained(os.path.join(HERE, "v2", "model_scope"))
mod = DistilBertForSequenceClassification.from_pretrained(
    os.path.join(HERE, "v2", "model_scope")).to(dev).eval()
scope = []
with torch.no_grad():
    for b in range(0, len(texts), 256):
        e = tok(texts[b:b + 256], padding=True, truncation=True, max_length=192,
                return_tensors="pt")
        e = {k: v.to(dev) for k, v in e.items()}
        scope += [CATS[k] for k in mod(**e).logits.argmax(-1).cpu().tolist()]
print("  品类判定完成｜分布：" + "｜".join(f"{k}={v}" for k, v in
                                       collections.Counter(scope).most_common(5)))

hp_in = [i for i in range(len(texts)) if scope[i] in HP and gate[i] and len(texts[i]) >= 40]
hp_out = [i for i in range(len(texts)) if scope[i] in HP and not gate[i] and len(texts[i]) >= 40]
hp_in_pos = [i for i in hp_in if llm_pos[i] == 1]
print(f"  耳机家族：闸门内 {len(hp_in):,}（其中 LLM 判音质抱怨 {len(hp_in_pos):,}）"
      f"｜闸门外 {len(hp_out):,}")

rng = random.Random(SEED)
rng.shuffle(hp_in_pos)
rng.shuffle(hp_in)
rng.shuffle(hp_out)
picked_in = hp_in_pos[:8] + [i for i in hp_in if i not in set(hp_in_pos[:8])][:12]
picked_out = hp_out[:80]
rows = []
for i in picked_in:
    rows.append({"text": texts[i], "rating": ratings[i] or "",
                 "期望标签": "1" if llm_pos[i] == 1 else "0", "类别": "耳机（提到声音）"})
for i in picked_out:
    rows.append({"text": texts[i], "rating": ratings[i] or "",
                 "期望标签": "0", "类别": "耳机（未提声音）"})
out = os.path.join(HERE, "sample_reviews_100.csv")
with open(out, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["text", "rating", "期望标签", "类别"])
    w.writeheader()
    w.writerows(rows)
n_pos = sum(1 for r in rows if r["期望标签"] == "1")
print(f"[写出] sample_reviews_100.csv（{len(rows)} 条＝闸门内 {len(picked_in)}＋闸门外 "
      f"{len(picked_out)}；其中标注为音质抱怨 {n_pos} 条）")
json.dump({"seed": SEED, "frame": "品类判为耳机家族的语料评论",
           "n": len(rows), "gate_inside": len(picked_in), "gate_outside": len(picked_out),
           "labelled_positive": n_pos,
           "note": "替代原「全语料混合」样例，使演示代表目标用户（round-04 Qwen B3-3）"},
          open(os.path.join(HERE, "v2", "sample_manifest.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
