# -*- coding: utf-8 -*-
# rebuild_video_timing.py —— 把镜头 2（上传/等待）由 15 秒压到 8 秒，
# 其余镜头整体前移 7 秒，并重建字幕文件（避免字幕与画面错位）。
#
# 变换规则：
#   1) 保留前 3 条字幕（镜头 1：0:00-0:20）不变；
#   2) 把原本属于镜头 2 的两条字幕（第 4、5 条，0:20-0:35）合并为一条 0:20-0:28；
#   3) 其余字幕整体前移 7 秒。
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

P = "video_script.srt"
text = open(P, encoding="utf-8").read()

blocks = []
for blk in text.strip().split("\n\n"):
    lines = blk.strip().splitlines()
    if len(lines) < 3:
        continue
    m = re.match(r"(\d\d):(\d\d):(\d\d),(\d\d\d) --> (\d\d):(\d\d):(\d\d),(\d\d\d)",
                 lines[1])
    if not m:
        continue
    t = [int(x) for x in m.groups()]
    start = t[0] * 3600 + t[1] * 60 + t[2]
    end = t[4] * 3600 + t[5] * 60 + t[6]
    blocks.append({"start": start, "end": end,
                   "text": "\n".join(lines[2:])})

print(f"原字幕：{len(blocks)} 条，末条结束于 {blocks[-1]['end']} 秒")


def fmt(sec: int) -> str:
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d},000"


new = []
for i, b in enumerate(blocks):
    if b["start"] < 20:                      # 镜头 1：原样
        new.append(b)
    elif b["start"] < 35:                    # 镜头 2：合并为一条 0:20-0:28
        if not any(x["start"] == 20 for x in new):
            new.append({"start": 20, "end": 28,
                        "text": "把评论导成一个 CSV，拖进 SoundInsight——"
                                "一百条评论，本地 GPU 一点八秒出结果"})
    else:                                    # 其余整体前移 7 秒
        new.append({"start": b["start"] - 7, "end": b["end"] - 7,
                    "text": b["text"]})

out = []
for i, b in enumerate(new, 1):
    out.append(f"{i}\n{fmt(b['start'])} --> {fmt(b['end'])}\n{b['text']}")
open(P, "w", encoding="utf-8").write("\n\n".join(out) + "\n")

print(f"新字幕：{len(new)} 条，末条结束于 {new[-1]['end']} 秒"
      f"（{new[-1]['end'] // 60} 分 {new[-1]['end'] % 60} 秒）")
print("\n新时间轴：")
print("  镜头1 0:00-0:20 ｜ 镜头2 0:20-0:28 ｜ 镜头3 0:28-1:08")
print("  镜头4 1:08-1:28 ｜ 镜头5 1:28-1:53 ｜ 镜头6 1:53-2:28")
print("  镜头7 2:28-2:48 ｜ 镜头8 2:48-3:03 ｜ 镜头9 3:03-%d:%02d"
      % (new[-1]["end"] // 60, new[-1]["end"] % 60))
