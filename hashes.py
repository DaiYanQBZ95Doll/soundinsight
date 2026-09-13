# -*- coding: utf-8 -*-
# hashes.py —— 打印提交物大小与 SHA256（前 16 位），用于封包声明与提交前核对
import hashlib
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = [
    "更新世界的锋芒_SoundInsight_复赛作品.zip",
    "更新世界的锋芒_SoundInsight_复赛作品.pdf",
    "更新世界的锋芒_SoundInsight_复赛作品.docx",
    "更新世界的锋芒_SoundInsight_Demo.zip",
    "更新世界的锋芒_SoundInsight_其他材料.zip",
    "competition_v4.md",
    "competition_v3.txt",
    "video_script.md",
    "SoundInsight：跨境电商耳机音质差评智能归因系统.pptx",
]

for f in FILES:
    p = os.path.join(HERE, f)
    if os.path.isfile(p):
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
        print(f"{os.path.getsize(p):>10,} B  sha256:{h}  {f}")
    else:
        print(f"{'缺失':>10}      {'-' * 16}  {f}")
