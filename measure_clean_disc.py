# -*- coding: utf-8 -*-
"""判别器在**同一干净池**（14,299 条）上的触发数补测（round-03 审查附加条件）。

附加条件（Kimi）：
 ① 必须与 v1 的 15 条**同池、同闸门口径**，否则不可比；
 ② **逐条留档**（文本 + 分数），为将来人工判精确率留好抽样框——只报数不留清单不可接受。
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
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
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
# 与 v1 那次完全同定义：留出侧 ∧ 闸门外 ∧ 长度≥40 ∧ 未判过
clean = [i for i in hold if len(texts[i]) >= 40 and not mgs.RX.search(texts[i])
         and i not in judged]
print(f"干净池：{len(clean):,} 条（与 v1 的 15/14,299 同定义同池）")
assert len(clean) == 14299, f"池规模与既往不一致：{len(clean)}（应为 14,299）"
p = rwe.predict([texts[i] for i in clean], cfg["bin_model_dir"],
                int(cfg.get("max_len", 256)))
trig = [(i, float(q)) for i, q in zip(clean, p) if q >= 0.5]
print(f"判别器触发：**{len(trig)} 条**（v1 对照 15 条 = 0.105%）"
      f"｜触发率 {len(trig)/len(clean)*100:.3f}%")
lo, hi = len(clean) * 0.0026, len(clean) * 0.0221
r_lo = len(trig) / hi * 100 if hi else 0.0
r_hi = len(trig) / lo * 100 if lo else 0.0
print(f"期望正例区间（X-14 基线 0.26–2.21%）：{lo:.0f}–{hi:.0f} 条"
      f" ⇒ 期望正例÷告警 = {lo/max(1,len(trig)):.2f}–{hi/max(1,len(trig)):.2f}"
      f"（该比值 >1 即触发不足，**不是精确率**）｜"
      f"**若 {len(trig)} 条全为真阳，召回也只有 {r_lo:.0f}%–{r_hi:.0f}%**")
rows = [{"row_index": i, "prob": round(q, 6), "text": texts[i][:600],
         "rating": None, "note": "判别器触发（干净池）"} for i, q in
        sorted(trig, key=lambda x: -x[1])]
out = {"generation": cfg.get("generation"), "model": cfg["bin_model_dir"],
       "pool": len(clean), "pool_definition": "留出侧 ∧ 闸门外 ∧ 长度≥40 ∧ 未判过",
       "triggers": len(trig), "trigger_rate": round(len(trig) / len(clean), 6),
       "v1_reference_triggers": 15, "v1_reference_rate": 0.00105,
       "expected_positives_ci": [round(lo), round(hi)],
       "implied_precision_upper": round(hi / max(1, len(trig)), 2),
       "items": rows}
json.dump(out, open(os.path.join(HERE, "v2", "clean_pool_disc.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
with open(os.path.join(HERE, "docs", "gold_set", "clean_pool_disc_items.csv"), "w",
          encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["row_index", "prob", "原文", "人工判定(留空待判)", "备注"])
    for r in rows:
        w.writerow([r["row_index"], r["prob"], r["text"], "", ""])
print(f"[写出] v2/clean_pool_disc.json、docs/gold_set/clean_pool_disc_items.csv（{len(rows)} 条留档）")
