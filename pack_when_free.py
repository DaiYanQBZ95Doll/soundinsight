# -*- coding: utf-8 -*-
# pack_when_free.py —— 等提交包不再被占用（Bandizip 等）后自动重打内层与外层包
#
# 背景：用户用 Bandizip 打开了 复赛作品.zip，Windows 下该文件被独占，
# pack_final.py 无法替换它。本脚本轮询等待，一空闲就重打并复核。
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ZIP = os.path.join(HERE, "更新世界的锋芒_SoundInsight_复赛作品.zip")


def writable() -> bool:
    try:
        with open(ZIP, "a+b"):
            return True
    except PermissionError:
        return False
    except OSError:
        return False


deadline = time.time() + 45 * 60
print("等待 复赛作品.zip 释放（Bandizip 关闭后自动继续）...", flush=True)
while time.time() < deadline:
    if writable():
        break
    time.sleep(5)
else:
    print("TIMEOUT：45 分钟内文件一直被占用，未重打。", flush=True)
    sys.exit(2)
print("文件已释放，开始重打。", flush=True)

for script in ("build_submission.py", "pack_final.py"):
    print(f"\n===== {script} =====", flush=True)
    p = subprocess.run([sys.executable, script], cwd=HERE,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = (p.stdout or "").strip().splitlines()[-12:]
    print("\n".join(tail), flush=True)
    if p.returncode != 0:
        print(f"[FAIL] {script} 退出码 {p.returncode}", flush=True)
        print((p.stderr or "")[-800:], flush=True)
        sys.exit(1)

print("\n===== hashes =====", flush=True)
p = subprocess.run([sys.executable, "hashes.py"], cwd=HERE,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print(p.stdout, flush=True)
print("完成：内层与外层包已按当前文档重打。", flush=True)
