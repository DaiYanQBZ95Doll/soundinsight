# -*- coding: utf-8 -*-
"""重测一致性计分（intra-rater reliability）：

  · 输入：docs/gold_set/answer_sheet_retest.md（决策方盲判）＋ v2/retest_ids.json（原判定）
  · 产出：一致率、Cohen's κ（自身前后）、混淆矩阵、按域（耳机/音箱）与按原判定的分解、
          不一致条目清单（供定性分析）；写 v2/retest_scored.json
  · 编码 2（无法判断）单独统计，不进入 κ 的主计算（另报含 2 的版本）
"""
from __future__ import annotations

import collections
import importlib.util
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rio", os.path.join(HERE, "rulings_io.py"))
rio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rio)

CARD = os.path.join(HERE, "docs", "gold_set", "answer_sheet_retest.md")
IDS = os.path.join(HERE, "v2", "retest_ids.json")
OUT = os.path.join(HERE, "v2", "retest_scored.json")


def kappa(pairs):
    """pairs: [(a, b)]；返回 (po, pe, kappa)。"""
    n = len(pairs)
    if n == 0:
        return 0.0, 0.0, 0.0
    cats = sorted({x for p in pairs for x in p})
    po = sum(1 for a, b in pairs if a == b) / n
    pe = 0.0
    for c in cats:
        pa = sum(1 for a, _b in pairs if a == c) / n
        pb = sum(1 for _a, b in pairs if b == c) / n
        pe += pa * pb
    k = (po - pe) / (1 - pe) if pe != 1 else 0.0
    return po, pe, k


def main(card=CARD) -> int:
    if not os.path.isfile(IDS):
        print("  [FAIL] 缺少 v2/retest_ids.json")
        return 1
    meta = json.load(open(IDS, encoding="utf-8"))
    got, amb = rio.read_judgements(card)
    print(f"  已判 {len(got)}/{meta['n']}｜歧义 {len(amb)}")
    if len(got) < meta["n"]:
        miss = [it["rid"] for it in meta["items"] if it["rid"] not in got]
        print(f"  未填：{miss[:8]}{' …' if len(miss) > 8 else ''}")
    rows = [(it, got[it["rid"]]) for it in meta["items"] if it["rid"] in got]
    if not rows:
        print("  [FAIL] 尚无任何判定")
        return 1
    pairs = [(it["original_verdict"], v) for it, v in rows if v in ("0", "1")]
    pairs_all = [(it["original_verdict"], "0" if v not in ("0", "1") else v) for it, v in rows]
    po, pe, k = kappa(pairs)
    po2, pe2, k2 = kappa(pairs_all)
    print(f"\n[重测一致性] n={len(pairs)}｜一致率 {po*100:.1f}%｜期望一致 {pe*100:.1f}%"
          f"｜**Cohen's κ = {k:.3f}**")
    if len(pairs_all) != len(pairs):
        print(f"  （含「无法判断」按 0 计的敏感性分析：n={len(pairs_all)}｜"
              f"一致率 {po2*100:.1f}%｜κ = {k2:.3f}）")
    cm = collections.Counter(pairs)
    print("\n[混淆矩阵] 行=原判定，列=重测")
    for a in ("1", "0"):
        print(f"   原判 {a}：重测 1 = {cm[(a, '1')]:3d}｜重测 0 = {cm[(a, '0')]:3d}"
              f" → 一致率 {cm[(a, a)]/max(1, sum(v for (x, _y), v in cm.items() if x == a))*100:.0f}%")
    for dom in sorted({it["domain"] for it, _v in rows}):
        pp = [(it["original_verdict"], v) for it, v in rows
              if it["domain"] == dom and v in ("0", "1")]
        if pp:
            _p, _e, kk = kappa(pp)
            print(f"   [{dom}] n={len(pp)}｜一致率 {_p*100:.1f}%｜κ = {kk:.3f}")
    dis = [(it, v) for it, v in rows if v in ("0", "1") and v != it["original_verdict"]]
    print(f"\n[不一致条目] {len(dis)} 条（建议逐条定性分析：判据漂移 or 首轮误判）")
    for it, v in dis[:10]:
        print(f"   {it['rid']}｜原判 {it['original_verdict']} → 重测 {v}｜{it['domain']}"
              f"｜来源 {it['source_id']}")
    json.dump({"n": len(rows), "n_kappa": len(pairs), "agreement": round(po, 4),
               "kappa": round(k, 4), "agreement_sens": round(po2, 4), "kappa_sens": round(k2, 4),
               "confusion": {f"{a}->{b}": c for (a, b), c in cm.items()},
               "disagreements": [{"rid": it["rid"], "original": it["original_verdict"],
                                  "retest": v, "domain": it["domain"],
                                  "source": it["source"], "source_id": it["source_id"]}
                                 for it, v in dis],
               "note": "intra-rater reliability；单标注者条件下替代标注者间一致性"},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n[写出] {os.path.relpath(OUT, HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
