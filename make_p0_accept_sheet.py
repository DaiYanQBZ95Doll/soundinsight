# -*- coding: utf-8 -*-
"""生成 P0 出厂验收答题卡（100 条：Arm A 触发 50 ＋ Arm B 未触发 50，含中性翻译）。

判据：**是否在抱怨耳机音质/听感**（1/0/2）。Arm A 出精确率，Arm B 出召回。
"""
from __future__ import annotations

import concurrent.futures as cf
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
rwe = load_mod("rwe", os.path.join(HERE, "realworld_eval.py"))
mgn = load_mod("mgn", os.path.join(HERE, "make_gold_set_notes.py"))
texts = []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
dev = "cuda" if torch.cuda.is_available() else "cpu"
stok = DistilBertTokenizer.from_pretrained(os.path.join(HERE, "v2", "model_scope"))
smod = DistilBertForSequenceClassification.from_pretrained(
    os.path.join(HERE, "v2", "model_scope")).to(dev).eval()


def scope_of(idxs):
    out = []
    with torch.no_grad():
        for b in range(0, len(idxs), 64):
            e = stok([texts[i] for i in idxs[b:b + 64]], padding=True, truncation=True,
                     max_length=192, return_tensors="pt")
            e = {k: v.to(dev) for k, v in e.items()}
            out += [CATS[k] for k in smod(**e).logits.argmax(-1).cpu().tolist()]
    return out


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
served = [i for i, c in zip(pool, scope_of(pool)) if c in HP]
probs = rwe.predict([texts[i] for i in served], cfg["bin_model_dir"], 128)
lo = float(cfg.get("tier_low", 0.5))
fired = [i for i, p in zip(served, probs) if p >= lo]
notf = [i for i, p in zip(served, probs) if p < lo]
rng.shuffle(fired)
rng.shuffle(notf)
picked = [("A", i) for i in fired[:50]] + [("B", i) for i in notf[:50]]
print(f"出厂总体候选 {len(served):,}｜触发池 {len(fired):,}／未触发池 {len(notf):,}"
      f"｜取 A {min(50,len(fired))} ＋ B {min(50,len(notf))}")

# 翻译（复用缓存）
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
        for k, fut in enumerate(cf.as_completed(futs), 1):
            fh.write(json.dumps({"uid": futs[fut], **fut.result()}, ensure_ascii=False) + "\n")
    for line in open(cache, encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "zh" in rec:
            notes[str(rec["uid"])] = rec

sheet = ["# P0 出厂验收 · 答题卡（100 条，**双盲**）", "",
         "> **目的**：量出**出厂配置**（音频词汇闸门 ∧ 品类判耳机）下的**精确率与召回**。",
         "> Arm A（**触发** 50 条）→ 精确率；Arm B（**未触发** 50 条）→ **召回**（未触发里若有真抱怨，就是漏掉的）。", "",
         "> 编码：**1 = 是**（在抱怨耳机音质/听感）｜**0 = 不是**｜**2 = 无法判断**",
         "> 📝 可写想法（判断理由、犹豫、觉得该算别的类）——我会原样保留并汇总。", "",
         f"> 抽样框：闸门内 ∧ 本地品类判耳机，共 {len(served):,} 条；种子 {SEED}｜不显示模型分数", ""]
rows_out = []
for arm, i in picked:
    uid = f"{arm}{sum(1 for r in rows_out if r[1] == arm) + 1:02d}"
    d = notes.get(f"ridx:{i}", {})
    rows_out.append((uid, arm, i, texts[i], d.get("zh", "")))
    sheet += [f"## {uid}　[Arm {arm}]", "", f"**原文**：{texts[i]}", "",
              f"**翻译**：{d.get('zh', '')}", "",
              "**判定（决策方填）**：`___`", ""]
open(os.path.join(HERE, "docs", "gold_set", "answer_sheet_p0_accept.md"), "w",
     encoding="utf-8", newline="\n").write("\n".join(sheet) + "\n")
with open(os.path.join(HERE, "docs", "gold_set", "p0_accept.csv"), "w",
          encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["编号", "臂", "row_index", "原文", "中文翻译",
                "人工判定(1=音质差评/0=不是)", "备注"])
    for uid, arm, i, t, zh in rows_out:
        w.writerow([uid, arm, i, t, zh, "", ""])
json.dump({"seed": SEED, "served_pool": len(served), "fired_pool": len(fired),
           "notfired_pool": len(notf),
           "ids": [r[0] for r in rows_out], "arm": [r[1] for r in rows_out],
           "row_index": [r[2] for r in rows_out]},
          open(os.path.join(HERE, "v2", "p0_accept_ids.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"[写出] docs/gold_set/answer_sheet_p0_accept.md / p0_accept.csv（{len(rows_out)} 条）")
