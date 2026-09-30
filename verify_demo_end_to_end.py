# -*- coding: utf-8 -*-
"""端到端验证：从决赛包解包 → 在解出的 Demo 目录里实跑产品（模拟评委路径）。

步骤：
  1. 解包决赛包到工作区临时目录；
  2. 解包其中的 Demo.zip；
  3. 把真实权重**复制**进解出的 Demo（模拟 `download_models.py` 已完成）；
  4. 用**解出的那份代码**运行 `soundinsight_agent.py`（子进程，cwd=解出目录）；
  5. 校验：七节报告生成、非英文计数行存在、置信度三档表存在；
  6. 清理临时目录（自清理，避免被 git 扫入）。

本测试覆盖的是"包内代码 + 包内配置 + 真实权重"能否协同工作——
即评委实际会走的那条路。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, "_tmp_e2e")
TEAM, NAME = "更新世界的锋芒", "SoundInsight"
FINALS = f"{TEAM}_{NAME}_决赛入围定稿作品.zip"
DEMO = f"{TEAM}_{NAME}_Demo.zip"


def main() -> int:
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP, exist_ok=True)
    print("[1] 解包决赛包…")
    with zipfile.ZipFile(os.path.join(HERE, FINALS)) as z:
        z.extractall(TMP)
    demo_dir = os.path.join(TMP, "demo")
    print("[2] 解包 Demo.zip…")
    with zipfile.ZipFile(os.path.join(TMP, DEMO)) as z:
        z.extractall(demo_dir)

    print("[3] 复制真实权重（模拟已执行 download_models.py）…")
    for d in ("sound_model", "multi_label_model"):
        src = os.path.join(HERE, d)
        dst = os.path.join(demo_dir, d)
        if not os.path.isdir(src):
            print(f"    [跳过] 源目录不存在：{d}")
            continue
        os.makedirs(dst, exist_ok=True)
        for fn in os.listdir(src):
            shutil.copy2(os.path.join(src, fn), os.path.join(dst, fn))
        print(f"    {d}：{len(os.listdir(dst))} 个文件")

    print("[4] 用解出的代码运行 Agent…")
    csv_name = "sample_reviews_100.csv"
    p = subprocess.run([sys.executable, "soundinsight_agent.py", "--csv", csv_name],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=demo_dir)
    print(f"    退出码 {p.returncode}")
    if p.returncode != 0:
        print("    stderr 末行：" + (p.stderr.strip().splitlines()[-1][:200]
                                    if p.stderr.strip() else "（空）"))

    report = os.path.join(demo_dir, "insight_report_v2.md")
    print("[5] 校验报告…")
    ok = os.path.isfile(report)
    if ok:
        t = open(report, encoding="utf-8").read()
        secs = [l.strip() for l in t.splitlines() if l.startswith("## ")]
        checks = {
            "报告已生成": True,
            "七节齐备": len(secs) == 7,
            "含置信度档位节": any("置信度档位" in s for s in secs),
            "含非英文计数（显式跳过）": "非英文" in t,
            "含成本对照": "成本" in t,
        }
        for k, v in checks.items():
            print(f"    {'OK  ' if v else 'FAIL'} {k}")
        ok = all(checks.values())
    else:
        print("    FAIL 未生成报告文件")

    print("[6] 清理临时目录…")
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n[结论] 包内端到端 {'通过 ✓ 评委按 README 即可复现' if ok else '需检查'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
