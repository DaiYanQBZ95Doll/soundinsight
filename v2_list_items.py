# -*- coding: utf-8 -*-
"""列出 A-必做表的每项状态（提取行首编号与完成标记）。"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s = open("docs/frozen_execution_checklist.md", encoding="utf-8").read()
# 取 §二 到 §三 之间
i = s.find("## 二、冻结范围")
j = s.find("## 三、")
seg = s[i:j]
rows = [ln for ln in seg.splitlines() if ln.startswith("| **")]
print(f"A-必做/尽力 行数：{len(rows)}\n")
todo = []
for ln in rows:
    m = re.match(r"\|\s*\*\*([A-Za-z0-9\-\u4e00-\u9fff]+)\*\*\s*([^|]*)\|", ln)
    if not m:
        continue
    item, status = m.group(1), m.group(2).strip()
    mark = "✅" if "✅" in status else ("🟡" if "🟡" in status else ("⛔" if "⛔" in status else "—"))
    if mark in ("—", "🟡", "⛔"):
        todo.append((item, mark, status[:60]))
    print(f"  {mark} {item:<8} {status[:70]}")
print(f"\n未完成/待定项（{len(todo)}）：")
for item, mark, st in todo:
    print(f"  {mark} {item}: {st}")
