# -*- coding: utf-8 -*-
# 本脚本用于修复 PPT 第 19 页 AI 分工角色对调：
# "Kimi（产品头脑风暴）"→"Kimi（技术质检）"、"Qwen（灵感与质检）"→"Qwen（灵感与叙事）"。
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
    ("Kimi（产品头脑风暴）", "Kimi（技术质检）"),
    ("Qwen（灵感与质检）", "Qwen（灵感与叙事）"),
    ("KIMI · 产品经理", "KIMI · 技术质检"),
    ("负责头脑风暴", "负责技术质检"),
]


def main() -> None:
    if not os.path.isfile(PPTX):
        raise SystemExit("未找到 pptx 文件")
    bak = PPTX + ".bak"
    if not os.path.isfile(bak):
        shutil.copy2(PPTX, bak)
        print(f"备份 -> {bak}")

    # 先读取全部条目，检查目标字符串是否存在
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
        print("FAIL：未找到任何目标字符串。请人工检查 PPT 第 19 页的实际文本。")
        print("当前第 19 页提取文本：")
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(HERE, "audit_ppt.py")],
                           capture_output=True, text=True, cwd=HERE)
        dump = os.path.join(HERE, "ppt_text_dump.md")
        if os.path.isfile(dump):
            with open(dump, encoding="utf-8") as f:
                content = f.read()
            for line in content.splitlines():
                if "KIMI" in line or "Qwen" in line or "QWEN" in line:
                    print(" ", line)
        return

    # 按原结构重新打包
    with zipfile.ZipFile(PPTX, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in infos.items():
            z.writestr(name, new_contents.get(name, data))
    print(f"替换 {hits} 处，文件已重打包 -> {PPTX}")
    print("验证：请重跑 audit_ppt.py 并在 PowerPoint 中打开确认。")


if __name__ == "__main__":
    main()
