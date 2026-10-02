# -*- coding: utf-8 -*-
"""检查：对外材料里「耳机音质差评」类称谓的**一致性**（红队 Qwen 指出的空白维度）。

由来：门槛链会查数字成对、项数一致，但**不会查"正文称谓是否与附录改述一致"**。
2026-10-02 的实况是：附录 C 已改述为「声学相关抱怨集」（并披露真实场景 F1 0.427），
而正文标题、一句话定义、商业价值表仍在卖「音质差评识别 F1 0.7220」——
同一份交付物内两套口径并存，正是本项目一直在防的那类分裂。

规则：在中英文材料中，出现「音质差评」且**指向标签集/指标/正例**的行，必须带限定词
（声学相关抱怨／声学抱怨／分布内／人工口径／附录 C／真实场景 之一）；
**产品名**（如「蓝牙耳机音质差评智能归因系统」）与**历史材料**（competition_v1–v4、PPT dump 等）豁免。

用法：python check_scope_wording.py    （0=通过，1=存在未限定的旧称谓）
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = [
    "build_finals_content.py", "build_finals_appendix.py",
    "docs/N1_narrative_mainline.md", "docs/N2_narrative_final.md",
    "docs/N5_qna_factbase.md", "docs/N6_review_risk_list.md",
    "docs/roadshow_slides_corrections.md",
]
QUALIFIERS = ("声学相关抱怨", "声学抱怨", "分布内", "人工口径", "附录 C", "真实场景",
              "人工真值", "口径")
# 产品名与历史称谓豁免
NAME_OK = re.compile(r"蓝牙耳机音质差评智能归因系统|音质差评智能归因系统")
RISK = re.compile(r"(正例|标签|指标|数据集|语料|测试集|识别)[^\n]{0,26}(音质差评)|"
                  r"(音质差评)[^\n]{0,26}(正例|标签|指标|数据集|语料|测试集|识别)")


def main() -> int:
    bad = []
    for rel in TARGETS:
        p = os.path.join(HERE, rel)
        if not os.path.isfile(p):
            continue
        for i, ln in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
            if "音质差评" not in ln or NAME_OK.search(ln):
                continue
            if not RISK.search(ln):
                continue
            if any(q in ln for q in QUALIFIERS):
                continue
            # 否定句豁免：说「并非/不是/而非 X」时，X 是**被否定的对象**，不构成未限定称谓
            if any(n in ln for n in ("并非", "不是", "而非", "非严格", "不属于")):
                continue
            bad.append(f"{rel}:{i} {ln.strip()[:90]}")
    print("## 对外称谓一致性（正文 vs 附录改述）")
    if bad:
        for b in bad:
            print(f"- [FAIL] 未限定的旧称谓：{b}")
        print("- 修法：改述为「声学相关抱怨（含耳机音质）」或补限定词"
              "（分布内／人工口径／附录 C 第 8–10 条）")
    else:
        print(f"- [PASS] 未发现未限定的旧称谓（扫描 {len(TARGETS)} 个对外材料）")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
