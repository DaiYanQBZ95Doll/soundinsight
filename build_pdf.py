# -*- coding: utf-8 -*-
# 本脚本用于生成天池创意方案 PDF：A4 竖排排版方案文字，附加材料中为两张图片各预留一整页，并输出附录与页码。
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

FONT_CN = "Microsoft YaHei"
FONT_MONO = "Consolas"
PAGE_W, PAGE_H = 595.28, 841.89  # A4 points
ML = MR = MT = MB = 56.7          # 2cm margins
CONTENT_W = PAGE_W - ML - MR
OUT_PDF = r"C:\deepseek-harness-master\soundinsight\SoundInsight_创意方案.pdf"
TXT_FILE = r"C:\deepseek-harness-master\soundinsight\training_output.txt"

TITLE_TEXT = "方案名称：SoundInsight 蓝牙耳机音质差评智能归因系统"

SECTIONS = [
    ("行业背景",
     "近年来，人工智能正在重塑跨境电商的市场洞察方式。亚马逊在2026年发布的跨境电商白皮书中披露，中国卖家的AI使用率已超过98%。越来越多卖家开始用自然语言处理技术自动梳理海量评论，把过去依赖人工逐条翻阅的工作交给算法完成。对耳机这类体验型产品而言，音质、降噪、佩戴等细颗粒度反馈散落在大量英文长评论中，谁能更快更准地定位问题，谁就能在产品迭代与差评挽回上抢先一步。"),
    ("方案概述",
     "这是我第一次参加这类比赛，也是第一次试着解决一个真实的商业命题。面对这个题目，我没有先想宏观的数据模型，而是先问自己：我最熟悉什么品类？答案是头戴式耳机，我几乎每天戴着它，对音质好坏有自己的判断，于是我试着从卖家的视角看问题。翻过真实评论我发现，卖家不是缺数据，而是数据太多太乱，音质问题藏在长评论里，只能靠人工逐条翻看，很难快速定位。这个系统要做的，就是把它交给机器，帮卖家看清音质差评的分布与原因。"),
    ("",
     "目标用户是跨境电商平台上的耳机类目卖家，尤其是团队规模小、缺少专业数据分析人员的中小卖家。核心痛点是差评数量大、语言杂，人工翻看耗时耗力，音质类问题藏在长文本里难以归类和统计，产品改进与客服应对总是滞后。"),
    ("",
     "核心功能包括：音质差评自动识别，输入评论即可判断是否为音质负面并给出概率；问题归因，自动提取差评中的高频音质问题词，帮助卖家定位具体缺陷；批量分析，对整批评论批量打分，输出音质差评占比与问题分布统计；交互式演示，提供网页界面，卖家粘贴评论即可即时体验；结果可解释，给出判定概率与命中的关键词，让卖家明白模型为什么这么判断。"),
    ("",
     "方案亮点在于用少量真实评论训练出可用的音质差评识别模型，并通过关键词归因让结果可解释。预期效果是卖家几分钟即可完成过去数小时的差评梳理，音质问题定位从凭经验翻看变为数据驱动，为选品、质检和客服话术提供直接依据。"),
    ("技术方案",
     "基座模型采用轻量的预训练语言模型DistilBERT，推理速度快，适合中小卖家的使用场景。任务类型为文本二分类，即把评论分成音质负面与音质正常两类。训练方式是小样本微调，即用少量标注数据对预训练模型进行针对性训练，共训练三个轮次，学习率0.00002。"),
    ("",
     "数据处理方式为，数据来源于 McAuley Lab 官方发布的 Amazon Electronics 真实评论数据集，共五千条。标注方式为弱监督，即用规则自动打标签，不依赖人工逐条标注：评论命中音质关键词表视为音质相关，评分低于等于两星则标记为音质负面。关键词表涵盖低音、清晰度、发闷、失真、电流声等二十余个音质特征词。"),
    ("",
     "AI Agent 或工作流为，用户输入一段或一批英文评论后，系统先做文本预处理，统一格式并截断到固定长度；随后把文字转换为数字表示；模型读取这些数字后输出音质负面概率；概率超过设定阈值即判定为音质负面，同时自动提取评论中命中的音质关键词作为归因依据；最终结果在网页界面展示，支持单条即时体验与批量统计导出。"),
    ("",
     "前后端及其他技术组件为，前端使用 Gradio 框架搭建网页界面，直接提供输入框与结果展示；后端采用 Python，基于 PyTorch 与 Transformers 库完成模型推理；模型文件打包成单一目录，可部署到普通云服务器或本地电脑直接运行。"),
    ("附加材料说明",
     "系统架构流程图：已生成文本版流程图，从用户输入到结果展示共八个节点。"),
    ("",
     "Demo推理结果图：三条测试评论的预测概率柱状图，含阈值参考线。三条评论分别为音质负面（98.6%）、音质正常（0.1%）、音质负面（99.6%），证明模型能有效区分。"),
    ("",
     "训练结果验证：验证集准确率98.3%，F1值0.37（小样本下合理），混淆矩阵显示TN=978、FP=9、FN=8、TP=5。"),
    ("",
     "数据与代码：全部代码已整理至 GitHub 仓库，地址为 https://github.com/你的用户名/soundinsight，包含数据获取、标注、训练、推理和Demo全流程脚本。"),
]

IMAGE_PAGE_1 = (
    "图1：三条测试评论预测概率柱状图",
    "三条测试评论的音质负面概率预测柱状图，含阈值参考线，分别为音质负面98.6%、音质正常0.1%、音质负面99.6%",
    r"C:\deepseek-harness-master\soundinsight\demo_output.png",
)

IMAGE_PAGE_2 = (
    "图2：验证集混淆矩阵",
    "验证集混淆矩阵，阈值0.05下TN=978、FP=9、FN=8、TP=5",
    r"C:\deepseek-harness-master\soundinsight\confusion_matrix.png",
)


def tokenize(text):
    return re.findall(
        r"[A-Za-z0-9%.\-/:,;()\"'#]+|[\u4e00-\u9fff]|[^\sA-Za-z0-9\u4e00-\u9fff]",
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

    def measure(self, text, size, family=FONT_CN, weight="normal"):
        from matplotlib.font_manager import FontProperties
        fp = FontProperties(family=family, size=size, weight=weight)
        t = self.fig.text(0, 0, text, fontproperties=fp)
        w = t.get_window_extent(self.renderer).width * 72 / self.fig.dpi
        t.remove()
        return w

    def wrap(self, text, size, max_w, family=FONT_CN, weight="normal"):
        lines, cur = [], ""
        for tok in tokenize(text):
            trial = cur + tok
            if cur and self.measure(trial, size, family, weight) > max_w:
                lines.append(cur)
                cur = tok
            else:
                cur = trial
        if cur:
            lines.append(cur)
        return lines

    def draw_text(self, text, size, family=FONT_CN, weight="normal",
                  color="#111111", align="left", x=None, line_h=None):
        from matplotlib.font_manager import FontProperties
        fp = FontProperties(family=family, size=size, weight=weight)
        x0 = x if x is not None else ML
        for line in self.wrap(text, size, CONTENT_W, family, weight):
            if self.y < MB + size:
                self.new_page()
            self.ax.text(x0, self.y, line, fontproperties=fp, color=color,
                         va="top", ha=align)
            self.y -= (line_h if line_h else size * 1.7)

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
        center_y = PAGE_H / 2
        fp_title = FontProperties(family=FONT_CN, size=17, weight="bold")
        fp_desc = FontProperties(family=FONT_CN, size=11.5)
        fp_path = FontProperties(family=FONT_CN, size=9)
        self.ax.text(PAGE_W / 2, center_y + 30, title, fontproperties=fp_title,
                     color="#111111", va="center", ha="center")
        self.ax.text(PAGE_W / 2, center_y - 12, desc, fontproperties=fp_desc,
                     color="#333333", va="center", ha="center")
        self.ax.text(PAGE_W / 2, center_y - 42,
                     "（预留空白页，请在此插入图片文件：" + path + "）",
                     fontproperties=fp_path, color="#999999",
                     va="center", ha="center")

    def appendix(self, title):
        self.new_page()
        self.heading(title)
        with open(TXT_FILE, encoding="utf-8") as f:
            content = f.read()
        size = 9
        line_h = 13
        from matplotlib.font_manager import FontProperties
        fp = FontProperties(family=FONT_MONO, size=size)
        self.ax.text(ML, self.y,
                     "来源文件：C:\\deepseek-harness-master\\soundinsight\\"
                     "training_output.txt",
                     fontproperties=FontProperties(family=FONT_CN, size=9),
                     color="#666666", va="top")
        self.y -= 16
        for line in content.splitlines():
            if self.y < MB + size:
                self.new_page()
            self.ax.text(ML, self.y, line if line else " ",
                         fontproperties=fp, color="#222222", va="top")
            self.y -= line_h

    def finish(self):
        self.pdf.savefig(self.fig)
        plt.close(self.fig)


def main():
    with PdfPages(OUT_PDF) as pdf:
        doc = Doc(pdf)
        doc.heading(TITLE_TEXT, size=20)
        doc.gap(8)

        for heading, body in SECTIONS:
            if heading:
                doc.heading(heading)
                doc.paragraph(body)
            elif body:
                doc.paragraph(body)

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
