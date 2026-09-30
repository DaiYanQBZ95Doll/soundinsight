# -*- coding: utf-8 -*-
"""W4 复核结果的分层外推估计（凭证到位、复核跑完后**一条命令出结论**）。

输入：
- `v2/w4_strata.json`：分层信息（各组候选数）
- `v2/w4_review.jsonl`：逐条复核结果（`sound_negative` 0/1）

输出（控制台 + `v2/w4_estimate.json` + `docs/w4_mining_estimate.md`）：
- 各层产出率 p_h 与 Wilson 95% CI；
- **分层外推**：整个候选池（12,744 条 4–5★ 音质相关候选）中"真音质差评"的点估计与 95% CI；
- 与现有正例集（1,280 条）的关系：若全部复核，正例规模预计达到多少；
- **成本**：按实测 LLM 复核单价（0.03 美元/1,000 条）估算增量成本。

统计口径：分层随机抽样（按星级×主关键词分层，每组等量抽取），
总体估计 N̂ = Σ_h N_h·p_h；方差 Var = Σ_h N_h²·p_h(1−p_h)/(n_h−1)（有限总体不做校正，属保守）。
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v2")
REVIEW = os.path.join(OUT, "w4_review.jsonl")
STRATA = os.path.join(OUT, "w4_strata.json")
CANDS = os.path.join(OUT, "w4_candidates.csv")
COST_PER_1K = 0.03          # 美元，项目实测口径（llm_baseline.md）


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - r) / d), min(1.0, (c + r) / d)


def main() -> int:
    if not os.path.isfile(REVIEW):
        print("[等待] 尚无 v2/w4_review.jsonl —— 凭证到位后执行："
              "python v2_w4_mine.py --review --limit 300")
        return 0
    # 分层总体
    strata = json.load(open(STRATA, encoding="utf-8")) if os.path.isfile(STRATA) else {}
    groups = strata.get("groups", {})
    # 候选的层归属（星级×主关键词）
    layer_of, pop = {}, {}
    if os.path.isfile(CANDS):
        for r in csv.DictReader(open(CANDS, encoding="utf-8", errors="replace")):
            key = f"{r['rating']}★/{r['hits'].split(',')[0]}"
            layer_of[int(r["row_index"])] = key
            pop[key] = pop.get(key, 0) + 1
    # 复核结果
    k, n = {}, {}
    total_ok = 0
    for line in open(REVIEW, encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "sound_negative" not in rec:
            continue
        key = layer_of.get(rec.get("row_index"), "未分层")
        n[key] = n.get(key, 0) + 1
        k[key] = k.get(key, 0) + int(rec["sound_negative"])
        total_ok += 1
    if not n:
        print("[等待] 复核文件存在但无有效结果（可能全部解析失败）")
        return 0

    est = var = 0.0
    rows = []
    for key in sorted(n):
        p = k[key] / n[key]
        lo, hi = wilson(k[key], n[key])
        N_h = pop.get(key, 0)
        est += N_h * p
        if n[key] > 1:
            var += (N_h ** 2) * p * (1 - p) / (n[key] - 1)
        rows.append({"层": key, "总体 N_h": N_h, "样本 n_h": n[key], "命中 k_h": k[key],
                     "产出率 p_h": round(p, 4), "Wilson 95%": [round(lo, 4), round(hi, 4)],
                     "外推命中": round(N_h * p, 1)})
    se = math.sqrt(var)
    n_pop = sum(pop.values())
    print(f"复核样本 {total_ok} 条，覆盖 {len(n)} 层；候选池 {n_pop} 条")
    print(f"{'层':<18}{'N_h':>7}{'n_h':>6}{'k_h':>6}{'p_h':>9}{'外推':>9}")
    for r in rows:
        print(f"{r['层']:<18}{r['总体 N_h']:>7}{r['样本 n_h']:>6}{r['命中 k_h']:>6}"
              f"{r['产出率 p_h']:>9.3f}{r['外推命中']:>9.1f}")
    print(f"\n[分层外推] 候选池中的音质差评（隐藏正例）≈ **{est:,.0f}** 条"
          f"（95% CI {max(0, est-1.96*se):,.0f} – {est+1.96*se:,.0f}）")
    print(f"[规模含义] 现有正例 1,280 + 预计新增 {est:,.0f} ≈ **{1280+est:,.0f}** 条"
          f"（若全量复核并采纳）")
    print(f"[成本] 全量复核 {n_pop:,} 条 ≈ **{n_pop*COST_PER_1K/1000:.2f} 美元**"
          f"（按实测 0.03 美元/1,000 条）")

    payload = {"reviewed": total_ok, "candidates": n_pop, "per_stratum": rows,
               "hidden_positives_est": round(est, 1),
               "ci95": [round(max(0, est - 1.96 * se), 1), round(est + 1.96 * se, 1)],
               "projected_total_positives": round(1280 + est, 1),
               "full_review_cost_usd": round(n_pop * COST_PER_1K / 1000, 2),
               "note": "分层随机抽样外推；方差按各层二项方差独立求和（保守，未做有限总体校正）"}
    json.dump(payload, open(os.path.join(OUT, "w4_estimate.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=2)

    md = ["# W4 四五星开采：分层外推估计", "",
          f"> 复核样本 **{total_ok}** 条／候选池 **{n_pop:,}** 条（4–5★ 音质相关候选）。",
          "> 方法：按（星级×主关键词）分层等量抽样 → 分层外推（各层方差独立求和，保守）。", "",
          "| 层 | 总体 N_h | 样本 n_h | 命中 k_h | 产出率 p_h | 外推命中 |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['层']} | {r['总体 N_h']} | {r['样本 n_h']} | {r['命中 k_h']} | "
                  f"{r['产出率 p_h']} | {r['外推命中']} |")
    md += ["", "## 结论", "",
           f"- **候选池中的隐藏音质差评 ≈ {est:,.0f} 条**"
           f"（95% CI {max(0, est-1.96*se):,.0f} – {est+1.96*se:,.0f}）；",
           f"- 与现有 1,280 条正例合并后规模 ≈ **{1280+est:,.0f}** 条（若全量复核并采纳）；",
           f"- **全量复核成本 ≈ {n_pop*COST_PER_1K/1000:.2f} 美元**（实测 0.03 美元/1,000 条）；",
           "- 未复核比例已在 `v2/w4_strata.json` 记录（97.70%），本估计即用于把抽样结论外推到全池。"]
    open(os.path.join(HERE, "docs", "w4_mining_estimate.md"), "w",
         encoding="utf-8", newline="\n").write("\n".join(md) + "\n")
    print("[写出] v2/w4_estimate.json、docs/w4_mining_estimate.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
