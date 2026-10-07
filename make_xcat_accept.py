# -*- coding: utf-8 -*-
"""音箱试点 · 人工验收卡（100 条，同耳机协议）：

  · 抽样框＝**试点模型的冻结留出集**（612 条内部）——不在训练侧抽，避免污染；
  · Arm A＝模型**触发**档（≥0.5），测**人工口径精确率**；
  · Arm B＝模型**未触发**档，测**人工口径召回**（分层加权）；
  · 排除已判过的 mini 金标 40 条；双盲（不显示分数与模型判定）。
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
SEED = 20261014


def load_mod(n, p):
    spec = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


import torch  # noqa: E402
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer  # noqa: E402

mgn = load_mod("mgn", os.path.join(HERE, "make_gold_set_notes.py"))
sp = json.load(open(os.path.join(HERE, "v2", "xcat_speaker_split.json"), encoding="utf-8"))
mini = set(json.load(open(os.path.join(HERE, "v2", "xcat_mini_ids.json"),
                          encoding="utf-8"))["row_index"])
texts = []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
hold = [i for i in sp["holdout_row_index"] if i not in mini]
print(f"冻结留出集 {len(sp['holdout_row_index'])} 条｜排除已判 {len(mini)} 条 → 可用 {len(hold)}")

dev = "cuda" if torch.cuda.is_available() else "cpu"
tok = DistilBertTokenizer.from_pretrained(os.path.join(HERE, "v2", "model_xcat_speaker"))
mod = DistilBertForSequenceClassification.from_pretrained(
    os.path.join(HERE, "v2", "model_xcat_speaker")).to(dev).eval()
probs = []
with torch.no_grad():
    for b in range(0, len(hold), 64):
        e = tok([texts[i] for i in hold[b:b + 64]], padding=True, truncation=True,
                max_length=256, return_tensors="pt")
        e = {k: v.to(dev) for k, v in e.items()}
        probs += torch.softmax(mod(**e).logits, -1)[:, 1].cpu().tolist()
fires = [i for i, q in zip(hold, probs) if q >= 0.5]
nonfires = [i for i, q in zip(hold, probs) if q < 0.5]
print(f"留出集内：模型触发 {len(fires)} 条（池）｜未触发 {len(nonfires)} 条（池）")

rng = random.Random(SEED)
rng.shuffle(fires)
rng.shuffle(nonfires)
picked = ([("A", i) for i in fires[:50]] + [("B", i) for i in nonfires[:50]])
print(f"抽卡 {len(picked)} 条（A {sum(1 for a,_ in picked if a=='A')}／"
      f"B {sum(1 for a,_ in picked if a=='B')}）")

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

sheet = [f"# 音箱试点 · 人工验收卡（{len(picked)} 条，分数隐藏；臂归属可见）", "",
         "> 盲法说明：只隐藏分数，臂归属可见 → 单盲（可能存在朝模型方向的同化偏差）。", "",
         "> **目的**：把跨品类实证从 **LLM 标签口径** 升到 **人工口径**（与耳机那套证据结构对称）。",
         f"> 抽样框：**试点模型的冻结留出集**（不在训练侧抽，避免污染）｜"
         f"**Arm A 触发档 {sum(1 for a, _ in picked if a == 'A')} 条"
         f"（留出集内全部触发条目，属**普查** → 精确率只含人工判读误差）／"
         f"**Arm B 未触发档 {sum(1 for a, _ in picked if a == 'B')} 条**（→召回）。", "",
         "> 编码：**1 = 是**（在抱怨**音箱/便携音箱**的音质或听感，且产品确为该类）｜"
         "**0 = 不是**｜**2 = 无法判断**",
         "> ⚠️ 注意两种情形：① 产品其实不是音箱；② 提到声音但**不是在抱怨**（例如褒奖）。",
         f"> 📝 想法可选。**只判 Arm A 的 {sum(1 for a, _ in picked if a == 'A')} 条**也能先得出精确率（那是留出集内的全部触发条目）。", "",
         f"> 种子 {SEED}｜不显示模型分数与判定", ""]
rows_out = []
for arm, i in picked:
    uid = f"{arm}{sum(1 for r in rows_out if r[1] == arm) + 1:02d}"
    d = notes.get(f"ridx:{i}", {})
    rows_out.append((uid, arm, i, texts[i], d.get("zh", "")))
    sheet += [f"## {uid}　[Arm {arm}]", "", f"**原文**：{texts[i]}", "",
              f"**翻译**：{d.get('zh', '')}", "", "**判定（决策方填）**：`___`", ""]
open(os.path.join(HERE, "docs", "gold_set", "answer_sheet_xcat_accept.md"), "w",
     encoding="utf-8", newline="\n").write("\n".join(sheet) + "\n")
with open(os.path.join(HERE, "docs", "gold_set", "xcat_accept.csv"), "w",
          encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["编号", "臂", "row_index", "原文", "中文翻译",
                "人工判定(1=真音质抱怨/0=不是)", "备注"])
    for uid, arm, i, t, zh in rows_out:
        w.writerow([uid, arm, i, t, zh, "", ""])
json.dump({"seed": SEED, "ids": [r[0] for r in rows_out], "arm": [r[1] for r in rows_out],
           "row_index": [r[2] for r in rows_out],
           "pool_fired": len(fires), "pool_notfired": len(nonfires),
           "frame": "音箱试点冻结留出集（排除 mini 金标 40 条）",
           "model": "v2/model_xcat_speaker"},
          open(os.path.join(HERE, "v2", "xcat_accept_ids.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"[写出] docs/gold_set/answer_sheet_xcat_accept.md / xcat_accept.csv（{len(picked)} 条）")
