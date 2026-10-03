# -*- coding: utf-8 -*-
"""v3-lite-B 的真实场景评测（三个面，全部只用已有人工真值）。

面 1：**干净池告警率**——与 v1 的 15 条（0.105%）对比（样本相同，可直接比）。
面 2：**S2c 真实场景子集**（S1+S4+S5，n=59／1 正例）与 v1/v2 对比（命中计数）。
面 3：**S2c 混合口径**（112 条／8 正例）——仅作参考，不得单独引用。

产物：v2/v3liteb_realworld.json
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
HP = {"headphone", "earbud", "headset"}


def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rwe = load_mod("rwe", os.path.join(HERE, "realworld_eval.py"))
mgs = load_mod("mgs", os.path.join(HERE, "make_gold_set.py"))
MODEL = os.path.join(HERE, "v2", "model_inscope_b")
if not os.path.isdir(MODEL):
    print("[等待] 模型尚未落盘：v2/model_inscope_b")
    sys.exit(1)

texts = []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))

# ---- 面 1：干净池告警率（与 v1 同池）----
from sklearn.model_selection import train_test_split  # noqa: E402
labels = []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        labels.append(int(float(r.get("sound_negative_llm") or 0)))
_va = train_test_split(list(range(len(labels))), test_size=0.2, random_state=42,
                       stratify=labels)[1]
hold = set(_va)
judged = set()
for it in json.load(open(os.path.join(HERE, "v2", "gold_set_key.json"),
                         encoding="utf-8"))["items"]:
    judged.add(it["row_index"])
judged |= set(json.load(open(os.path.join(HERE, "v2", "s1_add100_ids.json"),
                             encoding="utf-8")).get("row_index", []))
for f in ("docs/gold_set/s5_clean_probe.csv", "docs/gold_set/clean_alerts.csv",
          "docs/gold_set/vocab_test.csv"):
    with open(os.path.join(HERE, f), encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if str(r.get("row_index", "")).strip():
                judged.add(int(r["row_index"]))
clean = [i for i in hold if len(texts[i]) >= 40 and not mgs.RX.search(texts[i])
         and i not in judged]
probs = rwe.predict([texts[i] for i in clean], MODEL, 256)
alerts = [(i, p) for i, p in zip(clean, probs) if p >= 0.5]
print(f"[面 1] 干净池 {len(clean):,} 条｜v3-lite-B 触发 **{len(alerts)}** 条 = "
      f"{len(alerts)/len(clean)*100:.3f}%｜对照 v1 = 15 条 = 0.105%")

# ---- 面 2/3：S2c（v1 真留出侧）----
mem = json.load(open(os.path.join(HERE, "v2", "s2_membership.json"), encoding="utf-8"))
ids = mem["s2c"]["ids"]
hm = {}
for f in ("docs/gold_set/assisted_worksheet.csv", "docs/gold_set/s1_add100.csv",
          "docs/gold_set/s5_clean_probe.csv"):
    with open(os.path.join(HERE, f), encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            v = (r.get("人工判定(1=音质差评/0=不是)") or "").strip()
            if v in ("0", "1"):
                hm[r["编号"]] = int(v)
# 用 row_index → 语料行（gold_set_key / s1_add100 / s5）
key = {it["id"]: it["row_index"] for it in json.load(
    open(os.path.join(HERE, "v2", "gold_set_key.json"), encoding="utf-8"))["items"]}
s4 = json.load(open(os.path.join(HERE, "v2", "s1_add100_ids.json"), encoding="utf-8"))
for k, ridx in enumerate(s4.get("row_index", []), 1):
    key[f"S4-{k:03d}"] = ridx
with open(os.path.join(HERE, "docs/gold_set/s5_clean_probe.csv"),
          encoding="utf-8-sig", errors="replace") as fh:
    for r in csv.DictReader(fh):
        if str(r.get("row_index", "")).strip():
            key[r["编号"]] = int(r["row_index"])
sel = [(u, key[u], hm[u]) for u in ids if u in hm and u in key]
txts = [texts[i] for _u, i, _y in sel]
y = [yy for _u, _i, yy in sel]
p = rwe.predict(txts, MODEL, 256)
for name, wanted in (("面 2 真实场景子集 S1+S4+S5",
                      [k for k, (u, _i, _y) in enumerate(sel) if u.startswith(("S1-", "S4-", "S5-", "C", "T"))]),
                     ("面 3 混合口径（参考）", list(range(len(sel))))):
    yy = [y[k] for k in wanted]
    pp = [p[k] for k in wanted]
    hits = sum(1 for a, b in zip(yy, pp) if a == 1 and b >= 0.5)
    al = sum(1 for b in pp if b >= 0.5)
    print(f"[{name}] n={len(wanted)} 正例={sum(yy)}｜v3-lite-B 命中 **{hits}**｜告警 {al}")
    if name.startswith("面 2"):
        face2 = {"n": len(wanted), "positives": sum(yy), "hits": hits, "alerts": al}

out = {"clean_pool": len(clean), "alerts": len(alerts),
       "alert_rate": round(len(alerts) / len(clean), 6),
       "v1_reference": {"alerts": 15, "alert_rate": 0.001049},
       "face2_realworld_subset": face2,
       "note": "新告警的精确率未测（需人工判定）；本表只报计数与率"}
json.dump(out, open(os.path.join(HERE, "v2", "v3liteb_realworld.json"), "w",
                    encoding="utf-8"), ensure_ascii=False, indent=2)
print("[写出] v2/v3liteb_realworld.json")
