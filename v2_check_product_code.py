# -*- coding: utf-8 -*-
"""内存编译校验产品代码 + 重跑报告六节冒烟（不写 .pyc，兼容沙箱）。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PRODUCT = ["report_builder.py", "deployment/report_builder.py", "soundinsight_agent.py",
           "demo_sound_v2.py", "api_server.py", "text_utils.py", "predict_utils.py"]

print("=== 1) 语法编译（内存，不落盘）===")
bad = 0
for rel in PRODUCT:
    p = os.path.join(HERE, rel)
    if not os.path.isfile(p):
        print(f"  [缺] {rel}")
        continue
    src = open(p, encoding="utf-8", errors="replace").read()
    try:
        compile(src, rel, "exec")
        print(f"  [OK] {rel}")
    except SyntaxError as e:
        bad += 1
        print(f"  [FAIL] {rel}: {e}")

print("\n=== 2) 代码内残留 [v1]/[v2] 直贴数字检查（产品模块）===")
import re
pat = re.compile(r"\d\[v[12]\]")
for rel in PRODUCT:
    p = os.path.join(HERE, rel)
    if not os.path.isfile(p):
        continue
    for i, line in enumerate(open(p, encoding="utf-8", errors="replace").read().splitlines(), 1):
        if pat.search(line):
            bad += 1
            print(f"  [FAIL] {rel}:{i} {line.strip()[:90]}")

print("\n=== 3) 报告生成冒烟（六节 + 三档表）===")
sys.path.insert(0, HERE)
import report_builder as rb  # noqa: E402
t = rb.build_report(src_name="冒烟", n_total=10, n_unsupported=0, n_valid=10, n_neg=2,
                    avg_rating=3.5, issue_counts={"杂音": 2, "清晰度": 1},
                    examples=[{"text": "bass rattle", "issue": "杂音", "prob": 0.98}],
                    n_mid=1, lang="zh")
sections = [l for l in t.splitlines() if l.startswith("## ")]
print("  节：", "、".join(s.replace("## ", "") for s in sections))
ok = len(sections) == 7 and "置信度档位" in t and "0.9744[" not in t
print(f"  {'OK  ' if ok else 'FAIL'} 七节齐备且无代码内标签残留")
print(f"\n[结论] {'全部通过' if (bad == 0 and ok) else '存在失败项'}")
raise SystemExit(0 if (bad == 0 and ok) else 1)
