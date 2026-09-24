# -*- coding: utf-8 -*-
# 抽取官方模板 docx 的结构与正文，用于格式对照。
# 用法：python extract_template.py [模板.docx]
#   不带参数时默认抽复赛模板；决赛模板示例：
#   python extract_template.py "hackathon-决赛入围定稿作品提交模板-天池版.docx"
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = "hackathon-复赛作品提交模板-天池版.docx"
DOCX = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
if not os.path.isabs(DOCX):
    DOCX = os.path.join(HERE, DOCX)
if not os.path.isfile(DOCX):
    print(f"找不到模板文件：{DOCX}")
    sys.exit(2)
print(f"模板：{os.path.basename(DOCX)}")

z = zipfile.ZipFile(DOCX)
xml = z.read("word/document.xml").decode("utf-8", errors="replace")

# 按段落切分，保留段落边界
paras = re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S)
out = []
for p in paras:
    texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, flags=re.S)
    line = "".join(texts)
    line = (line.replace("&amp;", "&").replace("&lt;", "<")
            .replace("&gt;", ">").replace("&quot;", '"'))
    style = re.search(r'w:val="([^"]+)"', p)
    out.append((style.group(1) if style else "", line.strip()))

print(f"段落数: {len(out)}")
print("=" * 70)
for st, line in out:
    if not line:
        continue
    marker = f"[{st}] " if st and ("Head" in st or "标题" in st) else ""
    print(marker + line)
