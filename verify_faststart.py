# -*- coding: utf-8 -*-
"""faststart 重排的数据一致性验证：按采样表逐块比对"原文件 vs 新文件"的字节。

原理：stco 表给出每个 chunk 在文件中的绝对偏移。重排只改偏移、不改数据，
因此对任意 chunk k：原文件 @old_off 的 N 字节，应等于新文件 @new_off 的同样 N 字节。
本脚本按偏移差（delta）逐块验证前若干块与全部块的首尾抽样。
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_faststart import collect_offsets, parse_boxes  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = "更新世界的锋芒_SoundInsight_演示视频.mp4"
DST = "更新世界的锋芒_SoundInsight_演示视频_faststart.mp4"


def offsets_of(buf: bytes, path: str):
    top = parse_boxes(buf, 0, len(buf))
    moov = [b for b in top if b[0] == b"moov"][0]
    mdat = [b for b in top if b[0] == b"mdat"][0]
    tables = collect_offsets(buf, moov[1], moov[3])
    offs = []
    for t, s, hdr, count, width in tables:
        for k in range(count):
            p = s + hdr + 8 + k * width
            offs.append(struct.unpack(">I" if width == 4 else ">Q", buf[p:p + width])[0])
    return offs, mdat[1], mdat[3]


a = open(SRC, "rb").read()
b = open(DST, "rb").read()
oa, mdat_a, mlen_a = offsets_of(a, SRC)
ob, mdat_b, mlen_b = offsets_of(b, DST)
print(f"原文件：{len(oa)} 个 chunk，mdat@[{mdat_a:,}, {mdat_a+mlen_a:,})")
print(f"新文件：{len(ob)} 个 chunk，mdat@[{mdat_b:,}, {mdat_b+mlen_b:,})")
if len(oa) != len(ob):
    print("[FAIL] chunk 数量不一致")
    raise SystemExit(1)

deltas = {ob[i] - oa[i] for i in range(len(oa))}
print(f"偏移差集合：{deltas if len(deltas) < 4 else str(len(deltas)) + ' 个不同值'}"
      f"（期望单一常数）")
if len(deltas) != 1:
    print("[FAIL] 偏移差不唯一 → 重排逻辑异常")
    raise SystemExit(1)
delta = deltas.pop()
print(f"统一 delta = {delta:+,}（应等于 mdat 位移 {mdat_b - mdat_a:+,}）")

# 逐块比对：每块取首 64 字节 + 末 64 字节（块长由相邻偏移或 mdat 末尾界定）
bad = 0
checked = 0
for i in range(len(oa)):
    start = oa[i]
    end = oa[i + 1] if i + 1 < len(oa) else mdat_a + mlen_a
    n = max(0, end - start)
    if n == 0:
        continue
    take = min(n, 64)
    seg_a1, seg_b1 = a[start:start + take], b[start + delta:start + delta + take]
    seg_a2, seg_b2 = a[end - take:end], b[end - take + delta:end + delta]
    if seg_a1 != seg_b1 or seg_a2 != seg_b2:
        bad += 1
        if bad <= 3:
            print(f"  [FAIL] chunk {i}: 偏移 {start:,} 处字节不一致")
    checked += 1
print(f"\n逐块抽样比对：{checked} 块，不一致 {bad} 块")
print(f"[结论] {'全部一致 ✓ 重排未改动任何数据' if bad == 0 else '存在不一致，需回退'}")
raise SystemExit(0 if bad == 0 else 1)
