# -*- coding: utf-8 -*-
"""历史内容掩码：把全部历史提交中的 sk- 系列密钥替换为掩码形式（供 git filter-branch --tree-filter 调用）。

背景：`docs/repo_hygiene_scan.md` 的**历史版本**曾逐字打印一个真实 Token Plan 密钥，
使"卫生报告"本身成为历史中的凭据残留。删除文件不够，必须改写历史中的**文件内容**。

用法（由 purge 脚本调用）：
    git filter-branch -f --tree-filter "python mask_history_secrets.py" -- --all
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PAT = re.compile(r"sk-[A-Za-z0-9._\-]{24,}")
MAX_BYTES = 20 * 1024 * 1024


def main() -> int:
    changed = []
    for root, dirs, files in os.walk("."):
        if ".git" in dirs:
            dirs.remove(".git")
        for fn in files:
            p = os.path.join(root, fn)
            try:
                if os.path.getsize(p) > MAX_BYTES:
                    continue
                raw = open(p, "rb").read()
            except OSError:
                continue
            try:
                s = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if "sk-" not in s:
                continue
            new = PAT.sub(lambda m: m.group(0)[:6] + "…<redacted:历史掩码>", s)
            if new != s:
                with open(p, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new)
                changed.append(p)
    if changed:
        print(f"[mask] 改写 {len(changed)} 个文件：{changed[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
