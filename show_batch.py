# -*- coding: utf-8 -*-
"""打印紧凑批次（供聊天中使用，一屏可读）。用法：python show_batch.py [N]"""
import csv
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
COL = "人工判定(1=音质差评/0=不是)"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
rows = list(csv.DictReader(open("docs/gold_set/assisted_worksheet.csv", encoding="utf-8-sig")))
todo = [r for r in rows if not (r.get(COL) or "").strip()][:N]
out = []
for i, r in enumerate(todo, 1):
    out.append(f"[{i}] {r['编号']}｜产品：{r.get('产品') or '?'}")
    out.append(f"    原：{r['原文'][:160]}")
    zh = (r.get("中文翻译") or "")[:120]
    out.append(f"    译：{zh}")
print("\n".join(out))
print(f"\n（本批 {len(todo)} 条；判完回 {len(todo)} 个数字，例如：" + " ".join(["1"] * len(todo)) + "）")
