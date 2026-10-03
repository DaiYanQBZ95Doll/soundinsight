# -*- coding: utf-8 -*-
"""归因人工校验答题卡（50 条，双盲：**不显示模型与 LLM 的归因**）。

两个臂：
  A（约 25 条）**人工已确认为音质抱怨**的条目 → 检验"0.8273（对 LLM 标签）"与人工归因是否一致；
  B（约 25 条）**出厂 v1 判为阳性**的分布内条目（含音频词汇、从未判过）→ 检验"用户实际看到的归因"。

编码（写在判定位）：**1=低音 2=清晰度 3=杂音 4=音量 5=高音**，多选用逗号分隔（如 `1,3`）；
**0 = 无法判断/无明确类别**。

产物：docs/gold_set/answer_sheet_attribution.md、docs/gold_set/attribution_test.csv、
     v2/attribution_ids.json
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
SEED = 20261007
N_A, N_B = 25, 25
CLASSES = ["低音", "清晰度", "杂音", "音量", "高音"]


def load_mod(n, p):
    spec = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------- 语料与映射 ----------
texts, llm_cls = [], []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
        llm_cls.append([k for k, col in zip(CLASSES, ("issue_bass_llm", "issue_clarity_llm",
                                                      "issue_noise_llm", "issue_volume_llm",
                                                      "issue_treble_llm"))
                        if str(r.get(col, "")).strip() in ("1", "1.0", "True")])

# 人工已确认为正例的条目 → row_index
pos_ids = {}
for f, col in (("docs/gold_set/assisted_worksheet.csv", "人工判定(1=音质差评/0=不是)"),
               ("docs/gold_set/clean_alerts.csv", "人工判定(1=音质差评/0=不是)"),
               ("docs/gold_set/vocab_test.csv", "人工判定(1=音质差评/0=不是)")):
    with open(os.path.join(HERE, f), encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if (r.get(col) or "").strip() == "1" and str(r.get("row_index", "")).strip():
                pos_ids[r["编号"]] = int(r["row_index"])
# 金标 300 无 row_index 列 → 用 gold_set_key
key = {it["id"]: it["row_index"] for it in json.load(
    open(os.path.join(HERE, "v2", "gold_set_key.json"), encoding="utf-8"))["items"]}
with open(os.path.join(HERE, "docs/gold_set/assisted_worksheet.csv"),
          encoding="utf-8-sig", errors="replace") as fh:
    for r in csv.DictReader(fh):
        if (r.get("人工判定(1=音质差评/0=不是)") or "").strip() == "1" and r["编号"] in key:
            pos_ids[r["编号"]] = key[r["编号"]]
print(f"人工已确认为正例：{len(pos_ids)} 条")

rng = random.Random(SEED)
armA_idx = [pos_ids[u] for u in sorted(pos_ids)]
rng.shuffle(armA_idx)
armA_idx = armA_idx[:N_A]

# ---------- Arm B：v1 判正的分布内条目（含音频词、未判过） ----------
mgs = load_mod("mgs", os.path.join(HERE, "make_gold_set.py"))
rwe = load_mod("rwe", os.path.join(HERE, "realworld_eval.py"))
judged = set(pos_ids.values())
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
cand = [i for i, t in enumerate(texts)
        if i not in judged and len(t) >= 60 and mgs.RX.search(t)]
rng.shuffle(cand)
cand = cand[:1500]
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
probs = rwe.predict([texts[i] for i in cand], cfg["bin_model_dir"], 128)
armB_idx = [i for i, p in zip(cand, probs) if p >= 0.5][:N_B]
print(f"Arm A {len(armA_idx)} 条（人工已确认正例）｜Arm B {len(armB_idx)} 条（v1 判正、含音频词、未判过）")

# ---------- 翻译（Arm B 需新生成；Arm A 复用既有） ----------
existing = {}
for f, k in (("docs/gold_set/assisted_worksheet.csv", "编号"),
             ("docs/gold_set/s1_add100.csv", "编号"),
             ("docs/gold_set/clean_alerts.csv", "编号"),
             ("docs/gold_set/vocab_test.csv", "编号")):
    if not os.path.isfile(os.path.join(HERE, f)):
        continue
    with open(os.path.join(HERE, f), encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if r.get("中文翻译"):
                existing.setdefault(r["原文"], r["中文翻译"])
mgn = load_mod("mgn", os.path.join(HERE, "make_gold_set_notes.py"))
cache = os.path.join(HERE, "v2", "attribution_notes.jsonl")
notes = {}
if os.path.isfile(cache):
    for line in open(cache, encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "zh" in rec:
            notes[str(rec["uid"])] = rec
todo = []
for i in armB_idx:
    if texts[i] not in existing and f"ridx:{i}" not in notes:
        todo.append((f"ridx:{i}", texts[i]))
keyenv = os.environ.get("DEEPSEEK_API_KEY", "")
if todo and keyenv:
    print(f"  生成翻译 {len(todo)} 条…")
    with open(cache, "a", encoding="utf-8") as fh, cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(mgn.call, t, keyenv): u for u, t in todo}
        for k, fut in enumerate(cf.as_completed(futs), 1):
            fh.write(json.dumps({"uid": futs[fut], **fut.result()}, ensure_ascii=False) + "\n")
    for line in open(cache, encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "zh" in rec:
            notes[str(rec["uid"])] = rec

# ---------- 写卡 ----------
sheet = ["# 归因人工校验 · 答题卡（50 条，**双盲**）", "",
         "> 本条校验 **五类归因**：出厂产品在报告里显示「低音／清晰度／杂音／音量／高音」。",
         "> 该指标（宏 F1 0.8273）此前**只对 LLM 标签**测过，从未经人工校准——本卡即为此。", "",
         "> **编码**：**1=低音　2=清晰度　3=杂音　4=音量　5=高音**；多选用逗号分隔（例：`1,3`）；"
         "**0 = 无法判断／无明确类别**。", "",
         f"> 抽样：Arm A **{len(armA_idx)} 条**（你此前已判为音质抱怨）＋ Arm B **{len(armB_idx)} 条**"
         f"（出厂模型判正、含音频词、从未判过）｜种子 {SEED}", "",
         "> ⚠️ 本卡**不显示**模型与 LLM 的归因结果，以免锚定。", ""]
rows_out = []
for arm, idxs in (("A", armA_idx), ("B", armB_idx)):
    for j, i in enumerate(idxs, 1):
        uid = f"{arm}{j:02d}"
        zh = existing.get(texts[i]) or notes.get(f"ridx:{i}", {}).get("zh", "")
        rows_out.append((uid, arm, i, texts[i], zh))
        sheet += [f"## {uid}　[Arm {arm}]", "",
                  f"**原文**：{texts[i]}", "",
                  f"**翻译**：{zh}", "",
                  "**归因（决策方填，可多选）**：`___`", ""]
open(os.path.join(HERE, "docs", "gold_set", "answer_sheet_attribution.md"), "w",
     encoding="utf-8", newline="\n").write("\n".join(sheet) + "\n")
with open(os.path.join(HERE, "docs", "gold_set", "attribution_test.csv"), "w",
          encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["编号", "臂", "row_index", "原文", "中文翻译", "人工归因(1-5逗号分隔/0)", "备注"])
    for uid, arm, i, t, zh in rows_out:
        w.writerow([uid, arm, i, t, zh, "", ""])
json.dump({"seed": SEED, "armA": [f"A{j:02d}" for j in range(1, len(armA_idx) + 1)],
           "armB": [f"B{j:02d}" for j in range(1, len(armB_idx) + 1)],
           "row_index": [r[2] for r in rows_out],
           "llm_classes": {"".join(k for k in []): None} or
           {r[0]: llm_cls[r[2]] for r in rows_out},
           "classes": CLASSES},
          open(os.path.join(HERE, "v2", "attribution_ids.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"[写出] answer_sheet_attribution.md / attribution_test.csv（{len(rows_out)} 条）")
