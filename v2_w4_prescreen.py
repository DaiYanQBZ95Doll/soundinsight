# -*- coding: utf-8 -*-
"""W4 预筛估计（**无需 LLM 凭证**）：用本地二分类模型对四五星候选池做分层外推。

定位（务必如实标注）：
- 这是**代理口径**，不是 LLM 复核结论。模型在正例上 P≈77%／R≈68%（v2 调优档），
  因此"模型判为音质差评"既不等于"真为音质差评"（含误报），也会漏掉一部分（含漏报）。
- 价值：① 在凭证到位前给出**量级与分层结构**；② 与后续 LLM 复核结果对照，可量化"模型与 LLM 的一致性"。

口径：模型 = v2 候选（`v2/model_maxlen256`），阈值 = `v2/threshold.json` 的调优档（0.6）；
      分层 = 与 `v2/w4_strata.json` 相同的（星级×主关键词）分组；外推 = 分层比率 × 各层总体量。

输出：控制台 + `v2/w4_prescreen.json` + `docs/w4_prescreen_estimate.md`
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

import numpy as np
import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_w1_longtext import predict  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v2")
CANDS = os.path.join(OUT, "w4_candidates.csv")
SAMPLE = os.path.join(OUT, "w4_sample.csv")
THR_JSON = os.path.join(OUT, "threshold.json")
MODEL = os.path.join(OUT, "model_maxlen256")
MAX_LEN = 256


def read_csv_rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8", errors="replace")))


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - r) / d), min(1.0, (c + r) / d)


def main() -> int:
    thr = json.load(open(THR_JSON, encoding="utf-8"))["tuned"] if os.path.isfile(THR_JSON) else 0.6
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = DistilBertTokenizer.from_pretrained(MODEL)
    model = DistilBertForSequenceClassification.from_pretrained(MODEL).to(dev).eval()
    print(f"模型 {os.path.relpath(MODEL, HERE)}｜阈值 {thr}｜device {dev}")

    pool = read_csv_rows(CANDS)
    sample = read_csv_rows(SAMPLE) if os.path.isfile(SAMPLE) else pool
    print(f"候选池 {len(pool)} 条；本次评估样本 {len(sample)} 条")

    def run(rows):
        texts = [r["text"] for r in rows]
        return np.array(predict(model, tok, texts, MAX_LEN, "truncate", MAX_LEN, 64, dev))

    p_sample = run(sample)
    flag_sample = (p_sample >= thr).astype(int)
    k, n = int(flag_sample.sum()), len(flag_sample)
    lo, hi = wilson(k, n)
    print(f"\n[样本层] 模型判为音质差评：{k}/{n} = {k/n*100:.1f}%"
          f"（Wilson 95% CI {lo*100:.1f}–{hi*100:.1f}%）")

    # 分层外推（层定义与 w4_strata.json 一致）
    layer_of, pop = {}, {}
    for r in pool:
        key = f"{r['rating']}★/{r['hits'].split(',')[0]}"
        layer_of[int(r["row_index"])] = key
        pop[key] = pop.get(key, 0) + 1
    kk, nn = {}, {}
    for i, r in enumerate(sample):
        key = f"{r['rating']}★/{r['hits'].split(',')[0]}"
        nn[key] = nn.get(key, 0) + 1
        kk[key] = kk.get(key, 0) + int(flag_sample[i])
    est = var = 0.0
    rows = []
    for key in sorted(nn):
        p = kk[key] / nn[key]
        N_h = pop.get(key, 0)
        est += N_h * p
        if nn[key] > 1:
            var += (N_h ** 2) * p * (1 - p) / (nn[key] - 1)
        rows.append({"层": key, "N_h": N_h, "n_h": nn[key], "命中": kk[key],
                     "比率": round(p, 3), "外推": round(N_h * p, 1)})
    se = math.sqrt(var)
    print(f"[分层外推] 候选池中模型判为音质差评 ≈ **{est:,.0f}** 条"
          f"（95% CI {max(0,est-1.96*se):,.0f} – {est+1.96*se:,.0f}）")
    print(f"[对照] 池内已有正例 1,280 条；若预筛全部成立，正例规模可达 ≈ {1280+est:,.0f} 条"
          f"（**代理口径，需 LLM 复核确认**）")

    # 全池评估（便于看分布，不用于外推）
    p_pool = run(pool)
    flag_pool = int((p_pool >= thr).sum())
    print(f"[全池直推] 12,744 条候选中模型判正 {flag_pool} 条（{flag_pool/len(pool)*100:.1f}%）")
    print(f"[对照] 样本层外推与全池直推相差 {abs(est-flag_pool)/max(flag_pool,1)*100:.1f}%"
          f"（抽样波动 + 分层外推的近似性）")

    json.dump({"model": "v2/model_maxlen256", "threshold": thr, "gen": "[v2]",
               "sample": {"n": n, "flagged": k, "rate": round(k/n, 4),
                          "wilson95": [round(lo, 4), round(hi, 4)]},
               "strata": rows,
               "pool_estimate": {"point": round(est, 1),
                                 "ci95": [round(max(0, est-1.96*se), 1),
                                          round(est+1.96*se, 1)]},
               "pool_direct": {"flagged": flag_pool, "rate": round(flag_pool/len(pool), 4)},
               "caveat": "代理口径：模型 P/R 有限（v2 调优档 P 77.0%/R 68.0%），"
                         "故既含误报也含漏报；结论须以 LLM 复核（W4 复核段）为准"},
              open(os.path.join(OUT, "w4_prescreen.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    md = ["# W4 预筛估计（代理口径，无需 LLM 凭证）", "",
          f"> 模型 `v2/model_maxlen256`，阈值 **{thr}**（v2 调优档）；样本 "
          f"**{n}** 条（与 `v2/w4_sample.csv` 同一分层样本）。", "",
          "## 结果", "",
          f"- 样本层：模型判为音质差评 **{k}/{n} = {k/n*100:.1f}%**"
          f"（Wilson 95% CI {lo*100:.1f}–{hi*100:.1f}%）",
          f"- **分层外推**：12,744 条候选池中约 **{est:,.0f}** 条"
          f"（95% CI {max(0,est-1.96*se):,.0f} – {est+1.96*se:,.0f}）",
          f"- 全池直推（对照）：{flag_pool} 条（{flag_pool/len(pool)*100:.1f}%）",
          f"- 合并含义：现有正例 1,280 + 预筛命中 ≈ **{1280+est:,.0f}** 条（若全部成立）", "",
          "## 分层明细", "",
          "| 层 | 总体 N_h | 样本 n_h | 模型命中 | 比率 | 外推 |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['层']} | {r['N_h']} | {r['n_h']} | {r['命中']} | {r['比率']} | {r['外推']} |")
    md += ["", "## 必须同时声明的边界（不可省）", "",
           "1. **这是代理口径**：模型在正例上的 P≈77.0%、R≈68.0%（v2 调优档），"
           "因此「模型判正」**既含误报也含漏报**，不能当作「新增正例数」对外宣称；",
           "2. **它不能替代 LLM 复核**：W4 复核段仍待凭证（`v2_w4_mine.py --review`），"
           "复核完成后用 `v2_w4_estimate.py` 出正式估计；",
           "3. **它的用途**：① 凭证到位前给出量级与分层结构；② 与 LLM 复核结果对照，"
           "可量化「模型 vs LLM」在四五星子集上的一致性（一个额外的方法学产出）。"]
    open(os.path.join(HERE, "docs", "w4_prescreen_estimate.md"), "w",
         encoding="utf-8", newline="\n").write("\n".join(md) + "\n")
    print("[写出] v2/w4_prescreen.json、docs/w4_prescreen_estimate.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
