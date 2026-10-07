# -*- coding: utf-8 -*-
"""依赖前置检查（链的第一步）：把"环境缺包"变成一条明确指令，而不是 4 个莫名 FAIL。

动机（2026-10-07）：决策方运行链时，docx 构建 → No module named 'docx'、包内 e2e →
No module named 'pandas'；终端只显示截断的 traceback，排查花了数轮。真实原因是他那边的
`python` 指向未装依赖的解释器（我方为 C:\\Python312）。
"""
from __future__ import annotations

import importlib
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

# 模块名 → pip 包名（仅列链与产品实际用到的）
DEPS = [("docx", "python-docx"), ("pandas", "pandas"), ("numpy", "numpy"),
        ("torch", "torch"), ("transformers", "transformers"), ("sklearn", "scikit-learn"),
        ("requests", "requests"), ("openpyxl", "openpyxl")]


def main() -> int:
    missing = []
    for mod, pkg in DEPS:
        try:
            importlib.import_module(mod)
        except Exception as e:  # noqa: BLE001
            missing.append((mod, pkg, type(e).__name__))
    print("## 依赖前置检查")
    print(f"- 解释器：`{sys.executable}`（Python {sys.version.split()[0]}）")
    if not missing:
        print(f"- 依赖齐全 ✓（检查 {len(DEPS)} 项）")
        return 0
    print(f"- [FAIL] 缺少 **{len(missing)}** 项依赖：" +
          "、".join(f"{m}（pip: {p}）" for m, p, _e in missing))
    print(f"- **修复**：`\"{sys.executable}\" -m pip install " +
          " ".join(p for _m, p, _e in missing) + "`")
    print("- 或改用已装好依赖的解释器运行整条链，例如："
          "`C:\\Python312\\python.exe run_all_checks.py`")
    print("- 说明：本检查为**环境问题**，不代表产物有问题——产物由已装依赖的解释器构建。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
