# -*- coding: utf-8 -*-
# md_to_pdf.py —— 把复赛主文档（Markdown）转成真正的 PDF（无需 Typora / pandoc / WPS）
#
# 中文用 reportlab 内置 CID 字体 STSong-Light（无需外部字体文件）。
# 用法：
#   python md_to_pdf.py competition_v4.md "更新世界的锋芒_SoundInsight_复赛作品.pdf"
import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 优先内嵌系统字体（PDF 自带字形，任何阅读器/WPS 都不会出现方框）；
# 找不到时退回 reportlab 内置中文 CID 字体（依赖阅读器字体）。
FONT = "STSong-Light"
BOLD_FONT = "STSong-Light"
_WIN_FONTS = r"C:\Windows\Fonts"
_CANDIDATES = [
    ("SimSun", os.path.join(_WIN_FONTS, "simsun.ttc"), 0, "SimHei",
     os.path.join(_WIN_FONTS, "simhei.ttf")),
    ("MSYH", os.path.join(_WIN_FONTS, "msyh.ttc"), 0, "MSYH", None),
]
for normal_name, normal_path, idx, bold_name, bold_path in _CANDIDATES:
    if not os.path.isfile(normal_path):
        continue
    try:
        pdfmetrics.registerFont(TTFont(normal_name, normal_path,
                                       subfontIndex=idx))
        if bold_path and os.path.isfile(bold_path):
            pdfmetrics.registerFont(TTFont(bold_name, bold_path))
            pdfmetrics.registerFontFamily(normal_name, normal=normal_name,
                                          bold=bold_name,
                                          italic=normal_name,
                                          boldItalic=bold_name)
            BOLD_FONT = bold_name
        else:
            BOLD_FONT = normal_name
        FONT = normal_name
        break
    except Exception as e:  # noqa: BLE001 - 字体不可用时退回内置字体
        print(f"字体 {normal_path} 不可用（{type(e).__name__}），尝试下一个")
if FONT == "STSong-Light":
    pdfmetrics.registerFont(UnicodeCIDFont(FONT))
print(f"正文字体: {FONT} ｜ 粗体字体: {BOLD_FONT}")

BODY = ParagraphStyle("body", fontName=FONT, fontSize=10.5, leading=16,
                      spaceAfter=4)
H1 = ParagraphStyle("h1", fontName=FONT, fontSize=18, leading=24,
                    spaceBefore=6, spaceAfter=10)
H2 = ParagraphStyle("h2", fontName=FONT, fontSize=14.5, leading=20,
                    spaceBefore=14, spaceAfter=8)
H3 = ParagraphStyle("h3", fontName=FONT, fontSize=12, leading=17,
                    spaceBefore=10, spaceAfter=6)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=14,
                        bulletIndent=4, spaceAfter=3)
NOTE = ParagraphStyle("note", parent=BODY, fontSize=9,
                      textColor=colors.grey, alignment=TA_CENTER)

INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def inline_md(text):
    """Markdown 行内标记 → reportlab 迷你 HTML。"""
    out = []
    for piece in INLINE.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**") and len(piece) > 4:
            out.append(f"<b>{esc(piece[2:-2])}</b>")
        elif piece.startswith("`") and piece.endswith("`") and len(piece) > 2:
            out.append(f'<font face="Courier">{esc(piece[1:-1])}</font>')
        else:
            out.append(esc(piece))
    return "".join(out)


def is_table_sep(line):
    return bool(re.fullmatch(r"\|[\s:|-]+\|", line.strip()))


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def convert(md_path, out_path):
    with open(md_path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    flow = []
    i = 0
    n_table = n_head = n_para = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue

        if re.fullmatch(r"-{3,}", stripped):
            flow.append(Spacer(1, 4))
            flow.append(HRFlowable(width="100%", thickness=0.5,
                                   color=colors.HexColor("#bbbbbb")))
            flow.append(Spacer(1, 6))
            i += 1
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level, text = len(m.group(1)), m.group(2)
            style = {1: H1, 2: H2, 3: H3, 4: H3}[min(level, 4)]
            flow.append(Paragraph(inline_md(text), style))
            n_head += 1
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) \
                and is_table_sep(lines[i + 1]):
            header = split_row(stripped)
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(split_row(lines[j]))
                j += 1
            data = [[Paragraph(f"<b>{inline_md(c)}</b>", BODY)
                     for c in header]]
            for row in rows:
                data.append([Paragraph(inline_md(row[k] if k < len(row)
                                                 else ""), BODY)
                             for k in range(len(header))])
            t = Table(data, repeatRows=1, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
                ("BACKGROUND", (0, 0), (-1, 0),
                 colors.HexColor("#eeeeee")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            flow.append(t)
            flow.append(Spacer(1, 8))
            n_table += 1
            i = j
            continue

        m = re.match(r"^[-*]\s+(.*)$", stripped)
        if m:
            flow.append(Paragraph(inline_md(m.group(1)), BULLET,
                                  bulletText="•"))
            n_para += 1
            i += 1
            continue

        m = re.match(r"^(\d+)[.、)]\s+(.*)$", stripped)
        if m:
            flow.append(Paragraph(inline_md(m.group(2)), BULLET,
                                  bulletText=f"{m.group(1)}."))
            n_para += 1
            i += 1
            continue

        flow.append(Paragraph(inline_md(stripped), BODY))
        n_para += 1
        i += 1

    doc = SimpleDocTemplate(out_path, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="SoundInsight 复赛作品文档",
                            author="更新世界的锋芒")
    doc.build(flow)

    with open(out_path, "rb") as f:
        blob = f.read()
    pages = re.search(rb"/Count\s+(\d+)", blob)
    print(f"段落 {n_para} ｜ 标题 {n_head} ｜ 表格 {n_table}")
    print(f"已生成 -> {out_path}（{len(blob):,} B，"
          f"页数约 {pages.group(1).decode() if pages else '?'}）")


def main():
    md = sys.argv[1] if len(sys.argv) > 1 else "competition_v4.md"
    out = sys.argv[2] if len(sys.argv) > 2 else \
        "更新世界的锋芒_SoundInsight_复赛作品.pdf"
    convert(md, out)


if __name__ == "__main__":
    main()
