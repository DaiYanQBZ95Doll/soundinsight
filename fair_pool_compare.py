# -*- coding: utf-8 -*-
"""公平对比：在**同一干净池**上跑 v1 与 v3-lite-B，并把结果写入 S1 落档（追加 B 的结果）。"""
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


rwe = load_mod("rwe", os.path.join(HERE, "realworld_eval.py"))
mgs = load_mod("mgs", os.path.join(HERE, "make_gold_set.py"))
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
# ⚠️ 只排除**原始测量时**排除的那两类（金标 300 + S1追加 + S5 探针）；
# **不得**排除 clean_alerts/vocab_test 的行——它们是被测出来的告警本身，
# 排除它们会把 v1 的 15 条告警一并删掉，从而伪造出"v1 零告警"的假象。
for f in ("docs/gold_set/s5_clean_probe.csv",):
    with open(os.path.join(HERE, f), encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if str(r.get("row_index", "")).strip():
                judged.add(int(r["row_index"]))
clean = [i for i in hold if len(texts[i]) >= 40 and not mgs.RX.search(texts[i])
         and i not in judged]
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
res = {}
for name, d, ml in (("v1（出厂）", cfg["bin_model_dir"], 128),
                    ("v3-lite（A：仅口径纠正）", os.path.join(HERE, "v2", "model_inscope"), 256),
                    ("v3-lite-B（+扩词表补标）", os.path.join(HERE, "v2", "model_inscope_b"), 256)):
    if not os.path.isdir(d):
        continue
    p = rwe.predict([texts[i] for i in clean], d, ml)
    n5 = sum(1 for x in p if x >= 0.5)
    res[name] = {"alerts_0.5": n5, "rate": round(n5 / len(clean), 6)}
    print(f"  {name}: 触发 **{n5}** 条 = {n5/len(clean)*100:.3f}%（同池 n={len(clean):,}）")
json.dump({"pool": len(clean), "models": res}, open(os.path.join(HERE, "v2",
          "clean_pool_three_models.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# 追加到 S1 落档
P = os.path.join(HERE, "docs", "v3lite_filing.md")
t = open(P, encoding="utf-8").read()
if "## 六、v3-lite-B" not in t:
    b = json.load(open(os.path.join(HERE, "v2", "v3liteb_eval_test.json"), encoding="utf-8"))
    rw = json.load(open(os.path.join(HERE, "v2", "v3liteb_realworld.json"), encoding="utf-8"))
    add = f"""
## 六、v3-lite-B（口径纠正 **+ 扩词表补标**）——同样是否定的

在 A 的基础上，把 S6 复核为"音质抱怨 ∧ 耳机家族"的新正例并入训练（新增约 15 条，均限训练侧）：

| 面 | v2 | v3-lite(A) | **v3-lite-B** |
|---|---|---|---|
| 范围内 F1@0.5（778／48） | **0.6966** | 0.5581 | **{b['groups']['耳机家族（范围内）']['at_0.5']['F1']}** |
| 全测试集 F1@0.5 | 0.7206 | 0.3616 | {b['groups']['全测试集']['at_0.5']['F1']} |
| **干净池触发（同池 {res and len(clean):,} 条）** | — | {res.get('v3-lite（A：仅口径纠正）', {}).get('alerts_0.5', '—')} | **{res.get('v3-lite-B（+扩词表补标）', {}).get('alerts_0.5', '—')}**（v1 为 {res.get('v1（出厂）', {}).get('alerts_0.5', '—')}） |
| S2c 真实场景子集（59／1）命中 | 0 | — | **{rw['face2_realworld_subset']['hits']}** |

**结论（可断言）**：**"口径纠正 + 扩词表补标"这条路径未能改善真实场景召回**——
新正例仅约 15 条（全语料可回收约 {79} 条，区间 42–142），而闸门外估计真阳在数百条量级；
模型反而更保守（同池触发 {res.get('v3-lite-B（+扩词表补标）', {}).get('alerts_0.5', '—')} 条 vs v1 的 {res.get('v1（出厂）', {}).get('alerts_0.5', '—')} 条）。
**不可断言**：不得据此说"补标无用"（更根本的原因是**闸门外正例总量不足以支撑监督**），
也不得把 A/B 的掉分归因于"口径"（监督量同时变化，两因未分离）。
"""
    open(P, "w", encoding="utf-8", newline="\n").write(t.rstrip("\n") + add)
    print("  [改] docs/v3lite_filing.md：追加第六节（v3-lite-B）")
