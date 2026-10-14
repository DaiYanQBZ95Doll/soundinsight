# -*- coding: utf-8 -*-
"""生成「重测一致性」盲判卡（intra-rater reliability）：

  · 池子：三张已判卡共 292 条（p0 100 / recheck 100 / xcat 92），排除「无法判断」5 条；
  · 抽样：100 条 = 50 条原判 1 ＋ 50 条原判 0，按来源近似比例分层，种子冻结；
  · **盲**：卡内只给编号 R01–R100、原文、翻译；**不显示**原判定、模型分数、来源与臂归属；
  · 原判定与来源只写入 v2/retest_ids.json（评分脚本用），卡内一律不出现；
  · 与原始判定间隔须 ≥7 天（首批 10-05/06/07，本次 10-14 起可判）。
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261021
spec = importlib.util.spec_from_file_location("rio", os.path.join(HERE, "rulings_io.py"))
rio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rio)

CARDS = ["answer_sheet_p0_accept.md", "answer_sheet_recheck.md", "answer_sheet_xcat_accept.md"]
DOMAIN = {"answer_sheet_p0_accept.md": "耳机", "answer_sheet_recheck.md": "耳机",
          "answer_sheet_xcat_accept.md": "音箱"}


def parse_card(name):
    """返回 {id: {verdict, text, zh}}；verdict 来自 rulings_io（正规模糊解析）。"""
    p = os.path.join(HERE, "docs", "gold_set", name)
    got, _amb = rio.read_judgements(p)
    items, cur = {}, None
    for ln in open(p, encoding="utf-8"):
        s = ln.strip()
        m = re.match(r"^##\s+([A-Za-z]{1,4}\d{1,3})\b", s)
        if m:
            cur = m.group(1)
            items.setdefault(cur, {})
            continue
        if cur and s.startswith("**原文**"):
            items[cur]["text"] = s.split("**原文**：", 1)[-1].strip()
        elif cur and s.startswith("**翻译**"):
            items[cur]["zh"] = s.split("**翻译**：", 1)[-1].strip()
    for k, v in items.items():
        v["verdict"] = got.get(k)
    return {k: v for k, v in items.items() if v.get("verdict") in ("0", "1") and v.get("text")}


pool = {}
for c in CARDS:
    d = parse_card(c)
    pool[c] = d
    ones = sum(1 for v in d.values() if v["verdict"] == "1")
    print(f"  {c:32s} 可用 {len(d):4d}（原判1 {ones}）")

want1, want0 = 50, 50
picked = []
for target, want in (("1", want1), ("0", want0)):
    avail = {c: [k for k, v in pool[c].items() if v["verdict"] == target] for c in CARDS}
    tot = sum(len(v) for v in avail.values())
    alloc, rest = {}, want
    for c in CARDS[:-1]:
        n = round(want * len(avail[c]) / tot)
        n = min(n, len(avail[c]))
        alloc[c] = n
        rest -= n
    alloc[CARDS[-1]] = min(rest, len(avail[CARDS[-1]]))
    rng = random.Random(SEED + (1 if target == "1" else 2))
    for c in CARDS:
        keys = sorted(avail[c])
        rng.shuffle(keys)
        for k in keys[:alloc[c]]:
            picked.append((c, k, pool[c][k]))

rng = random.Random(SEED)
rng.shuffle(picked)          # 打乱，来源交替，避免"连着一批同源"造成判据漂移
print(f"  抽中 {len(picked)} 条｜原判1 {sum(1 for _c,_k,v in picked if v['verdict']=='1')}"
      f"｜来源 " + str({c: sum(1 for cc, _k, _v in picked if cc == c) for c in CARDS}))

rows, ids = [], []
for i, (c, k, v) in enumerate(picked, 1):
    rid = f"R{i:02d}"
    ids.append({"rid": rid, "source": c, "source_id": k, "domain": DOMAIN[c],
                "original_verdict": v["verdict"]})
    rows.append({"编号": rid, "原文": v["text"], "中文翻译": v.get("zh", ""),
                 "判定(1=是/0=不是/2=无法判断)": "", "备注(可选)": ""})

sheet = ["# 重测一致性卡（100 条，盲判）", "",
         "> **目的**：测**你自己的判据是否稳定**（intra-rater reliability）。只有一名标注者时，",
         "> 这是替代标注者间一致性（κ）的合规做法；论文中与「人机一致性」并列报告。", "",
         "> **判据（与首轮完全一致，勿改）**：**1 = 是**（该产品确实在抱怨音质/听感）｜"
         "**0 = 不是**｜**2 = 无法判断**。",
         "> 判读顺序：① 先看**产品是不是目标品类** → ② 再看**是否提到声音** → "
         "③ 再看**是不是抱怨**（褒奖不算）→ ④ 最后才考虑归因类别。", "",
         "> ⚠️ **盲判要求**：本卡**不显示**你上次的判定、模型分数、来源与臂归属；",
         "> 请**不要**去翻旧卡对照。建议**间隔 ≥7 天**（首批已满足）。",
         "> 📝 备注可选：只在犹豫/异议时写。", "",
         f"> 种子 {SEED}｜按原判定分层抽样（**分层比例不在本卡展示**，避免诱导摊平；映射见 v2/retest_ids.json）",
         "> ⏱️ 可分两段判（R01–R50、R51–R100），每段约 25 分钟。", ""]
for r in rows:
    sheet += [f"## {r['编号']}", "", f"**原文**：{r['原文']}", ""]
    if r["中文翻译"]:
        sheet += [f"**翻译**：{r['中文翻译']}", ""]
    sheet += ["**判定（决策方填）**：`___`", ""]

os.makedirs(os.path.join(HERE, "docs", "gold_set"), exist_ok=True)
open(os.path.join(HERE, "docs", "gold_set", "answer_sheet_retest.md"), "w",
     encoding="utf-8", newline="\n").write("\n".join(sheet) + "\n")
with open(os.path.join(HERE, "docs", "gold_set", "retest.csv"), "w",
          encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
json.dump({"seed": SEED, "n": len(ids), "items": ids,
           "purpose": "intra-rater reliability（单标注者条件下的重测一致性）",
           "warning": "本文件含原判定，评分用；不得进入给判定者看的卡片"},
          open(os.path.join(HERE, "v2", "retest_ids.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
# ---- 逐条盲性自检：条目块的元数据行只允许 原文/翻译/判定 三个标签（白名单，防回归） ----
_start = sheet.index("## R01") if "## R01" in sheet else 0
_allowed = ("**原文**：", "**翻译**：", "**判定（决策方填）**：")
_bad = [ln for ln in sheet[_start:] if ln.startswith("**") and not ln.startswith(_allowed)]
if _bad:
    print(f"  [FAIL] 条目块出现未授权元数据行 {len(_bad)} 条：{_bad[:2]} → 请修正生成逻辑")
    raise SystemExit(1)
print("  逐条盲性自检通过 ✓（条目块元数据行白名单校验）")

print("[写出] docs/gold_set/answer_sheet_retest.md / retest.csv / v2/retest_ids.json")
