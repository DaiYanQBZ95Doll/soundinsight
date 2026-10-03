# -*- coding: utf-8 -*-
"""接收干净答题卡并计分：告警精确率、干净基线率、召回（含 CI 传导）。

真值来源：决策方在 docs/gold_set/answer_sheet_clean_alerts.md 的逐条判定（1/0/2）。
解析：rulings_io.read_judgements（唯一实现）。
抽样设计：告警臂 = 干净池中 **全部** 触发条目（15 条）；背景臂 = 随机 100 条（种子 20261005）。
故：告警精确率可直接算；基线率由背景臂估计；召回 = 告警中真阳数 ÷（池规模 × 基线率）。
"""
from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rio", os.path.join(HERE, "rulings_io.py"))
rio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rio)

POOL = json.load(open(os.path.join(HERE, "v2", "clean_alert_rate.json"),
                      encoding="utf-8"))["clean_pool"]
rows = list(csv.DictReader(open(os.path.join(HERE, "docs/gold_set/clean_alerts.csv"),
                                encoding="utf-8-sig", errors="replace")))
got, ambig = rio.read_judgements(os.path.join(HERE, "docs/gold_set/answer_sheet_clean_alerts.md"))
print(f"答题卡解析：收到 **{len(got)}/{len(rows)}** 条｜歧义 {len(ambig)}")
if ambig:
    for a in ambig[:5]:
        print("   ⚠", a)
unfilled = [r["编号"] for r in rows if r["编号"] not in got]
if unfilled:
    print(f"  未填：{len(unfilled)} 条 {unfilled[:6]}")


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


def arm(name):
    sub = [r for r in rows if r["臂"] == name and r["编号"] in got]
    y = [1 if got[r["编号"]] == "1" else 0 for r in sub]
    und = sum(1 for r in sub if got[r["编号"]] == "?")
    return sub, y, und


NAME_RE = re.compile(r"\b(noise[- ]?cancel\w*|anc\b|noise[- ]?isolat\w*|leak\w*|hiss\w*|"
                     r"static\w*|distort\w*|tinny|crackl\w*|rattle\w*|muffl\w*)\b", re.I)
res = {"pool": POOL, "received": len(got), "total_items": len(rows)}
for name in ("alert", "background"):
    sub, y, und = arm(name)
    k, n = sum(y), len(y)
    lo, hi = wilson(k, n)
    res[name] = {"n": n, "positives": k, "unclear": und, "rate": round(k / n, 4) if n else None,
                 "ci": [round(lo, 4), round(hi, 4)],
                 "ids_positive": [r["编号"] for r, yy in zip(sub, y) if yy == 1]}
    print(f"\n[{name}] n={n}｜判为「是」**{k}**｜无法判断 {und}｜"
          f"率 {k/n*100:.1f}%（Wilson 95% CI {lo*100:.1f}%–{hi*100:.1f}%）")

# 召回：告警中真阳 ÷（池规模 × 基线率）
pa = res["alert"]
pb = res["background"]
if pb["n"]:
    exp_tp = POOL * pb["rate"]
    rec = pa["positives"] / exp_tp if exp_tp else float("nan")
    # 传导：基线率取 CI 两端
    exp_hi = POOL * pb["ci"][1]
    exp_lo = POOL * pb["ci"][0]
    rec_lo = pa["positives"] / exp_hi if exp_hi else float("nan")
    rec_hi = pa["positives"] / exp_lo if exp_lo else float("nan")
    res["recall"] = {"point": round(rec, 4), "interval": [round(rec_lo, 4), round(rec_hi, 4)],
                     "expected_true_positives": round(exp_tp, 1),
                     "note": "分母用背景臂基线率；区间由基线率 Wilson CI 两端传导"}
    print(f"\n[召回] 池 {POOL:,} 条 × 基线率 {pb['rate']*100:.1f}% = 估计真阳 {exp_tp:.0f} 条；"
          f"告警中真阳 {pa['positives']} 条 → **召回 ≈ {rec*100:.1f}%**"
          f"（传导区间 {rec_lo*100:.1f}%–{rec_hi*100:.1f}%）")

# 降噪词描述性拆解（不引入新结论，仅记录口径敏感度）
anc = [(r["编号"], got[r["编号"]], r["原文"][:60]) for r in rows
       if NAME_RE.search(r["原文"]) and r["编号"] in got]
res["anc_items"] = [{"id": i, "judged": j} for i, j, _t in anc]
print(f"\n[降噪/漏音类词汇命中] {len(anc)} 条｜判定分布："
      + "｜".join(f"{v}:{sum(1 for _i, j, _t in anc if j == v)}" for v in ("1", "0", "?")))
for i, j, t in anc[:8]:
    print(f"   {i} 判={j}｜{t}")

json.dump(res, open(os.path.join(HERE, "v2", "clean_alerts_scored.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\n[写出] v2/clean_alerts_scored.json")
