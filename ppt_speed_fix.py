# -*- coding: utf-8 -*-
# 本脚本用于修复 PPT 中"2 分钟/99.6%"的旧耗时表述，改为实测值：
# "2 分钟"→"约 2 秒(GPU实测)"、"99.6%"→">99.9%"、"8h → 2min"→"8h → ~2s (GPU)"。
# 用标准库 zipfile 原地替换 XML 文本节点，保持其余字节不动，先备份 .bak。
import os
import re
import shutil
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PPTX = os.path.join(HERE, "SoundInsight：跨境电商耳机音质差评智能归因系统.pptx")

REPLACEMENTS = [
    ("从8小时压缩至2分钟", "从8小时压缩至约2秒(GPU实测)"),
    ("2分钟", "约2秒(GPU实测)"),
    ("2 分钟", "约 2 秒(GPU实测)"),
    ("8h → 2min", "8h → ~2s (GPU)"),
    ("Time 8h → 2min", "Time 8h → ~2s (GPU)"),
    ("提升99.6%", "提升>99.9%"),
    ("效率提升 99.6%", "效率提升 >99.9%"),
    ("99.6% ↓", ">99.9% ↓"),
    ("2分钟/0元", "约2秒(GPU实测)/0元"),
]


def main() -> None:
    if not os.path.isfile(PPTX):
        raise SystemExit("未找到 pptx 文件")
    bak = PPTX + ".bak"
    if not os.path.isfile(bak):
        shutil.copy2(PPTX, bak)
        print(f"备份 -> {bak}")

    z = zipfile.ZipFile(PPTX)
    infos = {n: z.read(n) for n in z.namelist()}
    hits = 0
    new_contents = {}
    for name, data in infos.items():
        if re.fullmatch(r"ppt/slides/slide\d+\.xml", name):
            text = data.decode("utf-8", errors="replace")
            changed = False
            for old, new in REPLACEMENTS:
                if old in text:
                    text = text.replace(old, new)
                    hits += 1
                    changed = True
            new_contents[name] = (text.encode("utf-8") if changed else data)
    z.close()

    if hits == 0:
        print("FAIL：未找到任何目标字符串。请人工检查 PPT 成本页的实际文本。")
        return

    with zipfile.ZipFile(PPTX, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in infos.items():
            z.writestr(name, new_contents.get(name, data))
    print(f"替换 {hits} 处，文件已重打包 -> {PPTX}")
    print("验证：请重跑 audit_ppt.py 并在 PowerPoint 中打开确认。")


if __name__ == "__main__":
    main()
