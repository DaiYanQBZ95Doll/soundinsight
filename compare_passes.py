# -*- coding: utf-8 -*-
"""比较两份判定来源：一致率、κ、分歧清单。

典型用途：
  · 我方卡（主表）vs Kimi 卡（**同一批 300 条的第二遍判定**）→ 检验判定稳定性；
  · 主卡 vs 偏向探针卡（只看原文）→ 量化执行方材料的锚定影响；
  · 三方席位文件互比 → 转写对账。

用法：
    python compare_passes.py --a csv --b docs/gold_set/human_rulings_dsh2.md
    python compare_passes.py --a csv --b docs/gold_set/answer_sheet_decision.md --title "主表 vs Kimi卡"
"""
from __future__ import annotations

import argparse
import csv
import os
import re

import rulings_io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GDIR = os.path.join(HERE, "docs", "gold_set")
COL = "人工判定(1=音质差评/0=不是)"


def _slot(line: str):
    m = re.search(r"`([^`]*)`", line)
    content = m.group(1) if m else line
    digs = sorted({c for c in content if c in "012"})
    if len(digs) > 1:
        return "AMBIG"
    if not digs:
        return None
    return "?" if digs[0] == "2" else digs[0]


def load(src: str) -> dict:
    """读判定来源：'csv'（主表）、CSV/TSV 路径、或 Markdown 卡（块式＋内联＋表格）。"""
    out = {}
    path = os.path.join(GDIR, "assisted_worksheet.csv") if src == "csv" else src
    if not os.path.isfile(path):
        return out
    if path.lower().endswith((".csv", ".tsv")):
        sep = "\t" if path.lower().endswith(".tsv") else ","
        enc = "utf-8-sig"
        for r in csv.DictReader(open(path, encoding=enc, errors="replace"), delimiter=sep):
            v = (r.get(COL) or r.get("人工判定") or "").strip()
            i = r.get("编号")
            if i and v in ("0", "1", "?"):
                out[i] = v
        return out
    # 非表格来源交给共享模块（R32）
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
    ap.add_argument("--a", default="csv")
    ap.add_argument("--b", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--list", type=int, default=15, help="最多列出多少条分歧")
    args = ap.parse_args()
    A, B = load(args.a), load(args.b)
    common = sorted(set(A) & set(B))
    print(f"比较：A={args.a}（{len(A)} 条）｜B={args.b}（{len(B)} 条）｜共同 {len(common)} 条"
          + (f"｜{args.title}" if args.title else ""))
    if not common:
        print("  无共同条目——若 B 是新样本（如 S4），它应走接收流程进入主表，而不是比较。")
        return 0
    pairs = [(A[i], B[i]) for i in common]
    agree = sum(1 for a, b in pairs if a == b) / len(pairs) * 100
    print(f"一致率 **{agree:.1f}%**｜κ **{kappa(pairs):.3f}**")
    diff = [(i, A[i], B[i]) for i in common if A[i] != B[i]]
    print(f"分歧 {len(diff)} 条" + ("：" if diff else " ✓"))
    for i, a, b in diff[:args.list]:
        print(f"  {i}: A={a} → B={b}")
    if diff:
        to1 = sum(1 for _, a, b in diff if b == "1")
        to0 = sum(1 for _, a, b in diff if b == "0")
        print(f"方向：B 相对 A 变为『是』{to1} 条｜变为『不是』{to0} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
