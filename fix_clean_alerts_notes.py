# -*- coding: utf-8 -*-
"""修复干净答题卡的翻译错配：缓存按 **row_index** 重键，并全部重生成（115 条，约 $0.02）。

错因：缓存以顺序编号 K001… 为键，而两轮选取的条目不同 → 约 85 条的译文与原文不对应。
修法：键改为 `ridx:<row_index>`（稳定身份），并写新缓存文件，旧的作废。
"""
from __future__ import annotations

import concurrent.futures as cf
import csv
import importlib.util
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

spec = importlib.util.spec_from_file_location("mgn", os.path.join(HERE, "make_gold_set_notes.py"))
mgn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mgn)

rows = list(csv.DictReader(open(os.path.join(HERE, "docs/gold_set/clean_alerts.csv"),
                                encoding="utf-8-sig", errors="replace")))
print(f"条目 {len(rows)}｜臂分布：" + "｜".join(
    f"{a} {sum(1 for r in rows if r['臂'] == a)}" for a in {r['臂'] for r in rows}))

cache = os.path.join(HERE, "v2", "clean_alerts_notes_ridx.jsonl")
done = {}
if os.path.isfile(cache):
    for line in open(cache, encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "zh" in rec:
            done[str(rec["uid"])] = rec
todo = [(f"ridx:{r['row_index']}", r["原文"]) for r in rows
        if f"ridx:{r['row_index']}" not in done]
print(f"已缓存 {len(done)}｜需生成 {len(todo)}")
key = os.environ.get("DEEPSEEK_API_KEY", "")
if todo and key:
    with open(cache, "a", encoding="utf-8") as fh, cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(mgn.call, t, key): u for u, t in todo}
        for k, fut in enumerate(cf.as_completed(futs), 1):
            fh.write(json.dumps({"uid": futs[fut], **fut.result()}, ensure_ascii=False) + "\n")
            if k % 25 == 0:
                fh.flush()
                print(f"  …{k}/{len(todo)}")
notes = {}
for line in open(cache, encoding="utf-8", errors="replace"):
    try:
        rec = json.loads(line)
    except ValueError:
        continue
    if "zh" in rec:
        notes[str(rec["uid"])] = rec

# 重写 CSV 与答题卡（保持原编号与臂序，只替换翻译/解释）
out_rows = []
for r in rows:
    d = notes.get(f"ridx:{r['row_index']}", {})
    r["中文翻译"] = d.get("zh", "")
    r["_prod"] = d.get("product", "") or "不确定"
    r["_snd"] = d.get("sound", "") or "未提及声音相关内容"
    r["_oth"] = d.get("other", "")
    out_rows.append(r)
with open(os.path.join(HERE, "docs/gold_set/clean_alerts.csv"), "w", encoding="utf-8-sig",
          newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["编号", "臂", "row_index", "v1_prob", "原文", "中文翻译",
                "人工判定(1=音质差评/0=不是)", "备注"])
    for r in out_rows:
        w.writerow([r["编号"], r["臂"], r["row_index"], r["v1_prob"], r["原文"],
                    r["中文翻译"], "", ""])

sheet = ["# 干净告警精确率 · 答题卡（留出侧 + 闸门外 + 从未训练）", "",
         f"> **{len(out_rows)} 条**：告警臂 **{sum(1 for r in out_rows if r['臂'] == 'alert')}** 条"
         f"（v1 分数 ≥0.5，即「产品会报警的那些」）＋ 背景臂 "
         f"**{sum(1 for r in out_rows if r['臂'] == 'background')}** 条（随机，用于基线率）", "",
         "> 全部取自**留出侧**、**闸门外**、**从未被训练也从未被人工判过**——"
         "是当前**唯一无污染**的人工评测集。", "",
         "> 编码：**1 = 是**（在说耳机/耳塞/头戴的音质）｜**0 = 不是**｜**2 = 无法判断**", "",
         "> ⚠️ 判定口径待决策方确认（D-Q9）：「**降噪差／降噪过强**」算不算「音质」——"
         "请在首批判定时一并定下，我会据此统一统计。", ""]
for r in out_rows:
    sheet += [f"## {r['编号']}　[{r['臂']}]　（v1 分数 {r['v1_prob']}）", "",
              f"**原文**：{r['原文']}", "",
              f"**翻译**：{r['中文翻译']}", "",
              f"**解释**：产品：{r['_prod']}｜声音：{r['_snd']}｜其他：{r['_oth']}", "",
              "**判定（决策方填）**：`___`", ""]
open(os.path.join(HERE, "docs/gold_set/answer_sheet_clean_alerts.md"), "w", encoding="utf-8",
     newline="\n").write("\n".join(sheet) + "\n")
print(f"[写出] answer_sheet_clean_alerts.md / clean_alerts.csv（{len(out_rows)} 条，翻译已重键）")
