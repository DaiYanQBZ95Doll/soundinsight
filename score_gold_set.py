# -*- coding: utf-8 -*-
"""评分：人工金标 vs LLM 判定的一致性，并重算受影响的对外数字。

用法：python score_gold_set.py [--self-test]
  · 正常：读 `docs/gold_set/worksheet.csv`（人工已填「人工判定」列）+ `v2/gold_set_key.json`
  · --self-test：用合成标签跑一遍（验证脚本本身），**不写任何结论文件**

产出（正常模式）：
  `docs/gold_set/agreement_report.md`、`v2/gold_set_agreement.json`
  含：逐层一致率、总体 Cohen's κ、以及在**人工口径**下重算的
  ① 闸门外真阳性率（校准 1.33%）；② 四五星池率（校准 1.0%/3.1%）；③ 现有标签的准确率。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GDIR = os.path.join(HERE, "docs", "gold_set")
KEY = os.path.join(HERE, "v2", "gold_set_key.json")
SHEET = os.path.join(GDIR, "worksheet.csv")          # 盲评版（原始）
SHEET_ASSISTED = os.path.join(GDIR, "assisted_worksheet.csv")  # 辅助版（含执行方中性翻译与解析）
OUT_MD = os.path.join(GDIR, "agreement_report.md")
OUT_JSON = os.path.join(HERE, "v2", "gold_set_agreement.json")

STRATA = {"S1": "闸门外随机（校准 1.33% 一说）",
          "S2": "四五星候选池（校准 1.0%／3.1%）",
          "S3": "现有已标注集（校准标签质量本身）"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - r) / d), min(1.0, (c + r) / d)


def kappa(pairs: list[tuple[int, int]]) -> float:
    """Cohen's κ（二分类）。"""
    n = len(pairs)
    if n == 0:
        return float("nan")
    po = sum(1 for a, b in pairs if a == b) / n
    pa1 = sum(1 for a, _ in pairs if a == 1) / n
    pb1 = sum(1 for _, b in pairs if b == 1) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    return (po - pe) / (1 - pe) if pe != 1 else float("nan")


def read_sheet(path: str) -> dict[str, int]:
    """读人工判定；`?`（无法判断）**记为 -1**，由双口径统计分别处理。"""
    labels = {}
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            v = (r.get("人工判定(1=音质差评/0=不是)") or "").strip()
            if v in ("0", "1"):
                labels[r["编号"].strip()] = int(v)
            elif v == "?":
                labels[r["编号"].strip()] = -1
    return labels


def score(human: dict[str, int], items: list[dict], quiet: bool = False) -> dict:
    per = {}
    pairs_all = []
    for tag in STRATA:
        rows = [it for it in items if it["stratum"] == tag]
        pairs, n_pos, n_unknown = [], 0, 0
        for it in rows:
            h = human.get(it["id"])
            llm = it.get("llm_label")
            if h is None:
                continue
            if h == -1:                     # 口径 A：排除；口径 B：记为负
                n_unknown += 1
                if str(llm) in ("0", "1"):
                    pairs.append((0, int(llm)))
                continue
            n_pos += h
            if str(llm) in ("0", "1"):
                pairs.append((h, int(llm)))
        # 口径 A（排除 ?）与口径 B（? 记为负）
        kA, nA = n_pos, n_pos + sum(1 for a, _ in pairs if a == 0) - 0
        kB, nB = n_pos, (len(pairs) if pairs else n_pos) + n_unknown
        k, n = n_pos, sum(1 for a, _ in pairs if True)      # 兼容旧字段
        lo, hi = wilson(kA, max(1, len([p for p in pairs if p[0] != 0 or True]) - n_unknown))
        agree = (sum(1 for a, b in pairs if a == b) / len(pairs) * 100) if pairs else float("nan")
        # 口径 A（排除 "?"）：只统计明确判定条目的一致率与 κ
        pairsA = [(human[it["id"]], int(it["llm_label"])) for it in rows
                  if human.get(it["id"]) in (0, 1) and str(it.get("llm_label")) in ("0", "1")]
        agreeA = (sum(1 for a, b in pairsA if a == b) / len(pairsA) * 100) if pairsA else float("nan")
        nA_eff = n_pos + (len(pairs) - n_pos - n_unknown)      # 口径 A 分母 = 明确判定数
        loA, hiA = wilson(n_pos, max(1, nA_eff))
        loB, hiB = wilson(n_pos, max(1, nA_eff + n_unknown))
        per[tag] = {"labeled": len(rows), "human_labeled": n + n_unknown, "human_positive": n_pos,
                    "human_unknown": n_unknown,
                    "human_rate": round(n_pos / nA_eff, 4) if nA_eff else None,
                    "wilson95": [round(loA, 4), round(hiA, 4)],
                    "human_rate_unknown_as_neg": round(n_pos / (nA_eff + n_unknown), 4)
                    if (nA_eff + n_unknown) else None,
                    "wilson95_unknown_as_neg": [round(loB, 4), round(hiB, 4)],
                    "llm_agreement_pct": round(agree, 1) if pairs else None,
                    "llm_agreement_pct_excl_unknown": round(agreeA, 1) if pairsA else None,
                    "kappa": round(kappa(pairs), 3) if pairs else None,
                    "kappa_excl_unknown": round(kappa(pairsA), 3) if pairsA else None,
                    "desc": STRATA[tag]}
        pairs_all += pairs
    pairsA_all = [(a, b) for a, b in pairs_all if a in (0, 1) and not (a == 0 and b == 0 and False)]
    # 口径 A 的总体：仅由各层 "排除 ?" 集合构成
    pairsA_all = []
    for tag in STRATA:
        rows = [it for it in items if it["stratum"] == tag]
        pairsA_all += [(human[it["id"]], int(it["llm_label"])) for it in rows
                       if human.get(it["id"]) in (0, 1) and str(it.get("llm_label")) in ("0", "1")]
    overall = {"pairs": len(pairs_all),
               "agreement_pct": round(sum(1 for a, b in pairs_all if a == b) / len(pairs_all) * 100, 1)
               if pairs_all else None,
               "kappa": round(kappa(pairs_all), 3) if pairs_all else None,
               "agreement_pct_excl_unknown": round(
                   sum(1 for a, b in pairsA_all if a == b) / len(pairsA_all) * 100, 1)
               if pairsA_all else None,
               "kappa_excl_unknown": round(kappa(pairsA_all), 3) if pairsA_all else None,
               "pairs_excl_unknown": len(pairsA_all)}
    if not quiet:
        print(f"总体：口径A（排除?）可比对 {overall['pairs_excl_unknown']} 条｜"
              f"一致率 {overall['agreement_pct_excl_unknown']}%｜κ {overall['kappa_excl_unknown']}"
              f"　｜　口径B（?记为负）可比对 {overall['pairs']} 条｜"
              f"一致率 {overall['agreement_pct']}%｜κ {overall['kappa']}")
        for tag, d in per.items():
            print(f"  [{tag}] {d['desc']}：人工标注 {d['human_labeled']} 条｜"
                  f"人工判正 {d['human_positive']}（{d['human_rate']}）｜"
                  f"与 LLM 一致 {d['llm_agreement_pct']}%｜κ {d['kappa']}")
    return {"per_stratum": per, "overall": overall}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--sheet", choices=("blind", "assisted"), default="assisted",
                    help="blind=盲评表；assisted=含中性翻译与解析的辅助表（默认）")
    args = ap.parse_args()
    if not os.path.isfile(KEY):
        print("[等待] 缺少 v2/gold_set_key.json —— 先跑 python make_gold_set.py")
        return 0
    items = json.load(open(KEY, encoding="utf-8"))["items"]

    if args.self_test:
        import random
        rng = random.Random(7)
        human = {}
        for it in items:
            truth = 1 if rng.random() < 0.05 else 0
            # 模拟"人工与 LLM 约 85% 一致"
            human[it["id"]] = truth if rng.random() < 0.85 else 1 - truth
        res = score(human, items, quiet=False)
        print("\n[self-test] 合成数据跑通，未写出任何结论文件")
        return 0

    sheet = SHEET if args.sheet == "blind" else SHEET_ASSISTED
    if not os.path.isfile(sheet):
        print(f"[等待] 缺少 {os.path.relpath(sheet, HERE)} —— 先跑 make_gold_set.py"
              "（辅助版还需 make_gold_set_notes.py）")
        return 0
    human = read_sheet(sheet)
    if not human:
        n = len(items)
        print(f"[等待人工填写] 工作表 {n} 条，已填 0 条。")
        print(f"  填写位置：{os.path.relpath(sheet, HERE)} 的「人工判定」列"
              "（Excel 可直接打开；判为是填 1，不是填 0，无法判断产品填 ?）")
        print(f"  预计耗时 {n*20/60:.0f}–{n*35/60:.0f} 分钟；填毕后重跑本脚本即出结论。")
        return 0
    res = score(human, items)
    json.dump(res, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    lines = ["# 人工金标 vs LLM 判定：一致性与重算", "",
             f"> 已填 {len(human)} 条｜**口径 A（排除「无法判断」）**：可比对 "
             f"{res['overall']['pairs_excl_unknown']} 条、一致率 "
             f"**{res['overall']['agreement_pct_excl_unknown']}%**、κ "
             f"**{res['overall']['kappa_excl_unknown']}**｜"
             f"**口径 B（「无法判断」记为负）**：可比对 {res['overall']['pairs']} 条、一致率 "
             f"**{res['overall']['agreement_pct']}%**、κ **{res['overall']['kappa']}**", "",
             "| 层 | 说明 | 人工标注 | 人工判正 | 无法判断 | **口径A：排除 ?（95% CI）** | "
             "**口径B：? 记为负（95% CI）** | 与 LLM 一致率 | κ |",
             "|---|---|---|---|---|---|---|---|---|"]
    for tag, d in res["per_stratum"].items():
        lines.append(f"| {tag} | {d['desc']} | {d['human_labeled']} | {d['human_positive']} | "
                     f"{d.get('human_unknown', 0)} | "
                     f"{d['human_rate']}（{d['wilson95'][0]}–{d['wilson95'][1]}） | "
                     f"{d.get('human_rate_unknown_as_neg')}"
                     f"（{d.get('wilson95_unknown_as_neg', ['—', '—'])[0]}–"
                     f"{d.get('wilson95_unknown_as_neg', ['—', '—'])[1]}） | "
                     f"{d['llm_agreement_pct_excl_unknown']}%（A）／{d['llm_agreement_pct']}%（B） | "
                     f"{d['kappa_excl_unknown']}（A）／{d['kappa']}（B） |")
    lines += ["", "## 读法", "",
              "- **S1** 的人工率即「闸门外真阳性率」的**校准值**——用它替换/并列 1.33%；",
              "- **S3** 的一致率与 κ 直接回答「现有标签质量如何」，是全部指标可信度的天花板；",
              "- κ 参考：<0.2 差／0.2–0.4 一般／0.4–0.6 中等／0.6–0.8 良好／>0.8 极好。",
              "",
              "## 两个口径为何并列（决策方 2026-10-02 裁定）", "",
              "- **口径 A（排除「无法判断」）**：只统计明确判定的条目——反映「能判的那些里有多少是」；",
              "- **口径 B（「无法判断」记为负）**：把所有条目都计入分母——反映「面对全部文本时的下界」；",
              "- 两者差 = 「无法判断」的比例。两遍判定之间的摆动主要来自这些条目的归类，",
              "  故**固定并公开该政策**比再判一遍更能消减歧义。"]
    open(OUT_MD, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(f"[写出] {os.path.relpath(OUT_MD, HERE)}、v2/gold_set_agreement.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
