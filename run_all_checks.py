# -*- coding: utf-8 -*-
"""门槛链单入口：按**正确顺序**跑完全部检查与生成，最后给出总判定。

为什么需要：各步骤有**顺序依赖**（审计报告会被打包进决赛包；manifest 必须在所有文件改动之后生成，
否则"清单过期"不为 0；包内验证必须在打包之后）。手工按序执行容易漏步——本脚本把顺序固化。

顺序：见文件末尾的 `STEPS_FULL`——**它是步骤清单的唯一权威源**，本 docstring 不再重复列举
（此前列举 10 步、实际已 19 步，属 R13「声明与实现不符」；红队 Qwen 指出后改为引用）。

用法：python run_all_checks.py [--skip-package] [--list]
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
    ("数字审计（项数见报告头部）", ["check_doc_numbers.py"]),
    ("审计负向自测", ["test_audit_checks.py"]),
    ("断链 + 依赖声明", ["check_refs_and_deps.py"]),
    ("URL 一致性（M3c③）", ["check_url_consistency.py"]),
    ("换代核对（M0）", ["v2_m0_switch_check.py"]),
    ("材料生成器与 docx 构建（本次事故机制化）", ["check_docx_build.py"]),
    ("构建决赛包（含红线 9 核对）", ["build_finals_package.py"]),
    ("登记决赛包哈希", ["update_finals_hashes.py"]),
    ("包内校验 + Demo 冒烟", ["verify_finals_package.py"]),
    ("包内端到端（解包后实跑产品）", ["verify_demo_end_to_end.py"]),
    ("产品入口（Gradio UI + HTTP API）", ["verify_ui_and_api.py"]),
    ("在线 Demo 存活巡检（M3c④）", ["check_demo_alive.py"]),
    ("刷新对外状态卡（REVIEWER_BRIEF）", ["make_reviewer_brief.py"]),
    ("刷新停工快照（生成式）", ["make_pause_snapshot.py"]),
    ("PPT 导出与口径核对（含勘误指针）", ["audit_ppt.py"]),
    ("包外依赖检查（P9：配置/权重可达/包内结构）", ["check_external_deps.py"]),
    ("推送状态（每日一次 + 当日必推判定）", ["push_daily.py", "--status"]),
    ("推送机制自测（当日必推规则）", ["push_daily.py", "--self-test"]),
    ("刷新三方总线总览（INDEX）", ["make_bus_index.py"]),
    ("禁报数字机械门（R5 扩展）", ["check_retracted_numbers.py"]),
    ("对外称谓一致性（正文 vs 附录）", ["check_scope_wording.py"]),
    ("判定解析单点实现（R32 机制化）", ["check_single_parser.py"]),
    ("共享解析模块自测", ["rulings_io.py", "--self-test"]),
    ("刷新 AI 交接包 manifest", ["make_ai_handoff.py"]),
    ("仓库卫生扫描", ["scan_repo_hygiene.py"]),
]
STEPS_NO_PKG = [(n, c) for n, c in STEPS_FULL
                if n not in ("构建决赛包（含红线 9 核对）", "登记决赛包哈希",
                             "包内校验 + Demo 冒烟", "包内端到端（解包后实跑产品）")]
# 这些步骤的退出码非 0 不视为失败（其输出为"信息性"，如断链检查会列出合理的历史引用）
NON_FATAL = {"断链 + 依赖声明", "在线 Demo 存活巡检（M3c④）"}


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
        # 双保险：审计步骤额外核对报告内 FAIL 计数（防"退出码恒 0"类回归）
        if ok and cmd and cmd[0] == "check_doc_numbers.py":
            rep = os.path.join(HERE, "number_audit.md")
            if os.path.isfile(rep):
                with open(rep, encoding="utf-8", errors="replace") as fh:
                    n_fail = fh.read().count("[FAIL]")
                if n_fail:
                    ok = False
                    print(f"        → 报告内 FAIL {n_fail} 条（虽退出码为 0）")
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
    _write_machine_result(len(results), failed)
    print(f"\n=== 门槛链{'（跳过打包）' if args.skip_package else ''} ==="
          f"总用时 {time.time()-t0:.0f}s")
    print(f"步骤 {len(results)} 个｜失败 {len(failed)} 个"
          + (f"：{'、'.join(failed)}" if failed else "（全绿）"))
    if failed:
        return 1
    print("提示：审计报告头部的「运行时刻」用于判断读数新鲜度；本脚本已确认每步退出码。")
    return 0



def _write_machine_result(steps, failed):
    """写出机器可读结果，供 safe_commit --require-green-chain 使用。"""
    import datetime
    import json as _json
    import os as _os
    import subprocess as _sp
    try:
        head = _sp.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                       text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        head = ""
    _json.dump({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "steps": steps, "failed": failed, "head": head},
               open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                  "v2", "checks_result.json"), "w", encoding="utf-8"),
               ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
