# -*- coding: utf-8 -*-
"""检查：判定解析逻辑**单点实现**（R32 的机械化）。

由来：本会话出现 6 种填写写法，解析逻辑被复制到 4 个工具里，每遇到一种新写法就要改 4 处、
且每次都漏改一处。红队 Qwen 指出「R32 只是纪律不是机制」——本检查即其机制。

规则：
  · 解析实现只允许出现在 `rulings_io.py`；
  · 其他文件里若出现解析标志即 FAIL——**但「委托型薄包装」豁免**：
    函数体里调用了 `rulings_io.*` 的包装函数不算重复实现。

用法：python check_single_parser.py   （退出码 0=通过，1=存在重复实现）
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ALLOWED = {"rulings_io.py"}
FUNC_MARKERS = ("read_judgements", "_slot_value", "import_from_notes", "parse_inline_text")
CONST_MARKERS = ("PAT_INLINE = re.compile", "PAT_TABLE = re.compile",
                 "pat_id = re.compile", "pat_inline = re.compile")
SKIP_DIRS = {".git", "__pycache__", "_tmp_selftest", "vendor", "node_modules"}


def function_body(src: str, name: str) -> str:
    """取 `def name(` 的函数体（到下一个顶层 def 或文件末尾）。"""
    m = re.search(r"^def\s+" + re.escape(name) + r"\s*\(", src, re.M)
    if not m:
        return ""
    nxt = re.search(r"^def\s", src[m.end():], re.M)
    return src[m.start():m.end() + (nxt.start() if nxt else len(src) - m.end())]


def main() -> int:
    bad, scanned = [], 0
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".py") or f in ALLOWED:
                continue
            rel = os.path.relpath(os.path.join(root, f), HERE).replace("\\", "/")
            if (rel.startswith("v2_") or rel.startswith("test_")
                    or rel == "check_single_parser.py"):
                continue
            scanned += 1
            try:
                src = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for name in FUNC_MARKERS:
                body = function_body(src, name)
                if body and "rulings_io" not in body:
                    bad.append(f"{rel}：本地实现 def {name}(…)")
            for c in CONST_MARKERS:
                if c in src:
                    bad.append(f"{rel}：本地实现常量 {c}")
    print("## 判定解析单点实现（R32）")
    if bad:
        for b in bad:
            print(f"- [FAIL] 重复的解析实现：{b}")
        print("- 修法：删除本地实现，改为 `import rulings_io` 并调用其函数")
    else:
        print(f"- [PASS] 未发现重复实现（扫描 {scanned} 个 .py；唯一实现 `rulings_io.py`）")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
