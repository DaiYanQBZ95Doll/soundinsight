# -*- coding: utf-8 -*-
"""把「正文/附录生成器语法 + docx 构建」纳入门槛链（本次事故的机制化）。

事故：build_finals_appendix.py 因中文里的 ASCII 引号出现语法错误，
但 24 步门槛链**全绿**——因为 docx 构建（消费这两个模块）不在链里，
导致"材料源码坏了但链不报"的盲区。

本检查做三件事：① 两个生成器可解析；② 能成功构建 docx；③ 产物存在且非空。
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
MODS = ["build_finals_content.py", "build_finals_appendix.py", "build_finals_docx2.py"]


def main() -> int:
    bad = []
    for m in MODS:
        p = os.path.join(HERE, m)
        if not os.path.isfile(p):
            bad.append(f"{m} 不存在")
            continue
        try:
            ast.parse(open(p, encoding="utf-8").read())
        except SyntaxError as e:
            bad.append(f"{m} 语法错误：{e}")
    if not bad:
        r = subprocess.run([sys.executable, "build_finals_docx2.py"], cwd=HERE,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0:
            bad.append(f"docx 构建失败（rc={r.returncode}）：{out.strip()[-200:]}")
        else:
            docx = [f for f in os.listdir(HERE) if f.endswith(".docx")
                    and f.startswith("更新世界的锋芒_SoundInsight_决赛")]
            if not docx or os.path.getsize(os.path.join(HERE, docx[0])) < 10000:
                bad.append("docx 产物缺失或过小")
            else:
                print(f"- [OK] 生成器语法与 docx 构建正常（{docx[0]}，"
                      f"{os.path.getsize(os.path.join(HERE, docx[0])):,} B）")
    print("## 材料生成器与 docx 构建")
    for b in bad:
        print(f"- [FAIL] {b}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
