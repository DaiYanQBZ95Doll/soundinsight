# -*- coding: utf-8 -*-
"""v5（P1 重训的音质模型）评测：三数同框 + 分层限定。

面 1：**干净池**（14,299 条）触发数与期望正例区间（对照组：v1 触发 15 条）。
面 2：**闸门外触发**——v5 是否开始抓到"没提关键词的音质抱怨"（这是本轮的关键问题）。
面 3：S2c 真实场景子集**仅取留出侧**条目（避免与 v5 训练侧重叠）。

用法：python eval_v5.py
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))


def load_mod(n, p):
    spec = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mgs = load_mod("mgs", os.path.join(HERE, "make_gold_set.py"))
rwe = load_mod("rwe", os.path.join(HERE, "realworld_eval.py"))
MODEL = os.path.join(HERE, "v2", "model_v5_sound")
if not os.path.isdir(MODEL):
    print("[等待] v2/model_v5_sound 尚未生成")
    sys.exit(1)

texts, labels = [], []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
        labels.append(int(float(r.get("sound_negative_llm") or 0)))
from sklearn.model_selection import train_test_split  # noqa: E402
hold = set(train_test_split(list(range(len(labels))), test_size=0.2, random_state=42,
                            stratify=labels)[1])
judged = set()
for it in json.load(open(os.path.join(HERE, "v2", "gold_set_key.json"),
                         encoding="utf-8"))["items"]:
    judged.add(it["row_index"])
judged |= set(json.load(open(os.path.join(HERE, "v2", "s1_add100_ids.json"),
                             encoding="utf-8")).get("row_index", []))
for f in ("docs/gold_set/s5_clean_probe.csv",):
    with open(os.path.join(HERE, f), encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if str(r.get("row_index", "")).strip():
                judged.add(int(r["row_index"]))
clean = [i for i in hold if len(texts[i]) >= 40 and not mgs.RX.search(texts[i])
         and i not in judged]
p = rwe.predict([texts[i] for i in clean], MODEL, 256)
alerts = [i for x, i in zip(p, clean) if x >= 0.5]
print(f"[面 1] 干净池 {len(clean):,}｜**v5 触发 {len(alerts)} 条 = "
      f"{len(alerts)/len(clean)*100:.3f}%**｜对照 v1 = 15 条 = 0.105%")
lo, hi = 0.0026, 0.0221
print(f"        期望正例区间（X-14）：{len(clean)*lo:.0f}–{len(clean)*hi:.0f} 条"
      f" ⇒ 隐含精确率上界 {len(clean)*hi/max(1,len(alerts)):.2f}")
print(f"[面 2] 闸门外触发占全部触发：**{len(alerts)}/{len(alerts)}**（干净池本身即闸门外）")

# 面 3：S2c 留出侧条目
mem = json.load(open(os.path.join(HERE, "v2", "s2_membership.json"), encoding="utf-8"))
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
hm = {}
for f in ("docs/gold_set/assisted_worksheet.csv", "docs/gold_set/s1_add100.csv",
          "docs/gold_set/s5_clean_probe.csv"):
    with open(os.path.join(HERE, f), encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            v = (r.get("人工判定(1=音质差评/0=不是)") or "").strip()
            if v in ("0", "1"):
                hm[r["编号"]] = int(v)
sel = [(u, key[u], hm[u]) for u in mem["s2c"]["ids"] if u in hm and u in key
       and key[u] in hold]
print(f"[面 3] S2c 留出侧可比对：{len(sel)} 条（正例 {sum(y for _u,_i,y in sel)}）")
if sel:
    pp = rwe.predict([texts[i] for _u, i, _y in sel], MODEL, 256)
    hits = sum(1 for (_u, _i, y), q in zip(sel, pp) if y == 1 and q >= 0.5)
    al = sum(1 for q in pp if q >= 0.5)
    print(f"        命中 {hits}｜告警 {al}")
json.dump({"clean_pool": len(clean), "alerts": len(alerts),
           "v1_reference": 15, "expected_positives": [round(len(clean)*lo), round(len(clean)*hi)]},
          open(os.path.join(HERE, "v2", "v5_eval.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[写出] v2/v5_eval.json")
