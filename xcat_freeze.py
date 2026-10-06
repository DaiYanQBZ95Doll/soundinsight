# -*- coding: utf-8 -*-
"""跨品类试点（音箱）防火墙②：**先冻结划分与登记，再训练**。

要点（含 X-25 教训的前置修正）：
 ① 语料去重：按 normalized 内容哈希**先去重再划分**，避免既往 6.37% 的跨侧文本重复；
 ② 人工修正入训：mini 金标中判 0 的正例候选 → 翻为负例；判 ? 的 → 整条剔除（不进训练、不进评测）；
 ③ 划分冻结：分层、固定种子，登记四数（训练/留出行数、正例数）与两侧内容哈希交集（应为 0）；
 ④ 训练底座＝出厂判别器权重（这同时回答"音频域模型能否迁移到音箱"这一可迁移性问题）。
"""
from __future__ import annotations

import collections
import csv
import hashlib
import importlib.util
import json
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261013
ADJ = {"speaker", "soundbar", "other_audio"}
CATS = ["headphone", "earbud", "headset", "speaker", "soundbar", "other_audio",
        "cable", "non_audio", "unclear"]


def load_mod(n, p):
    spec = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


import torch  # noqa: E402
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer  # noqa: E402

rio = load_mod("rio", os.path.join(HERE, "rulings_io.py"))
texts = []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))


def h(t):
    return hashlib.sha256(re.sub(r"\s+", " ", str(t)).strip()
                          .encode("utf-8", "replace")).hexdigest()


# ① 品类判定（复用已登记的口径标签 + 对 P1 未覆盖者用本地品类模型）
scope = {}
for line in open(os.path.join(HERE, "v2", "scope_rows.jsonl"), encoding="utf-8",
                 errors="replace"):
    try:
        rec = json.loads(line)
    except ValueError:
        continue
    u = str(rec.get("uid", ""))
    if u.startswith(("lab:", "s6:")) and rec.get("category"):
        scope[int(u.split(":")[1])] = rec["category"]
recs = []
for line in open(os.path.join(HERE, "v2", "p1_labels.jsonl"), encoding="utf-8",
                 errors="replace"):
    try:
        rec = json.loads(line)
    except ValueError:
        continue
    recs.append(rec)
need = [int(r["row_index"]) for r in recs if int(r["row_index"]) not in scope]
dev = "cuda" if torch.cuda.is_available() else "cpu"
if need:
    tok = DistilBertTokenizer.from_pretrained(os.path.join(HERE, "v2", "model_scope"))
    mod = DistilBertForSequenceClassification.from_pretrained(
        os.path.join(HERE, "v2", "model_scope")).to(dev).eval()
    with torch.no_grad():
        for b in range(0, len(need), 64):
            e = tok([texts[i] for i in need[b:b + 64]], padding=True, truncation=True,
                    max_length=192, return_tensors="pt")
            e = {k: v.to(dev) for k, v in e.items()}
            for j, k in enumerate(mod(**e).logits.argmax(-1).cpu().tolist()):
                scope[need[b + j]] = CATS[k]
print(f"品类标签覆盖：{len(scope):,} 条")

# ② mini 金标的人工修正
got, _amb = rio.read_judgements(os.path.join(HERE, "docs/gold_set/answer_sheet_xcat_mini.md"))
meta = json.load(open(os.path.join(HERE, "v2", "xcat_mini_ids.json"), encoding="utf-8"))
fix = {i: got[u] for u, i in zip(meta["ids"], meta["row_index"]) if u in got}
flip_neg = [i for i, v in fix.items() if v == "0"]
drop = [i for i, v in fix.items() if v == "?"]
print(f"人工修正：翻为负例 {len(flip_neg)} 条、剔除 {len(drop)} 条")

# ③ 候选池（先按内容哈希去重）
pos, neg, seen = [], [], set()
for r in recs:
    i = int(r["row_index"])
    if i in drop or scope.get(i) not in ADJ:
        continue
    hh = h(texts[i])
    if hh in seen:
        continue
    seen.add(hh)
    if i in flip_neg:
        neg.append(i)
    elif int(r.get("sound_complaint") or 0) == 1:
        pos.append(i)
    else:
        neg.append(i)
print(f"去重后：正例 {len(pos)}｜负例 {len(neg)}")

# ④ 冻结划分（分层、固定种子）
rng = random.Random(SEED)
rng.shuffle(pos)
rng.shuffle(neg)
n_pos_te = max(30, round(len(pos) * 0.2))
n_neg_te = max(60, round(len(neg) * 0.2))
te = pos[:n_pos_te] + neg[:n_neg_te]
tr = pos[n_pos_te:] + neg[n_neg_te:]
rng.shuffle(te)
rng.shuffle(tr)
tr_set, te_set = set(tr), set(te)
assert not (tr_set & te_set)
overlap = {h(texts[i]) for i in tr_set} & {h(texts[i]) for i in te_set}
print(f"训练 {len(tr):,}（正例 {sum(1 for i in tr if i in set(pos))}）｜"
      f"留出 {len(te):,}（正例 {sum(1 for i in te if i in set(pos))}）"
      f"｜**两侧内容哈希交集 {len(overlap)}**（去重有效应为 0）")

out = {"generation": "xcat-speaker", "seed": SEED, "scope_categories": sorted(ADJ),
       "labels_source": "P1 LLM sound_complaint ∧ 本地品类模型（人工抽检确认率 96.6%，n=29）",
       "human_corrections": {"flipped_to_negative": len(flip_neg), "dropped": len(drop)},
       "dedup": "normalized content sha256（先去重再划分）",
       "n_train": len(tr), "n_holdout": len(te),
       "pos_train": sum(1 for i in tr if i in set(pos)),
       "pos_holdout": sum(1 for i in te if i in set(pos)),
       "content_overlap_train_holdout": len(overlap),
       "train_row_index": sorted(tr_set), "holdout_row_index": sorted(te_set),
       "base_weights": "sound_model（厂判别器）"}
json.dump(out, open(os.path.join(HERE, "v2", "xcat_speaker_split.json"), "w",
                    encoding="utf-8"), ensure_ascii=False, indent=2)

# ⑤ 登记（R34：训练前登记）
P = os.path.join(HERE, "docs", "split_manifest.md")
t = open(P, encoding="utf-8").read()
if "xcat-speaker" not in t:
    add = (f"\n| **音箱试点 xcat-speaker**（2026-10-06，训练前登记） | 见 `v2/xcat_speaker_split.json` | "
           f"训练 {out['n_train']:,}（正例 {out['pos_train']}）／留出 {out['n_holdout']:,}"
           f"（正例 {out['pos_holdout']}） | 种子 {SEED}；**先去重再划分**（跨侧内容交集 "
           f"**{len(overlap)}**）；人工修正：翻负 {len(flip_neg)}／剔除 {len(drop)}；"
           f"底座＝出厂判别器 |\n")
    t = t.rstrip("\n") + "\n" + add
    open(P, "w", encoding="utf-8", newline="\n").write(t)
print("  [改] split_manifest：登记 xcat-speaker 世代（训练前）")
print("[写出] v2/xcat_speaker_split.json")
