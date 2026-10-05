# -*- coding: utf-8 -*-
"""核验远端权重就是 v2：读 ModelScope 仓库里 LFS 指针文件的 oid sha256，与本地登记对比。

（LFS 指针只有百来字节，却能给出**远端真实内容**的 sha256——无需下载 256MB。）
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "DaiYanQBZ95Doll/SoundInsight_models"
URL = f"https://modelscope.cn/api/v1/models/{REPO}/repo?FilePath=sound_model/model.safetensors"
local = json.load(open(os.path.join(HERE, "model_hashes.json"), encoding="utf-8"))
want = local["sound_model/model.safetensors"]
print(f"本地登记（出厂 v2）：{want[:16]}…")
try:
    req = urllib.request.Request(URL, headers={"User-Agent": "SoundInsight-verify"})
    with urllib.request.urlopen(req, timeout=120) as r:
        head = r.read(400)
except Exception as e:  # noqa: BLE001
    print(f"  [取指针失败] {type(e).__name__}: {e}")
    sys.exit(1)
text = head.decode("utf-8", "replace")
m = re.search(r"oid sha256:([0-9a-f]{64})", text)
if m:
    remote = m.group(1)
    print(f"远端 LFS oid：    {remote[:16]}…")
    print(f"  ⇒ 远端内容与出厂 v2 **{'一致 ✓' if remote == want else '不一致 ✗'}**")
    sys.exit(0 if remote == want else 1)
print("  响应不是 LFS 指针（可能被重定向到实际文件流）：")
print("  前 120 字节：", text[:120].replace("\n", " "))
