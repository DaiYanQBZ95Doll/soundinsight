# -*- coding: utf-8 -*-
"""外部契合度门（第 28 步）：审题卡必须完整、且每个偏差都必须有处置。

判据（任一不满足即 FAIL，阻止打包）：
  ① docs/BRIEF_ALIGNMENT.md 存在；
  ② 四个必备小节都在：输出目标 / 形态要求 / 数据范围 / 交付物与截止；
  ③ 表格每行四列齐全，判定列 ∈ {满足, 部分, 不满足}——出现「待定」即 FAIL；
  ④ 判定为「部分」或「不满足」的行，处置列必须非空（不许沉默）。

设计动机（2026-10-07 复盘）：本项目建了 27 道门，全部检查**内部一致性**，
没有一道检查**是否答对了题**；结果是"答得很好，但答错了题"。
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CARD = os.path.join(HERE, "docs", "BRIEF_ALIGNMENT.md")
SECTIONS = ["输出目标", "形态要求", "数据范围", "交付物与截止"]
# 注意顺序：长判定在前——"满足" 是 "不满足" 的子串，顺序错了会把不满足判成满足
VERDICTS = ("不满足", "部分", "满足")


def main() -> int:
    bad = []
    print("## 外部契合度（审题卡）")
    if not os.path.isfile(CARD):
        print("- [FAIL] 缺少 docs/BRIEF_ALIGNMENT.md：**未审题即打包**（本次失利的直接原因）")
        return 1
    txt = open(CARD, encoding="utf-8").read()
    lines = txt.splitlines()
    # 定位各小节
    idx = {}
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            for sec in SECTIONS:
                if sec in ln and sec not in idx:
                    idx[sec] = i
    missing_sec = [s for s in SECTIONS if s not in idx]
    if missing_sec:
        bad.append(f"审题卡缺少小节：{'、'.join(missing_sec)}")

    rows_total = rows_bad = pending = unhandled = 0
    for j, (sec, i) in enumerate(sorted(idx.items(), key=lambda kv: kv[1])):
        end = next((k for k in range(i + 1, len(lines)) if lines[k].startswith("## ")),
                   len(lines))
        _block = lines[i:end]
        _hdr = next((ln for ln in _block if ln.strip().startswith("|")), "")
        if "原文要求" not in _hdr:      # 非审题表（如复审记录）不参与判定
            continue
        for ln in _block:
            if not ln.strip().startswith("|"):
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) < 3 or set("".join(cells)) <= set("-: "):
                continue
            if cells[0].startswith("原文要求"):
                continue
            rows_total += 1
            verdict_cell = cells[2] if len(cells) > 2 else ""
            verdict = next((v for v in VERDICTS if v in verdict_cell), None)
            if verdict is None:
                if "待定" in verdict_cell:
                    pending += 1
                    rows_bad += 1
                    print(f"- [FAIL] 「{cells[0][:28]}」判定为**待定**——不许进入开发/打包")
                else:
                    rows_bad += 1
                    print(f"- [FAIL] 「{cells[0][:28]}」判定列无法识别：{verdict_cell[:30]}")
                continue
            if verdict in ("部分", "不满足"):
                disp = cells[3] if len(cells) > 3 else ""
                if not disp or disp in ("—", "-", "无"):
                    unhandled += 1
                    rows_bad += 1
                    print(f"- [FAIL] 「{cells[0][:28]}」判定 **{verdict}** 但未写处置"
                          "（须写明：改产物／收窄主张并披露／明示放弃）")
    print(f"- 审查行数 {rows_total}｜待定 {pending}｜偏差未处置 {unhandled}")
    if bad:
        for b in bad:
            print(f"- [FAIL] {b}")
    if bad or rows_bad:
        print("- [FAIL] 外部契合度未通过：**先补审题卡，再打包**")
        return 1
    print("- 外部契合度通过 ✓（所有偏差均已处置或已明示）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
