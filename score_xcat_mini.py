# -*- coding: utf-8 -*-
"""跨品类试点 mini 金标计分：① 现货正例的**真人确认率**（决定是否开训）；② 同域负例纯度。

判定规则（事先约定）：确认率 ≥70% → 按防火墙②开训；<70% → 试点降级为方向性证据（不进包）。
"""
from __future__ import annotations

import collections
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

meta = json.load(open(os.path.join(HERE, "v2", "xcat_mini_ids.json"), encoding="utf-8"))
got, amb = rio.read_judgements(os.path.join(HERE, "docs/gold_set/answer_sheet_xcat_mini.md"))
print(f"已判 {len(got)}/{len(meta['ids'])}｜歧义 {len(amb)}")
if len(got) < len(meta["ids"]):
    miss = [u for u in meta["ids"] if u not in got]
    print(f"  未填：{miss}")
    sys.exit(1)


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


pos = [(u, c) for u, c in zip(meta["ids"], meta["candidate"]) if c == "正例候选"]
neg = [(u, c) for u, c in zip(meta["ids"], meta["candidate"]) if c == "负例候选"]
res = {}
for label, group in (("正例候选（现货）", pos), ("同域负例候选", neg)):
    vals = [got[u] for u, _ in group]
    cnt = collections.Counter(vals)
    n1, n0 = cnt.get("1", 0), cnt.get("0", 0)
    nu = cnt.get("?", 0)
    decided = n1 + n0
    rate = n1 / decided if decided else float("nan")
    lo, hi = wilson(n1, decided) if decided else (float("nan"), float("nan"))
    print(f"\n[{label}] n={len(group)}｜是 {n1}／不是 {n0}／无法判断 {nu}"
          f" → **确认率 {rate*100:.1f}%**（Wilson 95% CI {lo*100:.0f}–{hi*100:.0f}%，分母 {decided}）")
    res[label] = {"n": len(group), "yes": n1, "no": n0, "unclear": nu,
                  "rate": round(rate, 4), "ci": [round(lo, 4), round(hi, 4)]}

# 备注归类（看失败是"产品不是音箱"还是"不是在抱怨"）
notes = []
cur = None
for ln in open(os.path.join(HERE, "docs/gold_set/answer_sheet_xcat_mini.md"),
               encoding="utf-8", errors="replace"):
    t = ln.rstrip()
    m = re.match(r"^#{2,4}\s*(M\d{1,3})", t.strip())
    if m:
        cur = m.group(1)
        continue
    if cur and "判定（决策方填）" in t and got.get(cur) in ("0", "?"):
        note = t.split("`")[-1].strip()
        if note:
            notes.append((cur, got[cur], note))
print(f"\n非正例条目的备注（{len(notes)} 条有备注）：")
for u, v, nt in notes:
    print(f"  {u}[{v}]：{nt[:88]}")
# 粗归类
kinds = collections.Counter()
for _u, _v, nt in notes:
    if re.search(r"不是音箱|非音箱|太阳镜|显示器|键盘|手机|收音机|线材|不是耳机|品类", nt):
        kinds["产品品类误判"] += 1
    elif re.search(r"赞扬|褒奖|不是抱怨|没抱怨|好评|没有问题|正向", nt):
        kinds["非抱怨（褒奖）"] += 1
    elif re.search(r"连接|配对|续航|充电|做工|断|故障|功能|物|延迟", nt):
        kinds["功能故障非音质"] += 1
    else:
        kinds["其他/未归类"] += 1
print(f"\n粗归类：{dict(kinds)}")
verdict = ("**≥70% → 按防火墙②开训**" if res["正例候选（现货）"]["rate"] >= 0.70
           else "**<70% → 试点降级为方向性证据（不进提交包）**")
print(f"\n[裁定规则] 确认率 {res['正例候选（现货）']['rate']*100:.1f}% ⇒ {verdict}")
json.dump({"scored": res, "note_kinds": dict(kinds), "rule": "≥70% 开训，<70% 仅作方向性证据"},
          open(os.path.join(HERE, "v2", "xcat_mini_scored.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[写出] v2/xcat_mini_scored.json")
