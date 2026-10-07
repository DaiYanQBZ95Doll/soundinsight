# -*- coding: utf-8 -*-
"""提交存档：记录**上传时那一刻**交付文件的哈希，并把决赛包按哈希归档（防重建后无法对账）。

判据：与 docs/SUBMISSION_READINESS.md 中记录的哈希逐位比对；不一致则明确报警
（说明上传的不是清单所指的那一份）。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = "更新世界的锋芒_SoundInsight_决赛入围定稿作品.zip"
FILES = [PKG, "更新世界的锋芒_SoundInsight_演示视频.mp4",
         "更新世界的锋芒_SoundInsight_其他材料.zip",
         "更新世界的锋芒_SoundInsight_Demo.zip",
         "更新世界的锋芒_SoundInsight_决赛入围定稿作品.docx"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def content_hash(p):
    try:
        zf = zipfile.ZipFile(p)
    except zipfile.BadZipFile:
        return None
    parts = [f"{n}:{hashlib.sha256(zf.read(n)).hexdigest()}"
             for n in sorted(n for n in zf.namelist() if not n.endswith("/"))]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest(), len(parts)


# 读清单里记录的哈希（用于比对）
doc = os.path.join(HERE, "docs", "SUBMISSION_READINESS.md")
claimed = {}
if os.path.isfile(doc):
    for ln in open(doc, encoding="utf-8"):
        _rows = [ln for ln in open(doc, encoding="utf-8") if "（容器）" in ln]
        for f, ln in zip(FILES, _rows):          # 按表格行顺序匹配（文件名含反引号，完整可比）
            m = re.search(r"\|\s*([0-9a-f]{16})…（容器）", ln)
            if m:
                claimed[f] = m.group(1)

rows = []
mismatch = []
for f in FILES:
    p = os.path.join(HERE, f)
    if not os.path.isfile(p):
        rows.append({"file": f, "missing": True})
        continue
    ch = content_hash(p)
    rec = {"file": f, "bytes": os.path.getsize(p), "sha256": sha(p),
           "content_sha256": ch[0] if ch else None, "members": ch[1] if ch else None}
    if f in claimed and not rec["sha256"].startswith(claimed[f]):
        mismatch.append({"file": f, "claimed": claimed[f], "actual": rec["sha256"][:16]})
    rows.append(rec)

# 归档上传时的决赛包（按哈希命名；目录不进仓库）
arc = os.path.join(HERE, "_submitted")
os.makedirs(arc, exist_ok=True)
src = os.path.join(HERE, PKG)
if os.path.isfile(src) and not mismatch:
    dst = os.path.join(arc, f"submitted_{sha(src)[:16]}_{PKG}")
    if not os.path.isfile(dst):
        shutil.copy2(src, dst)
    print(f"  [归档] {os.path.relpath(dst, HERE)}")

out = {"recorded_at": datetime.datetime.now().isoformat(timespec="seconds"),
       "interpreter": sys.executable, "files": rows, "mismatch_vs_readiness": mismatch}
json.dump(out, open(os.path.join(HERE, "v2", "submission_archive.json"), "w",
                    encoding="utf-8"), ensure_ascii=False, indent=2)
print("  哈希记录：")
for r in rows:
    if r.get("missing"):
        print(f"    {r['file'][:34]}：缺失")
    else:
        print(f"    {r['file'][:34]}：{r['bytes']/1e6:.2f} MB｜{r['sha256'][:16]}…"
              + (f"｜内容级 {r['content_sha256'][:16]}…" if r.get("content_sha256") else ""))
if mismatch:
    print(f"  ⚠ 与核对清单不一致 {len(mismatch)} 项：{mismatch}")
else:
    print("  ✓ 与核对清单逐位一致")
print("[写出] v2/submission_archive.json")
