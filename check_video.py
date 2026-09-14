# -*- coding: utf-8 -*-
# check_video.py —— 校验演示视频文件：命名、大小、时长、分辨率、帧率，
# 并抽取若干关键时间点的画面供人工核对（输出到 _video_frames/）。
import glob
import os
import sys

import cv2

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = "更新世界的锋芒_SoundInsight_演示视频.mp4"
OUT = os.path.join(HERE, "_video_frames")

cands = sorted(glob.glob(os.path.join(HERE, "*.mp4")))
print("项目根目录下的视频文件：")
for c in cands:
    print(f"  {os.path.basename(c)}  ({os.path.getsize(c):,} B)")

path = os.path.join(HERE, TARGET)
if not os.path.isfile(path):
    print(f"\n✗ 未找到规范命名的文件：{TARGET}")
    if cands:
        print(f"  提示：把 {os.path.basename(cands[0])} 改名为 {TARGET} 即可")
    sys.exit(1)

size = os.path.getsize(path)
cap = cv2.VideoCapture(path)
fps = cap.get(cv2.CAP_PROP_FPS)
n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
dur = n / fps if fps else 0
print(f"\n规范命名文件：{TARGET}")
print(f"  大小     : {size:,} B（{size / 1024 / 1024:.1f} MB）")
print(f"  分辨率   : {w}×{h}（{'横屏 16:9 ✓' if abs(w / h - 16 / 9) < 0.05 else '注意：非 16:9'}）")
print(f"  帧率     : {fps:.2f} fps")
print(f"  总帧数   : {n}，时长 {int(dur // 60)} 分 {dur % 60:.1f} 秒")
in_range = 180 <= dur <= 300
print(f"  模板建议 : 3-5 分钟 → {'✓ 符合' if in_range else '✗ 超出建议区间'}")

os.makedirs(OUT, exist_ok=True)
marks = [5, 25, 40, 75, 120, 140, 160, 185, 200]
print(f"\n抽取关键帧（每点一张，存到 _video_frames/）：")
for t in marks:
    if t > dur:
        continue
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    if not ok:
        print(f"  {t:>4}s 抽取失败")
        continue
    fp = os.path.join(OUT, f"frame_{t:03d}s.png")
    cv2.imwrite(fp, frame)
    print(f"  {t:>4}s → {os.path.basename(fp)}")
cap.release()
print("\n完成。")
