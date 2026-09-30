# -*- coding: utf-8 -*-
"""MP4 faststart 重排（纯 Python，等价于 qt-faststart，无需 ffmpeg）。

动机（M2a 的硬性要求）：当前成片 `moov` 在 `mdat` 之后，网页/流式播放会先卡顿。

做法：
  1. 解析顶层 box（size 支持 32 位与 64 位 `largesize`）；
  2. 取出 `moov`，把它移到 `mdat` 之前；
  3. 修正 `moov` 内所有 `stco`（32 位）与 `co64`（64 位）中的 chunk offset：加上位移 delta；
  4. 输出新文件；**原文件不改**。

校验（全部通过才保留输出）：
  · 新文件总大小与顶层 box 覆盖范围一致（无缝隙/无重叠）；
  · `moov` 出现在 `mdat` 之前；
  · 所有 stco/co64 偏移落在新 `mdat` 报文范围内且单调不减；
  · 采样表条目数（stco/co64 计数）与原文件一致。

用法：python make_faststart.py <输入.mp4> [输出.mp4]
"""
from __future__ import annotations

import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts", b"dinf", b"udta"}


def parse_boxes(buf: bytes, start: int, end: int):
    """返回 [(type, box_start, header_size, size)]。"""
    boxes = []
    i = start
    while i + 8 <= end:
        size = struct.unpack(">I", buf[i:i + 4])[0]
        btype = buf[i + 4:i + 8]
        hdr = 8
        if size == 1:
            size = struct.unpack(">Q", buf[i + 8:i + 16])[0]
            hdr = 16
        elif size == 0:
            size = end - i
        if size < hdr or i + size > end:
            break
        boxes.append((btype, i, hdr, size))
        i += size
    return boxes


def find_all(buf: bytes, btype: bytes, start: int = 0, end: int | None = None):
    """递归查找指定 box 的 (start, header_size, size)。"""
    end = len(buf) if end is None else end
    out = []
    for t, s, hdr, size in parse_boxes(buf, start, end):
        if t == btype:
            out.append((s, hdr, size))
        if t in CONTAINERS:
            out += find_all(buf, btype, s + hdr, s + size)
    return out


def collect_offsets(buf: bytes, moov_start: int, moov_size: int):
    """收集 moov 内 stco/co64 的表项 (box_start, header, entries_offset, count, width)。"""
    tables = []
    for t in (b"stco", b"co64"):
        for s, hdr, size in find_all(buf, t, moov_start, moov_start + moov_size):
            version_flags = buf[s + hdr:s + hdr + 4]
            count = struct.unpack(">I", buf[s + hdr + 4:s + hdr + 8])[0]
            width = 4 if t == b"stco" else 8
            tables.append((t, s, hdr, count, width))
    return tables


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else "更新世界的锋芒_SoundInsight_演示视频.mp4"
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + "_faststart.mp4"
    buf = open(src, "rb").read()
    total = len(buf)
    top = parse_boxes(buf, 0, total)
    print(f"[原文件] {os.path.basename(src)}：{total:,} B，顶层 box "
          f"{[(t.decode('latin1'), sz) for t, _, _, sz in top]}")
    covered = sum(sz for _, _, _, sz in top)
    if covered != total:
        print(f"[中止] 顶层 box 覆盖 {covered:,} B ≠ 文件大小 {total:,} B（结构不完整）")
        return 1

    moov = [b for b in top if b[0] == b"moov"]
    mdat = [b for b in top if b[0] == b"mdat"]
    if len(moov) != 1 or not mdat:
        print("[中止] 顶层 box 形态不符合预期（需恰好 1 个 moov 与 ≥1 个 mdat）")
        return 1
    moov_start, moov_hdr, moov_size = moov[0][1], moov[0][2], moov[0][3]
    if moov_start < mdat[0][1]:
        print("[跳过] moov 已在 mdat 之前（已是 faststart），无需处理")
        return 0

    tables = collect_offsets(buf, moov_start, moov_size)
    if not tables:
        print("[中止] moov 内未找到 stco/co64 表")
        return 1
    print(f"[采样表] {len(tables)} 个：" +
          "、".join(f"{t.decode()}(count={c}, {w}B)" for t, _, _, c, w in tables))

    first_mdat_end = mdat[0][1] + mdat[0][3]
    others = [b for b in top if b not in moov]
    # 目标布局：moov 之前的**非 mdat** box（ftyp/free 等）→ moov → 其余（mdat 及 moov 之后者）
    pre = [b for b in others if b[1] < moov_start and b[0] != b"mdat"]
    post = [b for b in others if b not in pre]
    new_moov_start = sum(sz for _, _, _, sz in pre)
    # 块偏移指向 mdat 内部，因此修正量＝**mdat 的位移**（不是 moov 的位移）
    old_mdat_start = mdat[0][1]
    new_mdat_start = new_moov_start + moov_size
    delta = new_mdat_start - old_mdat_start
    print(f"[重排] 布局 {[t.decode('latin1') for t, _, _, _ in pre]} → moov → "
          f"{[t.decode('latin1') for t, _, _, _ in post]}")
    print(f"[重排] moov {moov_start:,} → {new_moov_start:,}；"
          f"mdat {old_mdat_start:,} → {new_mdat_start:,}；块偏移 delta = {delta:+,}")

    moov_bytes = bytearray(buf[moov_start:moov_start + moov_size])
    for t, s, hdr, count, width in tables:
        base = (s - moov_start) + hdr + 8         # 表项在 moov 内的偏移
        for k in range(count):
            off = base + k * width
            if width == 4:
                v = struct.unpack(">I", moov_bytes[off:off + 4])[0]
                moov_bytes[off:off + 4] = struct.pack(">I", v + delta)
            else:
                v = struct.unpack(">Q", moov_bytes[off:off + 8])[0]
                moov_bytes[off:off + 8] = struct.pack(">Q", v + delta)

    out = bytearray()
    for _, s, _, sz in pre:
        out += buf[s:s + sz]
    out += moov_bytes
    for _, s, _, sz in post:
        out += buf[s:s + sz]

    # ---------- 校验 ----------
    nb = bytes(out)
    checks = []
    checks.append(("总大小不变", len(nb) == total, f"{len(nb):,} vs {total:,}"))
    ntop = parse_boxes(nb, 0, len(nb))
    checks.append(("顶层 box 覆盖完整", sum(sz for _, _, _, sz in ntop) == len(nb),
                   f"{sum(sz for _, _, _, sz in ntop):,} vs {len(nb):,}"))
    nmoov = [b for b in ntop if b[0] == b"moov"]
    nmdat = [b for b in ntop if b[0] == b"mdat"]
    checks.append(("moov 在 mdat 之前", bool(nmoov and nmdat and nmoov[0][1] < nmdat[0][1]),
                   f"moov@{nmoov[0][1]:,} mdat@{nmdat[0][1]:,}" if nmoov and nmdat else "—"))
    ntab = collect_offsets(nb, nmoov[0][1], nmoov[0][3]) if nmoov else []
    checks.append(("采样表数量一致", len(ntab) == len(tables), f"{len(ntab)} vs {len(tables)}"))
    oks, inrange, mono = True, True, True
    lo, hi = nmdat[0][1], nmdat[0][1] + nmdat[0][3] if nmdat else (0, 0)
    for (t, s, hdr, count, width), (t2, s2, hdr2, c2, w2) in zip(tables, ntab):
        if count != c2:
            oks = False
        prev = None
        for k in range(c2):
            off = s2 + hdr2 + 8 + k * w2
            v = struct.unpack(">I" if w2 == 4 else ">Q", nb[off:off + w2])[0]
            if not (lo <= v < hi):
                inrange = False
            if prev is not None and v < prev:
                mono = False
            prev = v
    checks.append(("表项计数一致", oks, ""))
    checks.append(("偏移落在 mdat 内", inrange, f"mdat 范围 [{lo:,}, {hi:,})"))
    checks.append(("块偏移单调不减", mono, ""))
    print("\n[校验]")
    allok = True
    for name, ok, extra in checks:
        print(f"  {'OK  ' if ok else 'FAIL'} {name}" + (f"（{extra}）" if extra else ""))
        allok &= ok
    if not allok:
        print("\n[中止] 校验未通过 → 不写出新文件，保留原文件")
        return 1
    open(dst, "wb").write(nb)
    print(f"\n[写出] {os.path.basename(dst)}（{os.path.getsize(dst):,} B）"
          f"——原文件未改动：{os.path.basename(src)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
