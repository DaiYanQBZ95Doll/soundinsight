# -*- coding: utf-8 -*-
"""门槛链单入口：按**正确顺序**跑完全部检查与生成，最后给出总判定。

为什么需要：各步骤有**顺序依赖**（审计报告会被打包进决赛包；manifest 必须在所有文件改动之后生成，
否则"清单过期"不为 0；包内验证必须在打包之后）。手工按序执行容易漏步——本脚本把顺序固化。

顺序：
  1. `check_doc_numbers.py`        —— 数字审计（含 231 项检查）
  2. `test_audit_checks.py`        —— 审计负向自测（证明检查会拒绝坏输入）
  3. `check_refs_and_deps.py`      —— 断链 + 依赖声明（信息性，附在输出里）
  4. `check_url_consistency.py`    —— URL 一致性（M3c③）
  5. `v2_m0_switch_check.py`       —— 换代核对（待处理应为 0）
  6. `build_finals_package.py`     —— 构建决赛包（内含红线 9 双向核对）
  7. `update_finals_hashes.py`     —— 登记决赛包哈希
  8. `verify_finals_package.py`    —— 包内校验 + Demo 冒烟
  9. `make_ai_handoff.py`          —— 刷新 AI 交接包（manifest）
 10. `scan_repo_hygiene.py`        —— 仓库卫生（密钥/隐私/废弃 claim/清单过期）

用法：python run_all_checks.py [--skip-package]
退出码：0 = 全绿；非 0 = 有步骤失败（并打印失败步骤名）。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

STEPS_FULL = [
    ("数字审计（231 项检查）", ["check_doc_numbers.py"]),
    ("审计负向自测", ["test_audit_checks.py"]),
    ("断链 + 依赖声明", ["check_refs_and_deps.py"]),
    ("URL 一致性（M3c③）", ["check_url_consistency.py"]),
    ("换代核对（M0）", ["v2_m0_switch_check.py"]),
    ("构建决赛包（含红线 9 核对）", ["build_finals_package.py"]),
    ("登记决赛包哈希", ["update_finals_hashes.py"]),
    ("包内校验 + Demo 冒烟", ["verify_finals_package.py"]),
    ("刷新 AI 交接包 manifest", ["make_ai_handoff.py"]),
    ("仓库卫生扫描", ["scan_repo_hygiene.py"]),
]
STEPS_NO_PKG = [(n, c) for n, c in STEPS_FULL
                if n not in ("构建决赛包（含红线 9 核对）", "登记决赛包哈希",
                             "包内校验 + Demo 冒烟")]
# 这些步骤的退出码非 0 不视为失败（其输出为"信息性"，如断链检查会列出合理的历史引用）
NON_FATAL = {"断链 + 依赖声明"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-package", action="store_true",
                    help="跳过打包三步（仅做检查时用）")
    args = ap.parse_args()
    steps = STEPS_NO_PKG if args.skip_package else STEPS_FULL

    results = []
    t0 = time.time()
    for name, cmd in steps:
        t = time.time()
        p = subprocess.run([sys.executable, *cmd], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=HERE)
        ok = p.returncode == 0
        tail = (p.stdout or "").strip().splitlines()
        brief = next((l for l in reversed(tail)
                      if "FAIL" in l or "PASS" in l or "通过" in l or "密钥" in l
                      or "待处理" in l), (tail[-1] if tail else ""))
        results.append((name, ok, round(time.time() - t, 1), brief[:110]))
        flag = "OK  " if ok else ("WARN" if name in NON_FATAL else "FAIL")
        print(f"[{flag}] {name:<32} {results[-1][2]:>6.1f}s  {results[-1][3]}")
        if not ok and name not in NON_FATAL:
            print(f"        → 步骤失败，命令：python {' '.join(cmd)}")
            if p.stderr:
                print(f"        stderr: {p.stderr.strip().splitlines()[-1][:160]}")

    failed = [n for n, ok, _, _ in results if not ok and n not in NON_FATAL]
    print(f"\n=== 门槛链{'（跳过打包）' if args.skip_package else ''} ==="
          f"总用时 {time.time()-t0:.0f}s")
    print(f"步骤 {len(results)} 个｜失败 {len(failed)} 个"
          + (f"：{'、'.join(failed)}" if failed else "（全绿）"))
    if failed:
        return 1
    print("提示：审计报告头部的「运行时刻」用于判断读数新鲜度；本脚本已确认每步退出码。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
