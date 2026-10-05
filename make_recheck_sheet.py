# -*- coding: utf-8 -*-
"""生成**复核卡**（独立于此前那张）：按**判别器自己的**触发/未触发池分层抽样。

动机（登记表 X-27 已写）：三个模型在同一张卡上三选一 → 冠军优势可能被高估。
本卡用新种子、且**剔除已判过的 100 条**，用同一协议复核判别器的精确率与召回。
"""
from __future__ import annotations

import concurrent.futures as cf
import csv
import importlib.util
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
HP = {"headphone", "earbud", "headset"}
CATS = ["headphone", "earbud", "headset", "speaker", "soundbar", "other_audio",
        "cable", "non_audio", "unclear"]
SEED = 20261011


def load_mod(n, p):
    spec = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


import torch  # noqa: E402
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer  # noqa: E402

mgs = load_mod("mgs", os.path.join(HERE, "make_gold_set.py"))
rwe = load_mod("rwe", os.path.join(HERE, "realworld_eval.py"))
mgn = load_mod("mgn", os.path.join(HERE, "make_gold_set_notes.py"))
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
texts, labels = [], []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
        labels.append(int(float(r.get("sound_negative_llm") or 0)))
from sklearn.model_selection import train_test_split  # noqa: E402
hold = set(train_test_split(list(range(len(labels))), test_size=0.2, random_state=42,
                            stratify=labels)[1])

# 已判过的一律排除（含此前那张验收卡的 100 条）
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
prev = json.load(open(os.path.join(HERE, "v2", "p0_accept_ids.json"), encoding="utf-8"))
judged |= set(prev["row_index"])
print(f"已判过（排除）：{len(judged):,} 条")

pool = [i for i in hold if i not in judged and len(texts[i]) >= 40 and mgs.RX.search(texts[i])]
rng = random.Random(SEED)
rng.shuffle(pool)
pool = pool[:4000]
dev = "cuda" if torch.cuda.is_available() else "cpu"
stok = DistilBertTokenizer.from_pretrained(os.path.join(HERE, "v2", "model_scope"))
smod = DistilBertForSequenceClassification.from_pretrained(
    os.path.join(HERE, "v2", "model_scope")).to(dev).eval()
scope = []
with torch.no_grad():
    for b in range(0, len(pool), 64):
        e = stok([texts[i] for i in pool[b:b + 64]], padding=True, truncation=True,
                 max_length=192, return_tensors="pt")
        e = {k: v.to(dev) for k, v in e.items()}
        scope += [CATS[k] for k in smod(**e).logits.argmax(-1).cpu().tolist()]
served = [i for i, c in zip(pool, scope) if c in HP]
probs = rwe.predict([texts[i] for i in served], cfg["bin_model_dir"], int(cfg.get("max_len", 256)))
lo = float(cfg.get("tier_low", 0.5))
fired = [i for i, p in zip(served, probs) if p >= lo]
notf = [i for i, p in zip(served, probs) if p < lo]
rng.shuffle(fired)
rng.shuffle(notf)
picked = [("A", i) for i in fired[:50]] + [("B", i) for i in notf[:50]]
print(f"候选 {len(served):,}｜触发池 {len(fired):,}／未触发池 {len(notf):,}｜取 {len(picked)} 条")

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
todo = [(f"ridx:{i}", texts[i]) for _a, i in picked if f"ridx:{i}" not in notes]
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

sheet = ["# 出厂复核 · 答题卡（100 条，**双盲**）", "",
         "> **目的**：用**独立样本**复核现出厂（判别器）的精确率与召回——消除「三选一」的选择效应。",
         "> Arm A（**触发** 50 条）→ 精确率；Arm B（**未触发** 50 条）→ 召回。", "",
         "> 编码：**1 = 是**（在抱怨耳机音质/听感）｜**0 = 不是**｜**2 = 无法判断**",
         "> 📝 想法可选（只在犹豫/不同意时写）。**只判 Arm A 的 50 条**也能得出精确率。", "",
         f"> 抽样种子 {SEED}｜仅留出侧、闸门内、品类判耳机、且**排除此前判过的 {len(judged):,} 条**"
         "｜不显示模型分数", ""]
rows_out = []
for arm, i in picked:
    uid = f"{arm}{sum(1 for r in rows_out if r[1] == arm) + 1:02d}"
    d = notes.get(f"ridx:{i}", {})
    rows_out.append((uid, arm, i, texts[i], d.get("zh", "")))
    sheet += [f"## {uid}　[Arm {arm}]", "", f"**原文**：{texts[i]}", "",
              f"**翻译**：{d.get('zh', '')}", "", "**判定（决策方填）**：`___`", ""]
open(os.path.join(HERE, "docs", "gold_set", "answer_sheet_recheck.md"), "w",
     encoding="utf-8", newline="\n").write("\n".join(sheet) + "\n")
with open(os.path.join(HERE, "docs", "gold_set", "recheck.csv"), "w",
          encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["编号", "臂", "row_index", "原文", "中文翻译",
                "人工判定(1=音质差评/0=不是)", "备注"])
    for uid, arm, i, t, zh in rows_out:
        w.writerow([uid, arm, i, t, zh, "", ""])
json.dump({"seed": SEED, "served_pool": len(served), "fired_pool": len(fired),
           "notfired_pool": len(notf), "ids": [r[0] for r in rows_out],
           "row_index": [r[2] for r in rows_out], "model": "disc（判别器）"},
          open(os.path.join(HERE, "v2", "recheck_ids.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[写出] docs/gold_set/answer_sheet_recheck.md / recheck.csv")
