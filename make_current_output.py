# -*- coding: utf-8 -*-
"""生成「当前输出版本」对照件（HTML）：把当前 Demo 报告渲染成可直接打开的页面，
用于对照 9/14 版演示视频——让评委不必重录视频也能看到当前界面与其新增内容。

产出：`当前输出版本（对照视频）.html`（自包含、零依赖）
"""
from __future__ import annotations

import html
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "insight_report_v2.md")
OUT = os.path.join(HERE, "当前输出版本（对照视频）.html")
if not os.path.isfile(SRC):
    print("[跳过] insight_report_v2.md 不存在（先跑一次 Agent）")
    sys.exit(1)
md = open(SRC, encoding="utf-8", errors="replace").read()

HEAD = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>SoundInsight 当前输出版本（对照 9/14 演示视频）</title>
<style>
 body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;max-width:900px;
      margin:32px auto;padding:0 20px;line-height:1.75;color:#1f2328}
 h1{font-size:24px;border-bottom:2px solid #d0d7de;padding-bottom:8px}
 h2{font-size:19px;margin-top:28px;color:#0a3069}
 .note{background:#fff8c5;border:1px solid #d4a72c;border-radius:6px;padding:12px 16px;margin:16px 0}
 .new{background:#ddf4ff;border-left:4px solid #0969da;padding:8px 12px;margin:8px 0}
 code{background:#f6f8fa;padding:2px 5px;border-radius:4px}
 pre{white-space:pre-wrap;word-wrap:break-word;background:#f6f8fa;padding:12px;border-radius:6px}
</style></head><body>
<div class="note"><b>证据等级（请先读）</b>：本件为**脚本渲染的当前输出快照**（由本仓库管线实跑生成），<b>不是屏幕录制</b>；界面实录见演示视频（2026-09-14 版，界面与指标属 v1 世代）。<b>冲突时以本件与主文档为准。</b></div>
<div class="note"><b>本件用途</b>：包内演示视频为 <b>2026-09-14 成片</b>，其界面与指标属 v1 世代，
<b>不含</b>下列当前功能。本页为<b>当前出厂版本的真实输出</b>（同一次 Demo 运行生成），
用于对照视频阅读；<b>两者不一致时，以本页与主文档为准</b>。</div>
<div class="new"><b>与本视频的差异（当前新增）</b>：
① 三档输出（优先处理档／待复核档／范围外档）；
② 「未判定 ≠ 正常」显式声明；
③ 非音质差评的类型分布（初步）；
④ 不可归因原因（提到声音但说不清）；
⑤ 品类字段（本地品类模型）。</div>
<h1>SoundInsight 当前输出版本（Demo 报告原文）</h1>
"""


def md_to_html(text: str) -> str:
    out = []
    for raw in text.splitlines():
        ln = html.escape(raw)
        if raw.startswith("### "):
            out.append(f"<h3>{ln[4:]}</h3>")
        elif raw.startswith("## "):
            out.append(f"<h2>{ln[3:]}</h2>")
        elif raw.startswith("# "):
            out.append(f"<h1>{ln[2:]}</h1>")
        elif raw.startswith("|") and raw.count("|") >= 3:
            out.append(f"<pre>{ln}</pre>")
        elif raw.strip() == "":
            out.append("")
        else:
            ln = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", ln)
            ln = re.sub(r"`(.+?)`", r"<code>\1</code>", ln)
            out.append(f"<p>{ln}</p>")
    return "\n".join(out)


open(OUT, "w", encoding="utf-8", newline="\n").write(HEAD + md_to_html(md) + "\n</body></html>\n")
print(f"[写出] {os.path.basename(OUT)}（{os.path.getsize(OUT):,} B）")
# 同时把报告原文放进包里（纯文本，便于 diff）
open(os.path.join(HERE, "当前输出版本_报告原文.md"), "w", encoding="utf-8",
     newline="\n").write(md)
print("[写出] 当前输出版本_报告原文.md")
