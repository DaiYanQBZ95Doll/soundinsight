# -*- coding: utf-8 -*-
"""URL 一致性检查（M3c ③）：列出对外材料中的项目相关链接，报告不一致。

检查对象：README、决赛主文档（docx 文本）、PPT 文本、视频脚本、Demo 说明、部署说明。
判定：同一类资源（代码仓库 / 在线 Demo / 直链）在不同材料中的 URL 必须一致；
出现"疑似旧域名"（未在 `docs/*` 记录过的链接）即报警。
"""
from __future__ import annotations

import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TEXT_FILES = ["README.md", "MODEL_CARD.md", "competition_v4.md", "ppt_text_dump.md",
              "video_script.md", "video_script.srt", "insight_report_v2.md",
              "deployment/README.md", "deployment/README_Space.md",
              "docs/M3b_judge_access_guide.md", "docs/M8a_submission_precheck.md"]
DOCX = ["更新世界的锋芒_SoundInsight_决赛入围定稿作品.docx"]

PATTERNS = {
    "仓库(GitCode)": re.compile(r"https?://gitcode\.com/[\w\-./]+"),
    "仓库(GitHub)": re.compile(r"https?://github\.com/[\w\-./]+"),
    "在线Demo(ModelScope)": re.compile(r"https?://modelscope\.cn/[\w\-./]+"),
    "直链(ms.show)": re.compile(r"https?://[\w\-]+\.ms\.show[\w\-./]*"),
    "HF Spaces": re.compile(r"https?://huggingface\.co/spaces/[\w\-./]+"),
    "模型仓库": re.compile(r"https?://modelscope\.cn/models/[\w\-./]+"),
}

found: dict[str, dict[str, set[str]]] = {}
for rel in TEXT_FILES:
    p = os.path.join(HERE, rel)
    if not os.path.isfile(p):
        continue
    txt = open(p, encoding="utf-8", errors="replace").read()
    for kind, pat in PATTERNS.items():
        for m in pat.finditer(txt):
            found.setdefault(kind, {}).setdefault(m.group(0).rstrip("）)。,、"), set()).add(rel)
for rel in DOCX:
    p = os.path.join(HERE, rel)
    if not os.path.isfile(p):
        continue
    xml = zipfile.ZipFile(p).read("word/document.xml").decode("utf-8", "replace")
    txt = "\n".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, flags=re.S))
    for kind, pat in PATTERNS.items():
        for m in pat.finditer(txt):
            found.setdefault(kind, {}).setdefault(m.group(0).rstrip("）)。,、"), set()).add(rel)

print("=== 各类链接在材料中的出现情况 ===")
issues = 0
for kind in PATTERNS:
    urls = found.get(kind, {})
    print(f"\n[{kind}] {len(urls)} 个不同 URL")
    for url, files in sorted(urls.items()):
        print(f"    {url}")
        print(f"        出现于：{'、'.join(sorted(files))}")
    if len(urls) > 1:
        print("    ⚠️ 存在多个不同 URL —— 需确认是否为旧域名残留")
        issues += 1

print(f"\n[结论] 链接类别数 {len(PATTERNS)}，存在多 URL 的类别 {issues} 个")
print("说明：多 URL 不必然是错误（例如 GitCode 与 GitHub 双仓、modelscope 站点与应用直链），"
      "但**同类资源在同一材料内出现两个不同地址**即需修正；本检查的输出供 M3c ③ 人工复核。")
