# -*- coding: utf-8 -*-
"""机械门：禁报数字不得出现在对外材料（R5 扩展 + 红队裁定）。

规则：
  · 下列"撤回"数字出现在对外材料即 FAIL（除非该行同时含撤回/作废/禁报等字样）；
  · docs/extrapolation_register.md 自身：状态非撤回且填了点估计却无区间的行 → FAIL。

用法：python check_retracted_numbers.py   （0=通过，1=违规）
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = ["build_finals_content.py", "build_finals_appendix.py",
           "docs/N1_narrative_mainline.md", "docs/N2_narrative_final.md",
           "docs/N5_qna_factbase.md", "docs/N6_review_risk_list.md",
           "docs/roadshow_slides_corrections.md", "README.md"]
# 撤回数字（上下文锚定，避免误报）
PATTERNS = [r"0\.381", r"0\.471", r"2,?168", r"305\s*条", r"\$4\.2", r"4\.2\s*美元",
            r"7[–\-]10\s*%", r"检出\s*45\s*%", r"45\s*%.{0,6}检出",
            r"结构性漏检\s*37", r"37\s*%.{0,6}结构性", r"3/3\s*命中", r"命中\s*3/3",
            r"留出侧\s*74\s*条", r"召回上界\s*7"]
EXEMPT = ("撤回", "作废", "禁报", "不得", "已废", "不再是")


def main() -> int:
    bad = []
    for rel in TARGETS:
        p = os.path.join(HERE, rel)
        if not os.path.isfile(p):
            continue
        for i, ln in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
            if any(e in ln for e in EXEMPT):
                continue
            for pat in PATTERNS:
                if re.search(pat, ln):
                    bad.append(f"{rel}:{i} 命中禁报数字 /{pat}/：{ln.strip()[:80]}")
    # 登记表自洽
    reg = os.path.join(HERE, "docs", "extrapolation_register.md")
    if os.path.isfile(reg):
        for i, ln in enumerate(open(reg, encoding="utf-8", errors="replace"), 1):
            if not ln.startswith("| X-"):
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) < 10:
                continue
            point, interval, status = cells[4], cells[5], cells[9]
            if point and point not in ("—", "-") and (not interval or interval in ("—", "-")) \
                    and "撤回" not in status and "方向" not in status:
                bad.append(f"extrapolation_register.md:{i} 有点估计却无区间：{cells[0]}")
    print("## 禁报数字机械门（R5 扩展）")
    if bad:
        for b in bad:
            print(f"- [FAIL] {b}")
    else:
        print(f"- [PASS] 未发现禁报数字（扫描 {len(TARGETS)} 个对外材料）"
              f"；登记表自洽性通过")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
