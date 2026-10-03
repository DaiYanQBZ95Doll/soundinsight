# -*- coding: utf-8 -*-
"""归因校验计分：人工归因 vs ① 出厂模型（多标签 @0.5）② LLM 标签（0.8273 的评测对象）。

判读要点：0.8273 是"模型 vs **LLM** 标签"的宏 F1；本表给出"模型 vs **人工**"与
"LLM vs **人工**"，两者一对比即可回答"该数字是否被人工支持"。

用法：python score_attribution.py
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
spec = importlib.util.spec_from_file_location("rio", os.path.join(HERE, "rulings_io.py"))
rio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rio)
CLASSES = ["低音", "清晰度", "杂音", "音量", "高音"]
IDX2C = {"1": "低音", "2": "清晰度", "3": "杂音", "4": "音量", "5": "高音"}


def parse_multi(path):
    """解析判定位 → ({uid: set(classes)}, {uid: 原样文字}, {uid: 待确认原因})。

    支持：`` `1,3` ``、`` `1,3` 低音最明显，杂音轻微 ``、无引号写法、以及**自由文字备注**。
    规则（不猜）：
      · 优先取反引号内内容；无引号则取冒号后前 24 个字符里的独立数字 token；
      · token 级解析（`\\b[0-5]\\b`），避免把 "10" 之类误拆；
      · 同时出现 0 与 1–5 → **标为待确认**，不计入。
    """
    out, notes, ambig, cur, fence = {}, {}, {}, None, False
    for ln in open(path, encoding="utf-8", errors="replace"):
        t = ln.strip()
        if t.startswith("```"):
            fence = not fence
            continue
        if fence or t.startswith(">"):
            continue
        m = re.match(r"^#{2,4}\s*([AB]\d{2})\b", t)
        if m:
            cur = m.group(1)
            continue
        if cur and "归因（决策方填" in t:
            after = t.split("：", 1)[1] if "：" in t else t
            m2 = re.search(r"`([^`]*)`", after)
            slot = m2.group(1) if m2 else after[:24]
            toks = re.findall(r"(?<![\d])[0-5](?![\d])", slot)
            if not toks:                     # 无数字 → 视为未填，但保留文字
                if after.strip("`_ "):
                    notes[cur] = after.strip()
                continue
            has0 = "0" in toks
            cls = {IDX2C[d] for d in toks if d in IDX2C}
            if has0 and cls:
                ambig[cur] = f"同时出现 0 与 1–5：{after.strip()[:60]}"
                notes[cur] = after.strip()
                continue
            out[cur] = cls
            rest = after.replace(m2.group(0), "", 1) if m2 else after
            rest = rest.strip("`_ \t—–-")
            if len(rest) > 2:
                notes[cur] = rest
    return out, notes, ambig


meta = json.load(open(os.path.join(HERE, "v2", "attribution_ids.json"), encoding="utf-8"))
human, user_notes, ambig = parse_multi(os.path.join(HERE, "docs/gold_set/answer_sheet_attribution.md"))
print(f"答题卡：{len(human)}/{len(meta['row_index'])} 条已判"
      f"｜带文字备注 {len(user_notes)} 条｜待确认 {len(ambig)} 条")
if ambig:
    for u, why in list(ambig.items())[:5]:
        print(f"  ⚠️ {u}：{why}")
if len(human) < len(meta["row_index"]):
    miss = [u for u in (meta["armA"] + meta["armB"]) if u not in human]
    print(f"  未填 {len(miss)} 条（示例 {miss[:5]}）→ 请填完再计分")
    sys.exit(1)
if user_notes:
    print("\n=== 你的文字备注（原样保留，将一并归档）===")
    for u in (meta["armA"] + meta["armB"]):
        if u in user_notes:
            print(f"  {u}（判 {sorted(human[u]) or ['无法判断']}）：{user_notes[u]}")
    json.dump(user_notes, open(os.path.join(HERE, "v2", "attribution_user_notes.json"), "w",
                               encoding="utf-8"), ensure_ascii=False, indent=2)

# 模型归因（多标签 @0.5）
import importlib.util  # noqa: E402
import predict_core  # noqa: E402
st = predict_core.load()
texts = []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
uids = meta["armA"] + meta["armB"]
ridx = [meta["row_index"][uids.index(u)] if u in uids else None for u in uids]
sel = [(u, r) for u, r in zip(uids, ridx)]
ml = predict_core._ml_sigmoid(st["ml"], st["tok"], [texts[r] for _u, r in sel], st["device"])
names = st["issues"]["names"]
model_cls = {u: {names[k] for k in range(len(names)) if ml[i, k] >= 0.5}
             for i, (u, _r) in enumerate(sel)}
llm_cls = {u: set(meta["llm_classes"].get(u) or []) for u in uids}


def prf(truth, pred, c):
    tp = sum(1 for u in uids if c in truth[u] and c in pred[u])
    fp = sum(1 for u in uids if c not in truth[u] and c in pred[u])
    fn = sum(1 for u in uids if c in truth[u] and c not in pred[u])
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return tp, fp, fn, p, r, f


print(f"\n{'类':<6}{'模型 P':>8}{'模型 R':>8}{'模型 F1':>9}   {'LLM P':>8}{'LLM R':>8}{'LLM F1':>9}")
mf1s, lf1s = [], []
for c in CLASSES:
    _tp, _fp, _fn, p, r, f = prf(human, model_cls, c)
    _tp2, _fp2, _fn2, p2, r2, f2 = prf(human, llm_cls, c)
    mf1s.append(f)
    lf1s.append(f2)
    print(f"{c:<6}{p:>8.3f}{r:>8.3f}{f:>9.3f}   {p2:>8.3f}{r2:>8.3f}{f2:>9.3f}")
macro_m = sum(mf1s) / len(mf1s)
macro_l = sum(lf1s) / len(lf1s)
exact_m = sum(1 for u in uids if model_cls[u] == human[u]) / len(uids)
exact_l = sum(1 for u in uids if llm_cls[u] == human[u]) / len(uids)
jac = lambda a, b: len(a & b) / len(a | b) if (a | b) else 1.0
print(f"\n**宏 F1：模型 vs 人工 = {macro_m:.4f}｜LLM vs 人工 = {macro_l:.4f}**")
print(f"完全一致率：模型 {exact_m*100:.0f}%｜LLM {exact_l*100:.0f}%")
print(f"平均 Jaccard：模型 {sum(jac(model_cls[u], human[u]) for u in uids)/len(uids):.3f}"
      f"｜LLM {sum(jac(llm_cls[u], human[u]) for u in uids)/len(uids):.3f}")

# ---- 同子集公平对比：只在**有 LLM 类标签**的条目上比（0.8273 的真实评测面）----
sub = [u for u in uids if llm_cls[u]]
if sub:
    def macro_on(subset, pred):
        fs = []
        for c in CLASSES:
            tp = sum(1 for u in subset if c in human[u] and c in pred[u])
            fp = sum(1 for u in subset if c not in human[u] and c in pred[u])
            fn = sum(1 for u in subset if c in human[u] and c not in pred[u])
            pp = tp / (tp + fp) if tp + fp else 0.0
            rr = tp / (tp + fn) if tp + fn else 0.0
            fs.append(2 * pp * rr / (pp + rr) if pp + rr else 0.0)
        return sum(fs) / len(fs)
    m_sub = macro_on(sub, model_cls)
    l_sub = macro_on(sub, llm_cls)
    print(f"\n**同子集（有 LLM 类标签的 {len(sub)} 条）**：模型 vs 人工 **{m_sub:.4f}**"
          f"｜LLM vs 人工 **{l_sub:.4f}**")
    print(f"  ⇒ 出厂宣称 0.8273 是「模型 vs **LLM**」；此处给出「模型 vs **人工**」的同子集水平："
          f"**{m_sub:.4f}**")
out = {"n": len(uids), "macro_f1_model_vs_human": round(macro_m, 4),
       "macro_f1_llm_vs_human": round(macro_l, 4),
       "n_with_llm_classes": len(sub),
       "macro_f1_model_vs_human_subset": round(m_sub, 4) if sub else None,
       "macro_f1_llm_vs_human_subset": round(l_sub, 4) if sub else None,
       "exact_model": round(exact_m, 3), "exact_llm": round(exact_l, 3),
       "per_class": {c: dict(zip(("tp", "fp", "fn", "p", "r", "f1"),
                                 [round(x, 4) if isinstance(x, float) else x
                                  for x in prf(human, model_cls, c)])) for c in CLASSES},
       "claimed": 0.8273, "reading_limit": "n=50（有 LLM 类标签者 28）；区间较宽，只报区间与方向"}
json.dump(out, open(os.path.join(HERE, "v2", "attribution_scored.json"), "w",
                    encoding="utf-8"), ensure_ascii=False, indent=2)
print("[写出] v2/attribution_scored.json")
