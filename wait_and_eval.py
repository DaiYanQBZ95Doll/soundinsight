# -*- coding: utf-8 -*-
"""编排：等 v5 与类型模型落盘 → 自动评测 → 汇总（可后台运行）。

用法：python wait_and_eval.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))


def wait_for(path, label, timeout_min=180):
    t0 = time.time()
    while time.time() - t0 < timeout_min * 60:
        if os.path.isfile(os.path.join(path, "config.json")):
            print(f"[就绪] {label}（等待 {int(time.time()-t0)} 秒）", flush=True)
            return True
        time.sleep(20)
    print(f"[超时] {label} 未在 {timeout_min} 分钟内落盘", flush=True)
    return False


def run(script):
    r = subprocess.run([sys.executable, script], cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = ((r.stdout or "") + (r.stderr or "").strip())
    print(f"--- {script} ---\n{out[-1200:]}", flush=True)
    return r.returncode


summary = {}
if wait_for(os.path.join(HERE, "v2", "model_v5_sound"), "v5 音质模型"):
    run("eval_v5.py")
    p = os.path.join(HERE, "v2", "v5_eval.json")
    if os.path.isfile(p):
        summary["v5"] = json.load(open(p, encoding="utf-8"))

if wait_for(os.path.join(HERE, "v2", "model_types"), "类型/原因模型"):
    # 冒烟：用 3 条样例验证可用性
    smoke = subprocess.run([sys.executable, "-c",
                            "import types_helper as t;"
                            "print(t.available());"
                            "print(t.predict(['The bass is muddy and the battery dies fast.',"
                            "'Pairing failed and the manual is unclear.']))"],
                           cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
    print("--- types 冒烟 ---\n" + ((smoke.stdout or "") + (smoke.stderr or ""))[-500:],
          flush=True)
    summary["types_available"] = "True" in (smoke.stdout or "")

json.dump(summary, open(os.path.join(HERE, "v2", "pipeline_summary.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
print("[完成] 自动化流水线结束")
