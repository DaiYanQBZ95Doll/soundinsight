# -*- coding: utf-8 -*-
"""每日一次推送（决策方 2026-10-01 定：网络不可靠，降低推送频率到每天一次）。

设计：
  · **本地提交照旧即时**（提交是本地操作，不受网络影响）；只有**推送**限频。
  · `--status`：只看状态（待推送提交数、各远端是否落后、上次成功推送时间）——**永远 exit 0**，
    供门槛链作为非致命信息步使用。
  · 默认（推送模式）：若"今天已对所有可达远端成功推送过"则**跳过**；否则带重试推送，
    逐远端记录成功/失败；失败**不阻塞**后续工作（下次再试）。
  · `--force`：忽略"今天已成功"的限制，立即再试一次。

状态文件：`v2/push_log.json`
用法：
    python push_daily.py --status
    python push_daily.py
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "v2", "push_log.json")
GIT = r"C:\Program Files\Git\cmd\git.exe"
REMOTES = ("gitcode", "origin")
BRANCH = "main"


def git(*args, timeout=90):
    try:
        r = subprocess.run([GIT, *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=HERE, timeout=timeout)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def head() -> str:
    return git("rev-parse", "--short", "HEAD")[1]


def remote_sha(remote: str):
    rc, out, err = git("ls-remote", remote, f"refs/heads/{BRANCH}", timeout=60)
    if rc != 0 or not out:
        return None, (err or "查询失败")[:90]
    return out.split()[0][:7], ""


def load_log() -> dict:
    if os.path.isfile(LOG):
        try:
            return json.load(open(LOG, encoding="utf-8"))
        except ValueError:
            pass
    return {"history": [], "last_success": {}}


def save_log(d: dict) -> None:
    d["history"] = d.get("history", [])[-40:]
    json.dump(d, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def today() -> str:
    return datetime.date.today().isoformat()


def status_lines(verbose: bool = True):
    """返回 (需推送的行, 全远端都今日已成功的布尔)。"""
    h = head()
    rc, cnt, _ = git("rev-list", "--count", f"{REMOTES[0]}/{BRANCH}..HEAD")
    pending = cnt if rc == 0 and cnt.isdigit() else "?"
    log = load_log()
    lines = [f"本地 HEAD {h}｜相对 {REMOTES[0]}/{BRANCH} 待推送 {pending}"]
    all_ok_today = True
    for r in REMOTES:
        sha, err = remote_sha(r)
        last = (log.get("last_success") or {}).get(r, {})
        last_s = f"{last.get('at', '—')}（{last.get('sha', '—')}）" if last else "—"
        if sha is None:
            lines.append(f"  {r}: 不可达（{err}）｜上次成功 {last_s}")
            all_ok_today = False
        elif sha == h:
            lines.append(f"  {r}: 已同步 ✓｜上次成功 {last_s}")
            if last.get("date") != today():
                all_ok_today = False
        else:
            lines.append(f"  {r}: **落后**（远端 {sha}）｜上次成功 {last_s}")
            all_ok_today = False
    return lines, all_ok_today


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--retries", type=int, default=2)
    args = ap.parse_args()

    lines, all_ok_today = status_lines()
    if args.status:
        print("## 推送状态（每日一次）")
        for ln in lines:
            print("- " + ln)
        print(f"- 今日状态：{'所有可达远端均已同步' if all_ok_today else '**存在落后或未达**'}"
              f"｜推送频次规则：每天一次（`python push_daily.py`）")
        return 0

    h = head()
    log = load_log()
    if all_ok_today and not args.force:
        print(f"[跳过] 今天已成功推送（{today()}），且各可达远端均与本地一致")
        return 0

    results = {}
    for r in REMOTES:
        sha, err = remote_sha(r)
        if sha == h and (log.get("last_success") or {}).get(r, {}).get("date") == today():
            print(f"[跳过] {r} 今日已成功且一致")
            results[r] = "skip"
            continue
        ok = False
        for attempt in range(1, args.retries + 1):
            rc, out, err2 = git("push", r, BRANCH, timeout=300)
            if rc == 0:
                ok = True
                print(f"[成功] {r} 第 {attempt} 次尝试：{out.splitlines()[-1][:80] if out else 'pushed'}")
                break
            print(f"[重试] {r} 第 {attempt} 次失败：{(err2 or out)[:100]}")
            time.sleep(3 * attempt)
        if ok:
            (log.setdefault("last_success", {}))[r] = {"date": today(), "sha": h,
                                                       "at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
        results[r] = "ok" if ok else "fail"
        log.setdefault("history", []).append(
            {"date": today(), "at": datetime.datetime.now().strftime("%H:%M:%S"),
             "remote": r, "result": results[r], "sha": h})
    save_log(log)
    fails = [r for r, v in results.items() if v == "fail"]
    print(f"\n[汇总] 成功 {sum(1 for v in results.values() if v == 'ok')}｜"
          f"跳过 {sum(1 for v in results.values() if v == 'skip')}｜失败 {len(fails)}"
          + (f"（{', '.join(fails)}——网络问题不阻塞工作，下次自动重试）" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
