# -*- coding: utf-8 -*-
"""论文表格生成器：扫描 v2/exp_*_metrics.json，输出 Markdown 表格（**禁止手抄数字**）。

产物：docs/thesis/tables/exp_results.md（含划分指纹与生成时刻，保证可追溯）
"""
from __future__ import annotations

import datetime
import glob
import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "docs", "thesis", "tables")


def main() -> int:
    os.makedirs(OUTDIR, exist_ok=True)
    sp_path = os.path.join(HERE, "v2", "thesis_split.json")
    sp = json.load(open(sp_path, encoding="utf-8"))
    sp_fp = hashlib.sha256(json.dumps(sp["stats"], sort_keys=True).encode()).hexdigest()[:16]
    st = sp["stats"]["test"]

    rows = []
    for p in sorted(glob.glob(os.path.join(HERE, "v2", "exp_*_test_metrics.json"))):
        m = json.load(open(p, encoding="utf-8"))
        t = m["thr0.5"]
        rows.append((m.get("name", os.path.basename(p)), m["n"], m["pos"],
                     t["P"], t["R"], t["F1"], m["P_ci"], m["R_ci"], m["F1_ci"],
                     m["auc_pr"], m["ece"], t["tp"], t["fp"], t["fn"]))
    rows.sort(key=lambda r: -r[5])

    md = [f"# 实验结果表（自动生成，{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}）", "",
          f"> 划分：`v2/thesis_split.json`（指纹 `{sp_fp}`）｜测试集 n={st['n']}，"
          f"正例 {st['pos_v2llm']}（{st['rate_v2llm']*100:.2f}%）｜口径：**v2-LLM 标签**", "",
          "| 方法 | n | 正例 | P | P 95%CI | R | R 95%CI | F1 | F1 95%CI | AUC-PR | ECE | TP/FP/FN |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (name, n, pos, P, R, F1, Pci, Rci, Fci, ap, ec, tp, fp, fn) in rows:
        pc = f"{Pci[0]*100:.0f}–{Pci[1]*100:.0f}"
        rc = f"{Rci[0]*100:.0f}–{Rci[1]*100:.0f}"
        fc = f"{Fci[0]*100:.0f}–{Fci[1]*100:.0f}"
        md.append(f"| {name} | {n} | {pos} | {P*100:.1f}% | {pc} | {R*100:.1f}% | {rc} | "
                  f"**{F1*100:.1f}%** | {fc} | {ap:.3f} | {ec:.3f} | {tp}/{fp}/{fn} |")
    md += ["", "> 口径说明：所有数字来自 `thesis_eval.py` 对冻结划分的计算；"
               "配对比较用 `--mcnemar`（同一测试集）。", ""]
    out = os.path.join(OUTDIR, "exp_results.md")
    open(out, "w", encoding="utf-8", newline="\n").write("\n".join(md))
    print(f"  [写出] {os.path.relpath(out, HERE)}（{len(rows)} 行）")
    print("\n".join(md[4:4 + min(6, len(rows))]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
