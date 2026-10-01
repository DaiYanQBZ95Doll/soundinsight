# -*- coding: utf-8 -*-
"""M3c④ 评审期存活巡检：核对在线 Demo 与仓库入口是否可达。

用法：python check_demo_alive.py            # 单次巡检（追加到 docs/demo_uptime_log.md）
      python check_demo_alive.py --quiet    # 只输出结论

口径：只做**可达性**检查（HTTP 状态 + 响应时间），不判断内容正确性。
要求（契约 M3c④）：**提交前 24 h + 提交当天**各巡检一次，日志留证。
"""
from __future__ import annotations

import datetime
import os
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "docs", "demo_uptime_log.md")
TARGETS = [
    ("ModelScope 空间页", "https://modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight"),
    ("应用直链", "https://daiyanqbz95doll-soundinsight.ms.show"),
    ("GitCode 仓库", "https://gitcode.com/DaiYanQBZ95Doll/soundinsight"),
    ("GitHub 仓库", "https://github.com/DaiYanQBZ95Doll/soundinsight"),
]
HEADER = ("# 在线 Demo 存活巡检日志（M3c④）\n\n"
          "> 口径：仅可达性（HTTP 状态 + 响应时间），不判断内容正确性。\n"
          "> 要求：**提交前 24 h + 提交当天**各巡检一次（`python check_demo_alive.py`）。\n\n"
          "| 时刻 | 目标 | 状态 | 响应 | 判定 |\n|---|---|---|---|---|\n")


def probe(url: str, timeout: int = 20) -> tuple[int | None, float, str]:
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "SoundInsight-uptime-check"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, time.time() - t0, ""
    except urllib.error.HTTPError as e:
        return e.code, time.time() - t0, f"HTTPError {e.code}"
    except Exception as e:  # noqa: BLE001
        return None, time.time() - t0, f"{type(e).__name__}: {str(e)[:60]}"


def main() -> int:
    quiet = "--quiet" in sys.argv
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows, all_ok = [], True
    for name, url in TARGETS:
        status, dt, err = probe(url)
        ok = status is not None and status < 400
        all_ok = all_ok and ok
        rows.append((name, status, dt, ok, err))
        if not quiet:
            print(f"  [{'OK  ' if ok else 'FAIL'}] {name:<16} "
                  f"{status if status else '—':>4}  {dt:5.1f}s  {err}")
    if not os.path.isfile(LOG):
        with open(LOG, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(HEADER)
    with open(LOG, "a", encoding="utf-8", newline="\n") as fh:
        for name, status, dt, ok, err in rows:
            fh.write(f"| {ts} | {name} | {status if status else '—'} | {dt:.1f}s | "
                     f"{'可达' if ok else '不可达（' + err + '）'} |\n")
    print("  提示：契约要求 10/7（提交前 24 h）与 10/8（提交当天）各巡检一次")
    print(f"\n[巡检 {ts}] {'全部可达 ✓' if all_ok else '**有目标不可达**'}"
          f"｜日志 -> docs/demo_uptime_log.md")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
