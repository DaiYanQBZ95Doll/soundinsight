# -*- coding: utf-8 -*-
"""差评类型验证计分：人工类型 vs ① 本地类型模型 ② LLM 标签。

纪律（Kimi 定稿）：**每类人工实例 ≥10 才报逐类数字**，不足者只报合并口径；
本地模型数字必须与 LLM 并排，并附「本地模型服务于零 API 推理，非精度最优」。
用法：python score_types.py
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TYPES = ["连接/配对", "续航/充电", "做工/耐用", "佩戴/舒适", "麦克风/通话", "功能/操作",
         "物流/包装", "价格/性价比", "客服/售后", "描述不符/假货", "音质(听感)",
         "非负面/无抱怨", "其他"]
FLOOR = 10


def parse(path):
    out, cur, fence = {}, None, False
    for ln in open(path, encoding="utf-8", errors="replace"):
        t = ln.strip()
        if t.startswith("```"):
            fence = not fence
            continue
        if fence or t.startswith(">"):
            continue
        m = re.match(r"^#{2,4}\s*(T\d{3})\b", t)
        if m:
            cur = m.group(1)
            continue
        if cur and "类型（决策方填" in t:
            mm = re.search(r"`([^`]*)`", t)
            slot = mm.group(1) if mm else ""
            nums = {int(x) for x in re.findall(r"(?<![\d])(1[0-3]|[1-9])(?![\d])", slot)}
            out[cur] = {TYPES[n - 1] for n in nums}
    return out


meta = json.load(open(os.path.join(HERE, "v2", "types_validation_ids.json"), encoding="utf-8"))
human = parse(os.path.join(HERE, "docs/gold_set/answer_sheet_types.md"))
n_all = len(meta["ids"])
print(f"答题卡：{len(human)}/{n_all} 条已判")
if len(human) < n_all:
    miss = [u for u in meta["ids"] if u not in human]
    print(f"  未填 {len(miss)} 条（示例 {miss[:5]}）→ 请填完再计分")
    sys.exit(1)

# LLM 标签
llm = {}
for line in open(os.path.join(HERE, "v2", "p1_labels.jsonl"), encoding="utf-8",
                 errors="replace"):
    try:
        rec = json.loads(line)
    except ValueError:
        continue
    llm[int(rec["row_index"])] = set(t for t in (rec.get("types") or []) if t in TYPES)
llm_by_uid = {u: llm.get(i, set()) for u, i in zip(meta["ids"], meta["row_index"])}

# 本地模型（缺失则跳过）
model_by_uid = None
mp = os.path.join(HERE, "v2", "model_types")
if os.path.isdir(mp):
    import torch
    from transformers import DistilBertForSequenceClassification, DistilBertTokenizer
    mman = json.load(open(os.path.join(HERE, "v2", "types_model_manifest.json"),
                          encoding="utf-8"))
    labels = mman["labels"]
    texts = []
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            texts.append(str(r.get("text") or ""))
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = DistilBertTokenizer.from_pretrained(mp)
    mod = DistilBertForSequenceClassification.from_pretrained(mp).to(dev).eval()
    model_by_uid = {}
    with torch.no_grad():
        idxs = meta["row_index"]
        for b in range(0, len(idxs), 64):
            e = tok([texts[i] for i in idxs[b:b + 64]], padding=True, truncation=True,
                    max_length=192, return_tensors="pt")
            e = {k: v.to(dev) for k, v in e.items()}
            probs = torch.sigmoid(mod(**e).logits).cpu().numpy()
            for j, i in enumerate(idxs[b:b + 64]):
                model_by_uid[meta["ids"][b + j]] = {labels[k] for k in range(len(labels))
                                                    if probs[j, k] >= 0.5 and labels[k] in TYPES}


def prf(pred_by_uid, c):
    tp = sum(1 for u in meta["ids"] if c in human[u] and c in pred_by_uid.get(u, set()))
    fp = sum(1 for u in meta["ids"] if c not in human[u] and c in pred_by_uid.get(u, set()))
    fn = sum(1 for u in meta["ids"] if c in human[u] and c not in pred_by_uid.get(u, set()))
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return tp, fp, fn, p, r, (2 * p * r / (p + r) if p + r else 0.0)


def macro(pred_by_uid, reportable):
    fs = [prf(pred_by_uid, c)[5] for c in reportable]
    return sum(fs) / len(fs) if fs else 0.0


reportable = [c for c in TYPES if sum(1 for u in meta["ids"] if c in human[u]) >= FLOOR]
suppressed = [c for c in TYPES if c not in reportable]
print(f"可报逐类的类（人工 ≥{FLOOR}）：{len(reportable)}｜压制（不足）：{suppressed or '无'}")
for name, pred in (("LLM", llm_by_uid), ("本地模型", model_by_uid)):
    if pred is None:
        continue
    m = macro(pred, reportable)
    ex = sum(1 for u in meta["ids"] if pred.get(u, set()) == human[u]) / len(meta["ids"])
    print(f"\n[{name}] 逐类（仅可报者）：")
    for c in reportable:
        _tp, _fp, _fn, p, r, f = prf(pred, c)
        print(f"    {c:<12} P={p:.3f} R={r:.3f} F1={f:.3f}（人工 {sum(1 for u in meta['ids'] if c in human[u])}）")
    print(f"  **宏 F1（{name}）= {m:.4f}**｜完全一致率 {ex*100:.0f}%")
out = {"n": n_all, "reportable": reportable, "suppressed": suppressed,
       "macro_llm": round(macro(llm_by_uid, reportable), 4),
       "macro_model": round(macro(model_by_uid, reportable), 4) if model_by_uid else None,
       "note": "本地模型服务于零 API 推理，非精度最优"}
json.dump(out, open(os.path.join(HERE, "v2", "types_validation_scored.json"), "w",
                    encoding="utf-8"), ensure_ascii=False, indent=2)
print("\n[写出] v2/types_validation_scored.json")
