# -*- coding: utf-8 -*-
"""生成 `docs/bus/INDEX.md`：三方卡片的一屏总览（TL;DR + 基线 + 新鲜度报警）。

设计要点（并发安全）：**INDEX 是生成物，任何人都不手工编辑**；
每张卡片记录其 mtime 与声明基线；若卡片比 INDEX 新，则在报告中标注"待刷新"。
用法：python make_bus_index.py
"""
from __future__ import annotations

import datetime
import glob
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
BUS = os.path.join(HERE, "docs", "bus")
OUT = os.path.join(BUS, "INDEX.md")
GIT = r"C:\Program Files\Git\cmd\git.exe"
AUTHORS = {"dsh": "执行方（DSH）", "kimi": "红队 Kimi", "qwen": "红队 Qwen"}


def sh(*a):
    return subprocess.run([GIT, *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=HERE).stdout.strip()


def tldr_of(path: str) -> tuple[str, list[str], str, str]:
    """抽取卡片头部：基线、时刻、TL;DR 条目（最多 5 条）。"""
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    base = ts = ""
    tldr, in_tldr = [], False
    for ln in lines:
        if "基线" in ln and not base:
            m = re.search(r"`([0-9a-f]{6,})`", ln)
            base = m.group(1) if m else "?"
            m2 = re.search(r"时刻\*\*：\s*([0-9: \-]+)", ln)
            ts = (m2.group(1).strip() if m2 else "")
        if re.match(r"^##\s*TL;DR", ln):
            in_tldr = True
            continue
        if in_tldr:
            if ln.startswith("##"):
                break
            if ln.strip():
                tldr.append(ln.strip())
    return base, tldr[:5], ts, ""


def main() -> int:
    head = sh("rev-parse", "--short", "HEAD")
    rounds = sorted(d for d in os.listdir(BUS)
                    if os.path.isdir(os.path.join(BUS, d)) and d.startswith("round-"))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = ["# 三方沟通总线 · 总览（自动生成，勿手改）", "",
           f"> 生成时刻：{now}｜当前 HEAD `{head}`｜刷新：`python make_bus_index.py`",
           "> 协议见 `docs/bus/README.md`；卡片格式见 `docs/bus/TEMPLATE.md`。", ""]
    stale = []
    for rnd in rounds:
        out += [f"## {rnd}", ""]
        cards = sorted(glob.glob(os.path.join(BUS, rnd, "*.md")))
        if not cards:
            out += ["_（本轮暂无卡片）_", ""]
        for c in cards:
            name = os.path.splitext(os.path.basename(c))[0]
            if name in ("TEMPLATE",):
                continue
            author = AUTHORS.get(name, name)
            base, tldr, ts, _ = tldr_of(c)
            mt = datetime.datetime.fromtimestamp(os.path.getmtime(c)).strftime("%m-%d %H:%M")
            if base and base != head:
                stale.append(f"{rnd}/{name}.md 基线 `{base}` ≠ 当前 `{head}`")
            out += [f"### {author}（`{rnd}/{name}.md`）", "",
                    f"- 基线 `{base}`｜卡片更新 {mt}｜声明的时刻 {ts or '—'}"]
            if tldr:
                out.append("- **TL;DR**：")
                for t in tldr:
                    out.append(f"  {t}")
            else:
                out.append("- ⚠️ 未找到 TL;DR 段（请按 TEMPLATE 补齐）")
            out.append("")
    if stale:
        out += ["## ⚠️ 基线落后提示（文件在变，请以最新 HEAD 复核）", ""]
        out += [f"- {s}" for s in stale] + [""]
    open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print(f"  [生成] docs/bus/INDEX.md｜轮次 {len(rounds)}｜卡片 "
          f"{sum(len(glob.glob(os.path.join(BUS, r, '*.md'))) for r in rounds)}｜"
          f"基线落后 {len(stale)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
