# -*- coding: utf-8 -*-
# 本脚本用于生成复赛版方案 PDF v3：读取 competition_v2.txt 排版为 A4 文档，
# 支持 Markdown 二级标题、行内加粗与表格渲染，附加材料中为两张图片各预留一整页，
# 末尾输出附录，第二页起标注页码。
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
OUT_PDF = os.path.join(HERE, "SoundInsight_创意方案_v5.pdf")
TXT_FILE = os.path.join(HERE, "training_output.txt")

# 图片预留页标题与说明：英文硬编码，避免中文编码兼容问题
IMAGE_PAGE_1 = (
    "Demo: Three Test Reviews",
    "Predicted sound-negative probabilities of three test reviews with "
    "threshold reference line",
    os.path.join(HERE, "demo_output.png"),
)
IMAGE_PAGE_2 = (
    "Confusion Matrix (Threshold = 0.97)",
    "Validation-set confusion matrix showing classification of "
    "sound-negative vs normal reviews",
    os.path.join(HERE, "confusion_matrix.png"),
)

HEADINGS = {
    "行业背景：": "行业背景",
    "方案名称：": None,
    "方案概述：": "方案概述",
    "技术方案：": "技术方案",
    "附加材料说明：": "附加材料说明",
}


def tokenize(text):
    return re.findall(
        r"[A-Za-z0-9%.\-/:,;()\"'#+±]+|[\u4e00-\u9fff]|[^\sA-Za-z0-9\u4e00-\u9fff]",
        text)


def parse_runs(text):
    """Split markdown text into (segment, is_bold) runs on ** markers."""
    runs = []
    for i, part in enumerate(text.split("**")):
        if part:
            runs.append((part, i % 2 == 1))
    return runs


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

    def wrap_runs(self, runs, size, max_w):
        """Greedy wrap of (text, bold) runs into lines of runs."""
        lines, cur, cur_w = [], [], 0.0
        for text, bold in runs:
            weight = "bold" if bold else "normal"
            for tok in tokenize(text):
                w = self.measure(tok, size, weight)
                if cur and cur_w + w > max_w:
                    lines.append(cur)
                    cur, cur_w = [], 0.0
                cur.append((tok, bold))
                cur_w += w
        if cur:
            lines.append(cur)
        return lines

    def draw_runs_line(self, runs, size, x, y, color="#111111"):
        from matplotlib.font_manager import FontProperties
        cursor = x
        for text, bold in runs:
            fp = FontProperties(family=FONT_CN, size=size,
                                weight="bold" if bold else "normal")
            self.ax.text(cursor, y, text, fontproperties=fp, color=color,
                         va="top", ha="left")
            cursor += self.measure(text, size,
                                   "bold" if bold else "normal")
        return cursor

    def draw_text(self, text, size, weight="normal", color="#111111",
                  align="left"):
        from matplotlib.font_manager import FontProperties
        fp = FontProperties(family=FONT_CN, size=size, weight=weight)
        x0 = PAGE_W / 2 if align == "center" else ML
        runs = parse_runs(text)
        has_bold = any(b for _, b in runs)
        if not has_bold:
            for line in self.wrap_runs(runs, size, CONTENT_W):
                if self.y < MB + size:
                    self.new_page()
                self.draw_runs_line(line, size, x0, self.y, color)
                self.y -= size * 1.7
        else:
            for line in self.wrap_runs(runs, size, CONTENT_W):
                if self.y < MB + size:
                    self.new_page()
                total_w = sum(self.measure(t, size,
                                           "bold" if b else "normal")
                              for t, b in line)
                lx = x0 if align == "left" else PAGE_W / 2 - total_w / 2
                self.draw_runs_line(line, size, lx, self.y, color)
                self.y -= size * 1.7

    def gap(self, pts):
        self.y -= pts
        if self.y < MB:
            self.new_page()

    def paragraph(self, text, size=11.5):
        text = text.rstrip()
        if text.startswith("### "):
            self.subheading(text[4:].strip(), size=13)
            return
        if text.startswith("## "):
            self.heading(text[3:].strip(), size=15)
            return
        if text.startswith("|"):
            self.table(text, size=10)
            return
        # 保留段落内的硬换行：每行独立渲染，行与行之间换行不空行
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                self.gap(size * 0.6)
                continue
            self.draw_text(line, size)
            self.y -= size * 0.35
        self.gap(size * 0.9)

    def subheading(self, text, size=13):
        self.gap(size * 0.9)
        self.draw_text(text, size, weight="bold")
        self.gap(size * 0.5)

    def heading(self, text, size=16):
        self.gap(size * 1.1)
        self.draw_text(text, size, weight="bold")
        self.gap(size * 0.7)

    def table(self, text, size=10):
        lines = [l.strip() for l in text.split("\n") if l.strip().startswith("|")]
        rows = []
        for l in lines:
            cells = [c.strip() for c in l.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                continue
            rows.append([c.replace("**", "") for c in cells])
        if not rows:
            return
        n_cols = len(rows[0])
        pad = 8
        widths = []
        for c in range(n_cols):
            w = max(self.measure(r[c], size, "bold" if i == 0 else "normal")
                    for i, r in enumerate(rows) if c < len(r))
            widths.append(min(w, CONTENT_W * 0.5))
        total = sum(widths) + pad * 2 * n_cols
        if total > CONTENT_W:
            scale = CONTENT_W / total
            widths = [w * scale for w in widths]
        row_h = size * 1.9
        n_lines_rows = []
        for r in rows:
            max_lines = 1
            for c in range(n_cols):
                cell_lines = self.wrap_runs(parse_runs(r[c]), size,
                                            widths[c] - pad)
                max_lines = max(max_lines, len(cell_lines))
            n_lines_rows.append(max_lines)
        table_h = sum(row_h * nl for nl in n_lines_rows)
        if self.y - table_h < MB:
            self.new_page()
        top = self.y
        from matplotlib.font_manager import FontProperties
        x = ML
        for c in range(n_cols):
            if self.y < MB + size:
                self.new_page()
            self.ax.add_patch(plt.Rectangle((x, self.y - row_h),
                                            widths[c] + pad * 2, row_h,
                                            facecolor="#eef2f7",
                                            edgecolor="#999999", linewidth=0.8))
            cell = rows[0][c] if c < len(rows[0]) else ""
            self.draw_runs_line(parse_runs(cell), size, x + pad,
                                self.y - size * 0.7,
                                color="#111111")
            x += widths[c] + pad * 2
        self.y -= row_h
        for i, r in enumerate(rows[1:], start=1):
            nl = n_lines_rows[i]
            h = row_h * nl
            x = ML
            for c in range(n_cols):
                self.ax.add_patch(plt.Rectangle((x, self.y - h),
                                                widths[c] + pad * 2, h,
                                                facecolor="white",
                                                edgecolor="#999999",
                                                linewidth=0.8))
                cell = r[c] if c < len(r) else ""
                yy = self.y - size * 0.7
                for line in self.wrap_runs(parse_runs(cell), size,
                                           widths[c] - pad):
                    self.draw_runs_line(line, size, x + pad, yy,
                                        color="#333333")
                    yy -= size * 1.6
                x += widths[c] + pad * 2
            self.y -= h
        self.gap(16)

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
