# -*- coding: utf-8 -*-
"""修复 round-10 登记脚本造成的清单截断：从 e9d92ba 恢复，并正确追加 W4 进展。

同时做**损伤扫描**：对比 e9d92ba → HEAD 各跟踪文件的大小变化，列出"异常缩小"的文件
（排除预期缩小的：被删除的临时文件、重建的产物）。
"""
from __future__ import annotations

import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GIT = r"C:\Program Files\Git\cmd\git.exe"
HERE = r"C:\deepseek-harness-master\soundinsight"
TARGET = "docs/frozen_execution_checklist.md"
GOOD_REV = "e9d92ba"


def git(*args: str) -> str:
    return subprocess.run([GIT, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=HERE).stdout


def size_at(rev: str, path: str) -> int | None:
    out = subprocess.run([GIT, "cat-file", "-s", f"{rev}:{path}"], capture_output=True,
                         text=True, cwd=HERE)
    return int(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None


# ---------- 1) 损伤扫描 ----------
files = [f for f in git("ls-tree", "-r", "--name-only", GOOD_REV).splitlines() if f]
shrunk = []
for f in files:
    a, b = size_at(GOOD_REV, f), size_at("HEAD", f)
    if a and b and b < a * 0.6 and a > 3000:
        shrunk.append((f, a, b))
print(f"=== 损伤扫描（{GOOD_REV} → HEAD，缩小 >40% 且原 >3KB 的文件）===")
for f, a, b in shrunk:
    print(f"  {f}: {a} → {b} B（−{(1-b/a)*100:.0f}%）")
if not shrunk:
    print("  （无）")

# ---------- 2) 恢复清单 ----------
good = git("show", f"{GOOD_REV}:{TARGET}")
if not good:
    print(f"[FAIL] 无法从 {GOOD_REV} 读取 {TARGET}")
    raise SystemExit(1)
print(f"\n[恢复] {TARGET}：{GOOD_REV} 版本 {len(good.encode('utf-8'))} B")

# ---------- 3) 正确追加 W4 进展（table 行内追加，保留后半段） ----------
i = good.find("| **W4** ⛔ **阻塞（待人工凭证）**")
if i < 0:
    print("[注意] 未找到 W4 行锚点，仅做恢复")
else:
    j = good.find("\n", i)
    row = good[i:j]
    extra = (" **进展（2026-09-30/10-01）**：**候选段已完成**——4–5★ 音质相关候选 **12,744 条**"
             "（5★ 9,185／4★ 3,559），为预期 ≈300 的 **42 倍** → **W4b 上界规则触发**，"
             "已按（星级×主关键词）39 组分层等距抽样抽出 **293 条**（`v2/w4_sample.csv`，"
             "未复核比例 **97.70%**）。**复核段仍缺凭证**：探测顺序与放行守则见 "
             "`docs/llm_credential_status.md`（DSH 配置期望 `QWEN_TOKEN_PLAN_API_KEY` 等；"
             "`deepseek-account` 由 harness 内部管理、子进程读不到）。凭证到位后执行："
             "`python v2_w4_mine.py --review --limit 300`（支持断点续跑）。 | 执行方 |⛔ 阻塞（复核段）|")
    good = good[:i] + row.rstrip(" |") + extra + good[j:]
    print(f"[登记] W4 行已追加进展（新长度 {len(good.encode('utf-8'))} B）")

open(f"{HERE}/{TARGET.replace('/', chr(92))}", "w", encoding="utf-8", newline="\n").write(good)
print(f"[写出] {TARGET}")
