# -*- coding: utf-8 -*-
"""跨品类（音箱）试点 · mini 金标卡：人工抽检 30 条"现货正例" + 10 条同域负例。

动机（Kimi 防火墙①）：235 条候选正例 = LLM 标签 ∧ 本地品类模型判为音箱类；
该分类器有约 11.5% 误报 → **未经人工抽检不能称为正例**。判卡用于先验证"正例到底是不是正例"。

抽样：正例按 speaker／soundbar／other_audio 分层各取；负例取同域 sound_complaint=0。
"""
from __future__ import annotations

import collections
import concurrent.futures as cf
import csv
import importlib.util
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261012
CATS = ["headphone", "earbud", "headset", "speaker", "soundbar", "other_audio",
        "cable", "non_audio", "unclear"]
ADJ = {"speaker", "soundbar", "other_audio"}


def load_mod(n, p):
    spec = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


import torch  # noqa: E402
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer  # noqa: E402

mgn = load_mod("mgn", os.path.join(HERE, "make_gold_set_notes.py"))
texts = []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
recs = []
for line in open(os.path.join(HERE, "v2", "p1_labels.jsonl"), encoding="utf-8",
                 errors="replace"):
    try:
        rec = json.loads(line)
    except ValueError:
        continue
    recs.append(rec)
print(f"P1 标注 {len(recs):,} 条")

dev = "cuda" if torch.cuda.is_available() else "cpu"
tok = DistilBertTokenizer.from_pretrained(os.path.join(HERE, "v2", "model_scope"))
mod = DistilBertForSequenceClassification.from_pretrained(
    os.path.join(HERE, "v2", "model_scope")).to(dev).eval()
idxs = [int(r["row_index"]) for r in recs]
cats = []
with torch.no_grad():
    for b in range(0, len(idxs), 64):
        e = tok([texts[i] for i in idxs[b:b + 64]], padding=True, truncation=True,
                max_length=192, return_tensors="pt")
        e = {k: v.to(dev) for k, v in e.items()}
        cats += [CATS[k] for k in mod(**e).logits.argmax(-1).cpu().tolist()]
by_scope_pos = collections.defaultdict(list)
by_scope_neg = collections.defaultdict(list)
for r, c in zip(recs, cats):
    (by_scope_pos if int(r.get("sound_complaint") or 0) == 1 else by_scope_neg)[c].append(
        int(r["row_index"]))
print("候选正例（相邻音频）：" + "｜".join(f"{c}={len(by_scope_pos[c])}" for c in sorted(ADJ)))
print("候选负例（同域）：" + "｜".join(f"{c}={len(by_scope_neg[c])}" for c in sorted(ADJ)))

rng = random.Random(SEED)
picked = []
plan = [("speaker", 18, 8), ("other_audio", 8, 1), ("soundbar", 4, 1)]
for cat, npos, nneg in plan:
    ps = by_scope_pos[cat][:]
    ns = by_scope_neg[cat][:]
    rng.shuffle(ps)
    rng.shuffle(ns)
    for i in ps[:npos]:
        picked.append(("正例候选", cat, i))
    for i in ns[:nneg]:
        picked.append(("负例候选", cat, i))
print(f"抽卡 {len(picked)} 条（正例候选 {sum(1 for a,_,_ in picked if a=='正例候选')}／"
      f"负例候选 {sum(1 for a,_,_ in picked if a=='负例候选')}）")

cache = os.path.join(HERE, "v2", "p0_val_notes.jsonl")
notes = {}
if os.path.isfile(cache):
    for line in open(cache, encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "zh" in rec:
            notes[str(rec["uid"])] = rec
todo = [(f"ridx:{i}", texts[i]) for _a, _c, i in picked if f"ridx:{i}" not in notes]
key = os.environ.get("DEEPSEEK_API_KEY", "")
if todo and key:
    print(f"  生成翻译 {len(todo)} 条…")
    with open(cache, "a", encoding="utf-8") as fh, cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(mgn.call, t, key): u for u, t in todo}
        for fut in cf.as_completed(futs):
            fh.write(json.dumps({"uid": futs[fut], **fut.result()}, ensure_ascii=False) + "\n")
    for line in open(cache, encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "zh" in rec:
            notes[str(rec["uid"])] = rec

sheet = ["# 跨品类试点 · mini 金标卡（40 条，**双盲**）", "",
         "> **目的**：在训练任何音箱模型**之前**，先验证「现货正例」是不是真正例。",
         "> 背景：235 条候选 = LLM 标签 ∧ 本地品类模型判为音箱类；该分类器有约 **11.5% 误报**，",
         "> 故**未经人工抽检不能称正例**（Kimi 防火墙①）。", "",
         "> 编码：**1 = 是**（在抱怨该产品的音质/听感，且产品确为音箱类）｜"
         "**0 = 不是**｜**2 = 无法判断**",
         "> ⚠️ 特别注意两种情况：① 产品其实**不是音箱**（误分类）；② 提到了声音但**不是在抱怨**。",
         "> 📝 想法可选。判决完成后我立刻按结果决定：是否开训、或只作方向性证据。", "",
         f"> 种子 {SEED}｜分层：speaker／other_audio／soundbar｜不显示模型分数", ""]
rows_out = []
for k2, (arm, cat, i) in enumerate(picked, 1):
    uid = f"M{k2:02d}"
    d = notes.get(f"ridx:{i}", {})
    rows_out.append((uid, arm, cat, i, texts[i], d.get("zh", "")))
    sheet += [f"## {uid}　[{arm}／品类模型判：{cat}]", "", f"**原文**：{texts[i]}", "",
              f"**翻译**：{d.get('zh', '')}", "", "**判定（决策方填）**：`___`", ""]
open(os.path.join(HERE, "docs", "gold_set", "answer_sheet_xcat_mini.md"), "w",
     encoding="utf-8", newline="\n").write("\n".join(sheet) + "\n")
with open(os.path.join(HERE, "docs", "gold_set", "xcat_mini.csv"), "w",
          encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["编号", "候选类型", "品类模型判定", "row_index", "原文", "中文翻译",
                "人工判定(1=真音质抱怨/0=不是)", "备注"])
    for uid, arm, cat, i, t, zh in rows_out:
        w.writerow([uid, arm, cat, i, t, zh, "", ""])
json.dump({"seed": SEED, "ids": [r[0] for r in rows_out],
           "row_index": [r[3] for r in rows_out], "candidate": [r[1] for r in rows_out],
           "scope": [r[2] for r in rows_out],
           "source": "P1 LLM sound_complaint=1 ∧ 本地品类模型判为 speaker/soundbar/other_audio"},
          open(os.path.join(HERE, "v2", "xcat_mini_ids.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[写出] docs/gold_set/answer_sheet_xcat_mini.md / xcat_mini.csv（40 条）")
