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


def chain_is_green() -> tuple[bool, str]:
    """读门槛链的机器可读结果：失败项非空 → 不绿。"""
    import json as _json
    import os as _os
    p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "v2", "checks_result.json")
    if not _os.path.isfile(p):
        return False, "未找到门槛链结果（请先跑 run_all_checks.py）"
    try:
        d = _json.load(open(p, encoding="utf-8"))
    except ValueError:
        return False, "门槛链结果文件损坏"
    failed = d.get("failed") or []
    if failed:
        return False, f"门槛链有 {len(failed)} 项失败：{failed}｜运行于 {d.get('ts')}"
    # 时效：链结果必须来自当前 HEAD，否则视为过期（防"用旧绿链放行新改动"）
    import subprocess as _sp
    try:
        head = _sp.run(["git", "rev-parse", "--short", "HEAD"], cwd=_os.path.dirname(
            _os.path.abspath(__file__)), capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        head = ""
    if d.get("head") and head and d["head"] != head:
        return False, (f"门槛链结果过期：结果来自 {d['head']}，当前 HEAD 为 {head}"
                       "——请重跑 run_all_checks.py")
    return True, f"门槛链全绿（{d.get('steps')} 步，{d.get('ts')}，HEAD {d.get('head')}）"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message", action="append", required=True)
    ap.add_argument("--allow-guard-fail", action="store_true")
    ap.add_argument("--require-green-chain", action="store_true",
                    help="门槛链有失败项时拒绝提交（读 v2/checks_result.json）")
    args = ap.parse_args()

    rc, out = run([sys.executable, "precommit_guard.py"])
    print(out.strip())
    if rc != 0 and not args.allow_guard_fail:
        print("[安全提交] 守卫未通过 → 已阻止提交（如需强制，用 --allow-guard-fail 并说明理由）")
        return 1
    if getattr(args, "require_green_chain", False):
        ok, why = chain_is_green()
        print(f"[安全提交] 门槛链：{why}")
        if not ok:
            print("[安全提交] 门槛链未通过 → 已阻止提交")
            return 1

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
