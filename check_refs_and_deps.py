# -*- coding: utf-8 -*-
"""两项交付质量核查。

A. **断链检查**：扫描全部跟踪的 .md 里反引号包裹的文件名（*.py/*.md/*.csv/*.json/*.docx/*.zip/*.png），
   报告"被引用但不存在"的路径——评委或接手者按图索骥时会撞墙的那种。

B. **依赖声明检查**：解析产品模块的 import，与 requirements.txt 比对：
   第三方包是否都声明？是否声明了不存在的包名？
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GIT = r"C:\Program Files\Git\cmd\git.exe"

# ---------- A. 断链检查 ----------
files = subprocess.run([GIT, "-c", "core.quotepath=false", "ls-files", "*.md"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=HERE).stdout.split()
PAT = re.compile(r"`([A-Za-z0-9_./\-\u4e00-\u9fff]+\.(?:py|md|csv|json|docx|zip|png|txt|srt|bat|xlsx?))`")
EXT_KNOWN = ("http", "github.com", "gitcode.com", "modelscope", "example.com")
SKIP_MARKERS = ("...", "…", "例：", "例:", "xxx", "XXX")
missing, checked = {}, 0
for f in files:
    try:
        text = open(os.path.join(HERE, f), encoding="utf-8", errors="replace").read()
    except OSError:
        continue
    base = os.path.dirname(os.path.join(HERE, f))
    for m in PAT.finditer(text):
        ref = m.group(1)
        if any(k in ref for k in EXT_KNOWN) or ref.startswith(("http", "/")):
            continue
        if any(k in ref for k in SKIP_MARKERS):
            continue
        checked += 1
        # 先按"引用文件所在目录"解析，再退回仓库根（修 2026-10-01 的相对路径误报）
        if os.path.exists(os.path.join(base, ref)) or os.path.exists(os.path.join(HERE, ref)):
            continue
        missing.setdefault(ref, []).append(f)
print(f"=== A. 断链检查：扫描 {len(files)} 份 .md，文件引用 {checked} 处 ===")
if missing:
    print(f"被引用但不存在（{len(missing)} 个）：")
    for ref, where in sorted(missing.items()):
        print(f"  [缺] {ref}\n        引用自：{', '.join(sorted(set(where))[:4])}")
else:
    print("  （无断链）")

# ---------- B. 依赖声明检查 ----------
STDLIB = set(sys.stdlib_module_names)
LOCAL = {os.path.splitext(f)[0] for f in os.listdir(HERE) if f.endswith(".py")}
LOCAL |= {"report_builder", "text_utils", "predict_core", "config"}
PRODUCT = ["report_builder.py", "soundinsight_agent.py", "demo_sound_v2.py",
           "api_server.py", "deployment/app.py", "deployment/report_builder.py"]
imports = {}
for rel in PRODUCT:
    p = os.path.join(HERE, rel)
    if not os.path.isfile(p):
        continue
    try:
        tree = ast.parse(open(p, encoding="utf-8", errors="replace").read())
    except SyntaxError as e:
        print(f"  [语法错误] {rel}: {e}")
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.setdefault(a.name.split(".")[0], set()).add(rel)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.setdefault(node.module.split(".")[0], set()).add(rel)

req_path = os.path.join(HERE, "requirements.txt")
req_names = set()
if os.path.isfile(req_path):
    for line in open(req_path, encoding="utf-8", errors="replace"):
        line = line.split("#")[0].strip()
        if line:
            req_names.add(re.split(r"[<>=!\[]", line)[0].strip().lower())

third = {k: v for k, v in imports.items()
         if k not in STDLIB and k not in LOCAL and not k.startswith("_")}
print(f"\n=== B. 依赖声明检查：产品模块第三方 import {len(third)} 个 ===")
undeclared = []
for mod, where in sorted(third.items()):
    norm = mod.lower().replace("_", "-")
    ok = norm in req_names or mod.lower() in req_names
    # 常见别名
    alias = {"sklearn": "scikit-learn", "pil": "pillow", "dotenv": "python-dotenv",
             "yaml": "pyyaml", "transformers": "transformers", "torch": "torch"}
    if not ok and alias.get(norm) in req_names:
        ok = True
    print(f"  {'OK  ' if ok else '缺  '} {mod:<16} ← {', '.join(sorted(where))}")
    if not ok:
        undeclared.append(mod)
print(f"\n[结论] 断链 {len(missing)} 个｜未声明的第三方依赖 {len(undeclared)} 个"
      f"{'：' + '、'.join(undeclared) if undeclared else ''}")
