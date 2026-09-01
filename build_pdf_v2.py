# -*- coding: utf-8 -*-
# 本脚本用于生成复赛版方案 PDF：读取 competition_v2.txt 排版为 A4 文档，
# 附加材料中为两张图片各预留一整页，末尾输出附录，第二页起标注页码。
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FONT_CN = "Microsoft YaHei"
FONT_MONO = "Consolas"
PAGE_W, PAGE_H = 595.28, 841.89
ML = MR = MT = MB = 56.7
CONTENT_W = PAGE_W - ML - MR
HERE = os.path.dirname(os.path.abspath(__file__))
SRC_TXT = os.path.join(HERE, "competition_v2.txt")
OUT_PDF = os.path.join(HERE, "SoundInsight_创意方案_v2.pdf")
TXT_FILE = os.path.join(HERE, "training_output.txt")

IMAGE_PAGE_1 = (
    "图1：三条测试评论预测概率柱状图",
    "三条测试评论的音质负面概率预测柱状图，含阈值参考线",
    os.path.join(HERE, "demo_output.png"),
)
IMAGE_PAGE_2 = (
    "图2：验证集混淆矩阵",
    "验证集混淆矩阵，展示模型对音质负面与正常评论的判定分布",
    os.path.join(HERE, "confusion_matrix.png"),
)

HEADINGS = {
    "行业背景：": "行业背景",
    "方案名称：": None,          # 主标题
    "方案概述：": "方案概述",
    "技术方案：": "技术方案",
    "附加材料说明：": "附加材料说明",
}


def tokenize(text):
    return re.findall(
        r"[A-Za-z0-9%.\-/:,;()\"'#+±]+|[\u4e00-\u9fff]|[^\sA-Za-z0-9\u4e00-\u9fff]",
        text)


class Doc:
    def __init__(self, pdf):
        self.pdf = pdf
        self.fig = None
        self.ax = None
        self.renderer = None
        self.y = 0.0
        self.page_no = 0
        self.new_page()

    def new_page(self):
        if self.fig is not None:
            if self.page_no >= 2:
                from matplotlib.font_manager import FontProperties
                fp = FontProperties(family=FONT_CN, size=9)
                self.ax.text(PAGE_W / 2, 30, str(self.page_no),
                             fontproperties=fp, color="#888888",
                             va="center", ha="center")
            self.pdf.savefig(self.fig)
            plt.close(self.fig)
        self.page_no += 1
        self.fig = plt.figure(figsize=(PAGE_W / 72, PAGE_H / 72))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, PAGE_W)
        self.ax.set_ylim(0, PAGE_H)
        self.ax.axis("off")
        self.fig.canvas.draw()
        self.renderer = self.fig.canvas.get_renderer()
        self.y = PAGE_H - MT

    def measure(self, text, size, weight="normal"):
        from matplotlib.font_manager import FontProperties
        fp = FontProperties(family=FONT_CN, size=size, weight=weight)
        t = self.fig.text(0, 0, text, fontproperties=fp)
        w = t.get_window_extent(self.renderer).width * 72 / self.fig.dpi
        t.remove()
        return w

    def wrap(self, text, size, weight="normal"):
        lines, cur = [], ""
        for tok in tokenize(text):
            trial = cur + tok
            if cur and self.measure(trial, size, weight) > CONTENT_W:
                lines.append(cur)
                cur = tok
            else:
                cur = trial
        if cur:
            lines.append(cur)
        return lines

    def draw_text(self, text, size, weight="normal", color="#111111",
                  align="center" if False else "left"):
        from matplotlib.font_manager import FontProperties
        fp = FontProperties(family=FONT_CN, size=size, weight=weight)
        x0 = PAGE_W / 2 if align == "center" else ML
        for line in self.wrap(text, size, weight):
            if self.y < MB + size:
                self.new_page()
            self.ax.text(x0, self.y, line, fontproperties=fp, color=color,
                         va="top", ha=align)
            self.y -= size * 1.7

    def gap(self, pts):
        self.y -= pts
        if self.y < MB:
            self.new_page()

    def paragraph(self, text, size=11.5):
        self.draw_text(text, size)
        self.gap(size * 0.9)

    def heading(self, text, size=16):
        self.gap(size * 1.1)
        self.draw_text(text, size, weight="bold")
        self.gap(size * 0.7)

    def image_page(self, title, desc, path):
        from matplotlib.font_manager import FontProperties
        self.new_page()
        cy = PAGE_H / 2
        fp_t = FontProperties(family=FONT_CN, size=17, weight="bold")
        fp_d = FontProperties(family=FONT_CN, size=11.5)
        fp_p = FontProperties(family=FONT_CN, size=9)
        self.ax.text(PAGE_W / 2, cy + 30, title, fontproperties=fp_t,
                     color="#111111", va="center", ha="center")
        self.ax.text(PAGE_W / 2, cy - 12, desc, fontproperties=fp_d,
                     color="#333333", va="center", ha="center")
        self.ax.text(PAGE_W / 2, cy - 42,
                     "（预留空白页，请在此插入图片文件：" + path + "）",
                     fontproperties=fp_p, color="#999999",
                     va="center", ha="center")

    def appendix(self, title):
        from matplotlib.font_manager import FontProperties
        self.new_page()
        self.heading(title)
        with open(TXT_FILE, encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.ax.text(ML, self.y,
                     "来源文件：" + TXT_FILE,
                     fontproperties=FontProperties(family=FONT_CN, size=9),
                     color="#666666", va="top")
        self.y -= 16
        fp = FontProperties(family=FONT_MONO, size=9)
        for line in content.splitlines():
            if self.y < MB + 9:
                self.new_page()
            self.ax.text(ML, self.y, line if line else " ",
                         fontproperties=fp, color="#222222", va="top")
            self.y -= 13

    def finish(self):
        self.pdf.savefig(self.fig)
        plt.close(self.fig)


def main() -> None:
    with open(SRC_TXT, encoding="utf-8") as f:
        paragraphs = [p.strip() for p in f.read().split("\n\n") if p.strip()]

    with PdfPages(OUT_PDF) as pdf:
        doc = Doc(pdf)
        current = None
        for p in paragraphs:
            matched = False
            for key, heading in HEADINGS.items():
                if p.startswith(key):
                    body = p[len(key):].strip()
                    if heading is None:
                        doc.heading(body, size=20)
                    else:
                        doc.heading(heading)
                        doc.paragraph(body)
                    current = heading or "标题"
                    matched = True
                    break
            if not matched:
                doc.paragraph(p)
        doc.image_page(*IMAGE_PAGE_1)
        doc.image_page(*IMAGE_PAGE_2)
        doc.appendix("附录：训练结果完整控制台输出")
        doc.finish()
        pages = pdf.get_pagecount() if hasattr(pdf, "get_pagecount") else "?"

    size = os.path.getsize(OUT_PDF)
    print(f"PDF 已生成: {OUT_PDF}")
    print(f"页数: {pages} | 大小: {size} bytes")


if __name__ == "__main__":
    main()
