# -*- coding: utf-8 -*-
# make_video_assets.py —— 生成"视频素材"图（1920x1080 满屏画布 + 标题/来源），
# 供剪映 / WPS 演示直接拖入视频轨使用。
# 输出目录：视频素材/
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "视频素材")
W, H = 1920, 1080
BG = (255, 255, 255)
INK = (26, 26, 26)
GREY = (110, 110, 110)
ACCENT = (17, 94, 166)

FONT_BOLD = r"C:\Windows\Fonts\simhei.ttf"
FONT_REG = r"C:\Windows\Fonts\simsun.ttc"


def font(size, bold=True):
    path = FONT_BOLD if bold else FONT_REG
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def compose(chart_path, title, subtitle, out_name, footer="数据来源：results_summary.md（冻结口径）"):
    """把一张图放进 1080p 画布：顶部标题 + 居中图 + 底部来源。"""
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)

    d.text((80, 46), title, font=font(52), fill=INK)
    if subtitle:
        d.text((80, 118), subtitle, font=font(28, bold=False), fill=ACCENT)
    d.line([(80, 172), (W - 80, 172)], fill=(225, 225, 225), width=2)

    if chart_path and os.path.isfile(chart_path):
        img = Image.open(chart_path).convert("RGB")
        max_w, max_h = W - 260, H - 172 - 140
        ratio = min(max_w / img.width, max_h / img.height)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)),
                         Image.LANCZOS)
        canvas.paste(img, ((W - img.width) // 2, 172 + (max_h - img.height) // 2))

    d.text((80, H - 74), footer, font=font(24, bold=False), fill=GREY)
    path = os.path.join(OUT, out_name)
    canvas.save(path)
    print(f"  {out_name}  ({os.path.getsize(path):,} B)")


def text_card(lines, out_name, footer=None):
    """纯文字卡（标题卡 / 结尾卡）。"""
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    y = 300
    for text, size, color, bold in lines:
        f = font(size, bold)
        w = d.textlength(text, font=f)
        d.text(((W - w) / 2, y), text, font=f, fill=color)
        y += size + 34
    if footer:
        f = font(26, False)
        w = d.textlength(footer, font=f)
        d.text(((W - w) / 2, H - 90), footer, font=f, fill=GREY)
    path = os.path.join(OUT, out_name)
    canvas.save(path)
    print(f"  {out_name}  ({os.path.getsize(path):,} B)")


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f"输出目录: {OUT}")

    text_card([
        ("SoundInsight", 96, INK, True),
        ("蓝牙耳机音质差评智能归因系统", 48, ACCENT, True),
        ("10 万条真实评论 · RLCA 两阶段标注 · DistilBERT 二分类 + 五类归因", 34, GREY, False),
    ], "00_标题卡.png", footer="团队：更新世界的锋芒")

    compose(os.path.join(HERE, "learning_curve.png"),
            "验证 ①  学习曲线", "正例 100 → 1257，F1 0.4067 → 0.6179（无泄漏 bootstrap）",
            "01_学习曲线.png")
    compose(os.path.join(HERE, "pr_curve.png"),
            "验证 ②  PR 曲线", "AUC-PR = 0.7191",
            "02_PR曲线.png")
    compose(os.path.join(HERE, "confusion_matrix.png"),
            "验证 ③  混淆矩阵", "阈值 0.9744：TP 179 / FP 91 / FN 72 / TN 19658",
            "03_混淆矩阵.png")
    compose(os.path.join(HERE, "calibration_curve.png"),
            "验证 ④  可靠性曲线（校准）",
            "ECE 0.0122；决策区间过度自信 → 界面标注“未经校准，仅供排序参考”",
            "04_校准曲线.png")
    compose(os.path.join(HERE, "architecture.png"),
            "系统架构", "数据层 → RLCA 标注层 → 模型层 → 应用层（Agent / Demo / API）",
            "05_系统架构.png")
    compose(os.path.join(HERE, "trend_over_time.png"),
            "时序验证", "月度音质差评率趋势（2021-2023）；跨年份分桶无衰减，2022 桶 F1 0.80",
            "06_时序趋势.png")

    text_card([
        ("SoundInsight", 84, INK, True),
        ("让每一条差评，都成为产品进化的信号", 44, ACCENT, True),
        ("在线 Demo：modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight", 32, GREY, False),
        ("代码仓库：gitcode.com/DaiYanQBZ95Doll/soundinsight", 32, GREY, False),
    ], "07_结尾卡.png", footer="更新世界的锋芒")

    print("\n完成。剪辑时把图片拖入视频轨，按 素材清单.md 的时间轴摆放即可。")


if __name__ == "__main__":
    main()
