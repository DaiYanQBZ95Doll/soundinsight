# -*- coding: utf-8 -*-
# retime_srt.py —— 按"你实际剪出来的镜头时间"重排字幕
#
# 两种填法，任选其一：
#   ① 填 9 段【时长】（秒，累加即成时间轴）——剪映里每段长度最好读：
#      python retime_srt.py "22, 10, 45, 20, 25, 12, 20, 15, 36"
#   ② 填 9 个【起止窗口】：
#      python retime_srt.py "0-22, 22-32, 32-1:17, ..."
#
# 逻辑：按原字幕（video_script.srt）里各镜头归属的字幕分组，
# 在新窗口内均匀分配，保持"字幕与画面同一镜头"的对应关系。
# 运行后自动备份原字幕为 video_script.srt.bak
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRT = "video_script.srt"
OLD_WINDOWS = [(0, 20), (20, 28), (28, 68), (68, 88), (88, 113),
               (113, 148), (148, 168), (168, 183), (183, 193)]


def parse_time(t: str) -> float:
    parts = [float(x) for x in t.strip().split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]


def fmt(sec: float) -> str:
    sec = max(0.0, sec)
    ms = int(round((sec - int(sec)) * 1000))
    s = int(sec)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d},{ms:03d}"


def load_blocks():
    text = open(SRT, encoding="utf-8").read()
    out = []
    for blk in text.strip().split("\n\n"):
        L = blk.splitlines()
        if len(L) < 3:
            continue
        m = re.match(r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)",
                     L[1])
        out.append({"start": parse_time(m.group(1).replace(",", ".")),
                    "text": "\n".join(L[2:])})
    return out


def parse_arg(raw: str):
    """返回窗口列表：既支持 a-b 窗口，也支持纯时长（累加）。"""
    segs = [s.strip() for s in raw.split(",") if s.strip()]
    if all("-" in s for s in segs):                     # 窗口写法
        out = []
        for s in segs:
            a, b = s.split("-")
            out.append((parse_time(a), parse_time(b)))
        return out
    if all("-" not in s for s in segs):                 # 时长写法（累加）
        out, t = [], 0.0
        for s in segs:
            d = parse_time(s)
            out.append((t, t + d))
            t += d
        return out
    raise ValueError("请统一用 a-b 窗口 或 纯时长，不要混用")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("本片脚本的镜头时长（当前版本）：")
        for i, (a, b) in enumerate(OLD_WINDOWS, 1):
            print(f"  镜头{i}: {b - a:>4.0f} 秒"
                  f"（{fmt(a)[3:8]} - {fmt(b)[3:8]}）")
        print(f"  合计: {OLD_WINDOWS[-1][1] - OLD_WINDOWS[0][0]:.0f} 秒")
        return 1
    try:
        windows = parse_arg(sys.argv[1])
    except ValueError as e:
        print(f"参数解析失败：{e}")
        return 1
    if len(windows) != len(OLD_WINDOWS):
        print(f"需要 {len(OLD_WINDOWS)} 段，收到 {len(windows)} 段")
        return 1

    blocks = load_blocks()
    groups = {i: [] for i in range(len(OLD_WINDOWS))}
    for b in blocks:
        for i, (a, c) in enumerate(OLD_WINDOWS):
            if a <= b["start"] < c or (i == len(OLD_WINDOWS) - 1):
                groups[i].append(b)
                break

    shutil.copy2(SRT, SRT + ".bak")
    out, idx = [], 0
    for i, (na, nb) in enumerate(windows):
        items = groups[i]
        if not items:
            continue
        span = (nb - na) / len(items)
        for j, b in enumerate(items):
            idx += 1
            s = na + j * span
            e = min(na + (j + 1) * span, nb)
            out.append(f"{idx}\n{fmt(s)} --> {fmt(e)}\n{b['text']}")
    open(SRT, "w", encoding="utf-8").write("\n\n".join(out) + "\n")

    total = windows[-1][1]
    print(f"已重排 {len(out)} 条字幕（原文件备份为 {SRT}.bak）")
    print(f"新总时长：{int(total // 60)} 分 {total % 60:.0f} 秒")
    for i, (a, b) in enumerate(windows, 1):
        print(f"  镜头{i}: {fmt(a)[3:8]}-{fmt(b)[3:8]}  {b - a:>5.0f} 秒"
              f"  字幕 {len(groups[i])} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
