# -*- coding: utf-8 -*-
"""对比"主卡判定"与"偏向探针（只给原文）判定"，量化翻译/解析带来的锚定影响。

用法：
    python score_bias_probe.py                 # 主卡取 assisted_worksheet.csv，探针取 bias_probe_sheet.md
    python score_bias_probe.py --probe <路径>  # 或直接指定含内联判定的文件
输出：逐条差异表 + 一致率 + 方向性（在"我给了解析"条件下更偏向"是"还是"不是"）。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re

import rulings_io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GDIR = os.path.join(HERE, "docs", "gold_set")
COL = "人工判定(1=音质差评/0=不是)"


def read_main() -> dict:
    p = os.path.join(GDIR, "assisted_worksheet.csv")
    out = {}
    for r in csv.DictReader(open(p, encoding="utf-8-sig", errors="replace")):
        v = (r.get(COL) or "").strip()
        if v in ("0", "1", "?"):
            out[r["编号"]] = v
    return out


def read_inline(path: str) -> dict:
    """委托给共享实现（R32）。"""
    got, _ambig = rulings_io.read_judgements(path)
    return got


def kappa(pairs):
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(1 for a, b in pairs if a == b) / n
    a1 = sum(1 for a, _ in pairs if a == "1") / n
    b1 = sum(1 for _, b in pairs if b == "1") / n
    pe = a1 * b1 + (1 - a1) * (1 - b1)
    return (po - pe) / (1 - pe) if pe != 1 else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default=os.path.join(GDIR, "bias_probe_sheet.md"))
    args = ap.parse_args()
    ids = set(json.load(open(os.path.join(HERE, "v2", "bias_probe_ids.json"),
                             encoding="utf-8"))["ids"])
    main_v, probe_v = read_main(), read_inline(args.probe)
    both = [i for i in sorted(ids) if i in main_v and i in probe_v]
    if not both:
        print("[等待] 探针卡尚无已填判定（或主卡尚无对应条目）")
        print(f"  探针卡：{os.path.relpath(args.probe, HERE)}｜已填 {len(probe_v)} 条"
              f"｜主卡已填 {len(main_v)} 条｜交集 {len(both)} 条")
        return 0
    pairs = [(probe_v[i], main_v[i]) for i in both]      # (只看原文, 含我的翻译与解析)
    agree = sum(1 for a, b in pairs if a == b) / len(pairs) * 100
    print(f"对比 {len(pairs)} 条｜一致 {agree:.1f}%｜κ {kappa(pairs):.3f}")
    print("\n逐条差异（仅列不一致；A=只看原文，B=含翻译与解析）：")
    diff = 0
    for i in both:
        a, b = probe_v[i], main_v[i]
        if a != b:
            diff += 1
            print(f"  {i}: A={a} → B={b}")
    print(f"\n不一致 {diff} 条")
    to_yes = sum(1 for i in both if probe_v[i] != "1" and main_v[i] == "1")
    to_no = sum(1 for i in both if probe_v[i] != "0" and main_v[i] == "0")
    print(f"方向性：因材料而变为「是」{to_yes} 条｜变为「不是」{to_no} 条")
    print("\n解读：一致率低 → 我提供的翻译/解析对判读影响大（锚定强）；"
          "方向性偏正 → 材料倾向于推高「是」的比例。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
