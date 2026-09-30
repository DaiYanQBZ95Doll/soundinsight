# -*- coding: utf-8 -*-
"""把决赛包的哈希登记进 hashes.txt（保留复赛包冻结段不动）。

用法：python update_finals_hashes.py
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TEAM, NAME = "更新世界的锋芒", "SoundInsight"
FINALS = f"{TEAM}_{NAME}_决赛入围定稿作品.zip"
ENTRIES = [f"{TEAM}_{NAME}_决赛入围定稿作品.docx",
           f"{TEAM}_{NAME}_Demo.zip",
           f"{TEAM}_{NAME}_演示视频.mp4",
           f"{TEAM}_{NAME}_其他材料.zip"]
MARK = "# ===== 决赛包（v2 口径）====="


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    lines = open(os.path.join(HERE, "hashes.txt"), encoding="utf-8",
                 errors="replace").read().splitlines()
    # 去掉旧的决赛段（若有）
    out, skip = [], False
    for ln in lines:
        if ln.startswith(MARK):
            skip = True
            continue
        if skip and ln.startswith("# ===== "):
            skip = False
        if not skip:
            out.append(ln)
    block = ["", MARK,
             "# 决赛包（v2 口径）及其内部四件提交物在打包时刻的校验值；完整 SHA256。",
             "# 复赛包（上方一段）为已提交冻结物，两者互不影响。"]
    fp = os.path.join(HERE, FINALS)
    if os.path.isfile(fp):
        block.append(f"{os.path.getsize(fp):>12,} B  sha256:{sha(fp)}  {FINALS}")
    else:
        block.append(f"# （{FINALS} 尚未生成）")
    for name in ENTRIES:
        p = os.path.join(HERE, name)
        # 视频入包版本为 faststart 重排版（moov 前置）；哈希须按**实际入包内容**登记
        if name.endswith("演示视频.mp4"):
            fs = os.path.join(HERE, name.replace(".mp4", "_faststart.mp4"))
            if os.path.isfile(fs):
                p = fs
                block.append(f"# 视频入包版本为 faststart 重排版（数据逐块验证零改动，见 verify_faststart.py）")
        if os.path.isfile(p):
            block.append(f"{os.path.getsize(p):>12,} B  sha256:{sha(p)}  {name}")
    out += block
    open(os.path.join(HERE, "hashes.txt"), "w", encoding="utf-8",
         newline="\n").write("\n".join(out) + "\n")
    print(f"[写出] hashes.txt（{len(block)} 行决赛段）")
    for ln in block[3:]:
        print("   " + ln[:110])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
