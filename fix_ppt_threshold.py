# -*- coding: utf-8 -*-
# fix_ppt_threshold.py —— 修正 PPT 中"调优档 F1 与阈值 0.5 档 P/R 并排"的口径混用
#
# 起因：slide10 写"取得F1=0.6871、召回率89.6%"，以及"阈值0.97下的最优F1分数，精确率47.9%与
# 召回率89.6%的帕累托平衡点"——89.6%/47.9% 实际来自阈值 0.5，与 0.6871 不同档。
#
# 做法：与 ppt_speed_fix.py 同源——标准库 zipfile 原地改 XML 文本，其余字节不动，先备份 .bak。
#   ① PARA_MAP：整段合并文本精确匹配（含跨 <a:t> run 的段落），逐字替换，幂等；
#   ② SUB_MAP：段内子串替换（用于段落全文未知处），带"目标串已存在则跳过"的幂等保护。
# 任一 PARA_MAP 项未命中即整体不写回（避免改错），并打印未命中项。
import os
import re
import shutil
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PPTX = os.path.join(HERE, "SoundInsight：跨境电商耳机音质差评智能归因系统.pptx")
BAK = PPTX + ".bak"

# ① 整段精确替换：旧段落全文 -> 新段落全文
PARA_MAP = [
    # slide10 首段：把阈值 0.5 档的召回率换成与 F1=0.6871 同档的召回率
    ("DistilBERT模型在固定验证集（20,000条）上取得F1=0.6871、召回率89.6%，"
     "5折交叉验证波动率仅3.9%。阈值0.97在",
     "DistilBERT模型在固定验证集（20,000条）上取得F1=0.6871、召回率71.3%，"
     "5折交叉验证波动率仅3.9%。阈值0.97在"),
    # slide10 主指标卡：该句在 PPT 里被拆成两个段落，分别替换后语义完整
    ("阈值0.97下的最优F1分数，精确率47.9%与召",
     "阈值0.97下的最优F1分数，同档精确率66.3%、召回率71.3%，是"),
    ("回率89.6%的帕累托平衡点，确保极少漏掉真",
     "帕累托平衡点，确保极少漏掉真"),
    # slide12 消融表：Recall 列取自阈值 0.5 的混淆矩阵，调优 F1 列来自各档最优阈值
    ("帕累托最优，召回 89.6%",
     "调优 F1 为阈值 0.97 档；0.5 档召回 89.6%"),
    # slide15 商业价值表：同一处
    ("89.6%（量化）", "89.6%（阈值 0.5 档）"),
]

# ② 子串替换（段落全文未知，仅需局部加标注）
SUB_MAP = [
    ("近九成音质差评被成功识别", "近九成音质差评被成功识别（阈值 0.5 档）"),
]

PARA_RE = re.compile(r"<a:p>.*?</a:p>", flags=re.S)
TEXT_RE = re.compile(r"(<a:t>)(.*?)(</a:t>)", flags=re.S)


def rewrite_paragraph(para: str) -> tuple[str, str | None]:
    """整段精确替换 + 段内子串替换；返回（新段落, 命中的映射键或 None）。"""
    nodes = list(TEXT_RE.finditer(para))
    if not nodes:
        return para, None
    joined = "".join(m.group(2) for m in nodes)
    target = None
    key = None
    for old, new in PARA_MAP:
        if joined == old:
            target, key = new, old
            break
    if target is None:
        target = joined
        for old, new in SUB_MAP:
            if old in target and new not in target:
                target, key = target.replace(old, new), old
    if target is None or target == joined:
        return para, key  # 已是目标态或无命中
    for idx, m in enumerate(reversed(nodes)):
        first = (idx == len(nodes) - 1)
        para = para[:m.start(2)] + (target if first else "") + para[m.end(2):]
    return para, key


def main() -> int:
    if not os.path.isfile(PPTX):
        print(f"找不到 PPT：{PPTX}")
        return 2
    if not os.path.isfile(BAK):
        shutil.copy2(PPTX, BAK)
        print(f"已备份 -> {os.path.basename(BAK)}")

    with zipfile.ZipFile(PPTX) as z:
        names = z.namelist()
        data = {n: z.read(n) for n in names}

    counts = {old: 0 for old, _ in PARA_MAP + SUB_MAP}
    slide_names = [n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)]
    for name in slide_names:
        xml = data[name].decode("utf-8")

        def fix(match: re.Match) -> str:
            para, key = rewrite_paragraph(match.group(0))
            if key is not None:
                counts[key] += 1
            return para

        new_xml = PARA_RE.sub(fix, xml)
        if new_xml != xml:
            data[name] = new_xml.encode("utf-8")
            print(f"已修改 {name}")

    missing = [old for old, n in counts.items() if n == 0]
    if missing:
        print("\n以下片段未命中，未写回（避免改错）：")
        for m in missing:
            print("  - " + m)
        return 1

    tmp = PPTX + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            z.writestr(n, data[n])
    os.replace(tmp, PPTX)
    print(f"\n已写回 -> {os.path.basename(PPTX)}")
    for old, n in counts.items():
        print(f"  命中 {n} 次：{old[:40]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
