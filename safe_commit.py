# -*- coding: utf-8 -*-
"""安全提交：先跑预提交守卫，**只有 PASS 才执行 git commit**。

背景（2026-10-01 事故）：手工依次执行 `git add` → `precommit_guard.py` → `git commit` 时，
若没检查守卫退出码，守卫拦下的文件仍会被提交（当时把 44 MB 决赛包提交入库）。

用法：
    python safe_commit.py -m "提交信息" [-m "正文"] [--allow-guard-fail]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GIT = r"C:\Program Files\Git\cmd\git.exe"


def run(args: list[str]) -> tuple[int, str]:
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=HERE)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message", action="append", required=True)
    ap.add_argument("--allow-guard-fail", action="store_true")
    args = ap.parse_args()

    rc, out = run([sys.executable, "precommit_guard.py"])
    print(out.strip())
    if rc != 0 and not args.allow_guard_fail:
        print("[安全提交] 守卫未通过 → 已阻止提交（如需强制，用 --allow-guard-fail 并说明理由）")
        return 2

    cmd = [GIT, "-c", "core.quotepath=false", "commit", "-q"]
    for m in args.message:
        cmd += ["-m", m]
    rc2, out2 = run(cmd) if os.name != "nt" else run(cmd)
    if rc2 != 0:
        print(f"[安全提交] 提交失败（{rc2}）：{out2.strip()[:400]}")
        return rc2
    _, head = run([GIT, "rev-parse", "--short", "HEAD"])
    _, pending = run([GIT, "rev-list", "--count", "gitcode/main..HEAD"])
    print(f"[安全提交] 成功 → HEAD {head.strip()}｜待推送 {pending.strip()} 个提交")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
