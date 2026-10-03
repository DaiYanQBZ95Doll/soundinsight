# -*- coding: utf-8 -*-
"""S6 计分：独立检验 P(真阳｜扩词表命中)（**预注册口径**）。

纪律（写在预注册里，此处照做）：
  · 只报 P 与**两种区间**（Wilson 与 Clopper-Pearson），可回收量以**区间**给出；
  · 不做方向性外推（不得把 P 说成"召回提升幅度"）；
  · 词表哈希须与预注册一致，否则拒算（迭代即作废）。

用法：python score_vocab_test.py
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rio", os.path.join(HERE, "rulings_io.py"))
rio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rio)

pre = json.load(open(os.path.join(HERE, "v2", "s6_preregistration.json"), encoding="utf-8"))
h = hashlib.sha256(open(os.path.join(HERE, "audio_gate.py"), "rb").read()).hexdigest()
if h != pre["gate_sha256"]:
    print(f"[拒算] 词表已变更（现 {h[:16]}… ≠ 预注册 {pre['gate_sha256'][:16]}…）——"
          f"按预注册「迭代即作废」，请重新抽样后重验。")
    sys.exit(2)
print(f"词表哈希一致 ✓（{h[:16]}…）")

got, ambig = rio.read_judgements(os.path.join(HERE, "docs/gold_set/answer_sheet_vocab_test.md"))
rows = list(csv.DictReader(open(os.path.join(HERE, "docs/gold_set/vocab_test.csv"),
                                encoding="utf-8-sig", errors="replace")))
n_all, n_ans = len(rows), len(got)
print(f"答题卡：{n_ans}/{n_all} 条已判｜歧义 {len(ambig)}")
partial = "--allow-partial" in sys.argv
if n_ans < n_all:
    unf = [r["编号"] for r in rows if r["编号"] not in got]
    short = (n_all - n_ans) / n_all
    print(f"  未填 {len(unf)} 条（{unf[:6]}）")
    if not partial or short > 0.05:
        print("  → 拒算：预注册 n=100；缺口超过 5% 或未加 --allow-partial。")
        sys.exit(1)
    print(f"  ⚠️ **偏离预注册**：按已判 {n_ans} 条计分（缺口 {short*100:.0f}% ≤5%），"
          f"此项偏离必须在引用时披露；补齐后可复算。")
rows = [r for r in rows if r["编号"] in got]


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


def clopper_pearson(k, n, alpha=0.05):
    from scipy.stats import beta
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return (lo, hi)


y = [1 if got[r["编号"]] == "1" else 0 for r in rows]
und = sum(1 for r in rows if got[r["编号"]] == "?")
k, n = sum(y), len(y)
lo_w, hi_w = wilson(k, n)
try:
    lo_c, hi_c = clopper_pearson(k, n)
    cp = f"{lo_c*100:.1f}%–{hi_c*100:.1f}%"
except ImportError:
    cp = "（缺 scipy，未算 CP 区间）"
print(f"\n**[主结果] P(真阳｜扩词表命中) = {k}/{n} = {k/n*100:.1f}%**")
print(f"  Wilson 95% CI：{lo_w*100:.1f}%–{hi_w*100:.1f}%｜Clopper-Pearson：{cp}")
print(f"  「无法判断」{und} 条（按口径 A 排除时：{k}/{n-und}）")
frame = pre["frame_after_exclusion"]
print(f"\n可回收量（抽样框 {frame} 条 × P）：**{frame*k/n:.0f} 条**"
      f"｜区间（由 P 的 CI 传导）：{frame*lo_w:.0f}–{frame*hi_w:.0f} 条")
print("  ⚠️ 该区间为**抽样不确定性**传导；不得据此主张召回提升（须由重训后实测给出）。")

out = {"gate_sha256": h, "n": n, "true_positives": k, "unclear": und,
       "p": round(k / n, 4), "wilson": [round(lo_w, 4), round(hi_w, 4)],
       "frame": frame, "recoverable": round(frame * k / n, 1),
       "recoverable_ci": [round(frame * lo_w, 1), round(frame * hi_w, 1)],
       "reading_limit": "只报 P 与区间；不主张召回提升"}
json.dump(out, open(os.path.join(HERE, "v2", "vocab_test_scored.json"), "w",
                    encoding="utf-8"), ensure_ascii=False, indent=2)
print("\n[写出] v2/vocab_test_scored.json")
