# -*- coding: utf-8 -*-
"""M1 装配：把内容填进官方决赛模板，输出主文档 docx。

内容来源：
- build_finals_content.CONTENT（一~五节）、TEAM、LINKS、BAILIAN_ROWS
- build_finals_appendix.SECTION6（第六节）与 APPENDIX（附录 A~F）

用法：python build_finals_docx.py [--out 文件名.docx]
"""
from __future__ import annotations

import argparse
import os
import sys

from docx import Document

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_finals_appendix import APPENDIX, SECTION6  # noqa: E402
from build_finals_content import BAILIAN_ROWS, CONTENT, LINKS, TEAM  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "hackathon-决赛入围定稿作品提交模板-天池版.docx")
DEFAULT_OUT = os.path.join(HERE, "更新世界的锋芒_SoundInsight_决赛入围定稿作品.docx")

PLAN = dict(CONTENT)
PLAN["六、项目开发及阶段成果说明"] = SECTION6


def set_cell(cell, text: str) -> None:
    cell.text = ""
    cell.paragraphs[0].add_run(text)


def fill_tables(doc) -> None:
    for t in doc.tables:
        header = " ".join(c.text for c in t.rows[0].cells)
        is_bailian = "模型标识" in header
        is_links = ("链接类型" in header) or ("链接地址" in header)
        if is_bailian:
            idx = 1
            for label, usage, link in BAILIAN_ROWS:
                row = t.rows[idx] if idx < len(t.rows) else t.add_row()
                if len(row.cells) >= 3:
                    set_cell(row.cells[0], label)
                    set_cell(row.cells[1], usage)
                    set_cell(row.cells[2], link)
                idx += 1
            continue
        for row in t.rows:
            cells = row.cells
            if not cells or len(cells) < 2:
                continue
            key = cells[0].text.strip()
            if key in TEAM and not cells[1].text.strip():
                set_cell(cells[1], TEAM[key])
            elif key == "参赛场景":
                set_cell(cells[1], "AI市场洞察")
            elif key == "方案名称":
                set_cell(cells[1], "SoundInsight")
            elif key.startswith("一句话定义"):
                set_cell(cells[1], "为跨境电商耳机卖家提供音质差评自动识别与五类问题归因的"
                                   "一站式洞察工具，把人工数小时的差评梳理压缩到分钟级；"
                                   "产品推理 100% 本地。")
            elif is_links:
                for k, v in LINKS.items():
                    if key.startswith(k):
                        set_cell(cells[1], v)


def insert_after(paragraph, lines: list[str]) -> int:
    anchor = paragraph._p
    n = 0
    for line in lines:
        new_p = paragraph.insert_paragraph_before("")
        anchor.addnext(new_p._p)
        new_p.text = line
        anchor = new_p._p
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()
    if not os.path.isfile(TEMPLATE):
        print(f"[FAIL] 缺少模板 {os.path.basename(TEMPLATE)}")
        return 1

    doc = Document(TEMPLATE)
    print(f"模板：段落 {len(doc.paragraphs)}、表格 {len(doc.tables)}")
    inserted, matched = 0, []
    for para in list(doc.paragraphs):
        text = para.text.strip()
        for key, lines in PLAN.items():
            if text == key or text.startswith(key):
                inserted += insert_after(para, lines)
                matched.append(key)
                break
    print(f"已填充小节 {len(matched)}：{'、'.join(matched)}")
    print(f"插入正文段落 {inserted}")
    for line in APPENDIX:
        doc.add_paragraph(line)
    print(f"追加附录段落 {len(APPENDIX)}")
    fill_tables(doc)
    doc.save(args.out)
    print(f"[写出] {os.path.basename(args.out)}（{os.path.getsize(args.out)/1024:.0f} KB）")

    check = Document(args.out)
    all_text = "\n".join(p.text for p in check.paragraphs)
    must = ["0.7220", "0.7811", "0.8273", "已知表述勘误与口径演进",
            "置信度档位与建议动作", "qwen3.7-plus", "deepseek-chat", "0.5333", "68.3%"]
    for m in must:
        print(f"  {'OK  ' if m in all_text else 'MISS'} 含「{m}」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
