# -*- coding: utf-8 -*-
"""W1 变体 E（改）：混合策略的**约束式阈值选择**（CPU，复用已缓存概率）。

上一版失败原因：在 tune 上直接最大化**整体 F1**，因长档仅占 19.3% 的样本，
最优解会把长档阈值推到 0.95（少报以免误报），导致 test 长档召回仅 43.9%（DoD 未达）。

本版改为**约束式选择**（仍严格在 tune 上做，不碰 test）：
  ① 先筛出满足「长档召回 ≥ 70%」的长档阈值集合；
  ② 在集合内选使**整体 F1 最大**的（短档阈值, 长档阈值）组合；
  ③ 若不存在满足约束的长档阈值，则报告 tune 上的**最大可达长档召回**及其代价。

输出：`v2/w1_hybrid_result.json`（覆盖上一版）+ 控制台 Pareto 表（长档阈值 → tune/test 表现）。
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_w1_hybrid import SHORT_MAX, metrics_hybrid  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GRID = [round(0.05 * k, 2) for k in range(2, 20)]   # 0.10–0.95
RECALL_FLOOR = 70.0


def load(tag):
    p = os.path.join(HERE, "v2", f"w1_probs_{tag}.csv")
    labels, tl, ptr, pseg = [], [], [], []
    with open(p, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            labels.append(int(r["label"]))
            tl.append(int(r["tokens"]))
            ptr.append(float(r["p_trunc"]))
            pseg.append(float(r["p_seg"]))
    return labels, tl, np.array(ptr), np.array(pseg)


def decide(tl, ptr, pseg, ts, tlg):
    probs = np.where(np.array(tl) > SHORT_MAX, pseg, ptr)
    thrs = [ts if L <= SHORT_MAX else tlg for L in tl]
    return probs, thrs


def long_recall(y, tl, probs, thrs):
    idx = [i for i, L in enumerate(tl) if L > SHORT_MAX and y[i] == 1]
    if not idx:
        return 0.0
    return sum(1 for i in idx if probs[i] >= thrs[i]) / len(idx) * 100


def main() -> int:
    y_t, tl_t, ptr_t, pseg_t = load("tune")
    y_s, tl_s, ptr_s, pseg_s = load("test")
    print(f"tune n={len(y_t)}（长档 {sum(1 for L in tl_t if L > SHORT_MAX)} 条）；"
          f"test n={len(y_s)}（长档 {sum(1 for L in tl_s if L > SHORT_MAX)} 条）")

    # ① tune 上按长档阈值求可达召回（短档阈值先固定 0.5，仅用于筛约束）
    pareto = []
    for tlg in GRID:
        probs, thrs = decide(tl_t, ptr_t, pseg_t, 0.5, tlg)
        pareto.append((tlg, long_recall(y_t, tl_t, probs, thrs)))
    feasible = [t for t, r in pareto if r >= RECALL_FLOOR]
    print("tune 长档阈值 → 长档召回：",
          "；".join(f"{t}:{r:.0f}%" for t, r in pareto))
    print(f"满足 ≥{RECALL_FLOOR}% 的长档阈值：{feasible or '（无）'}")

    # ② 在可行集合内选整体 F1 最大的组合
    best = None
    for tlg in (feasible or [t for t, _ in pareto]):
        for ts in GRID:
            probs, thrs = decide(tl_t, ptr_t, pseg_t, ts, tlg)
            m = metrics_hybrid(y_t, probs, thrs)
            lr = long_recall(y_t, tl_t, probs, thrs)
            if feasible and lr < RECALL_FLOOR:
                continue
            key = m["F1"]
            if best is None or key > best[0]:
                best = (key, ts, tlg, m, lr)
    if best is None:
        print("[FAIL] 无可行解")
        return 1
    _, ts, tlg, m_tune, lr_tune = best
    print(f"[tune 选定（约束式）] 短档 {ts}／长档 {tlg} → tune 整体 F1 {m_tune['F1']}、"
          f"长档召回 {lr_tune:.1f}%")

    # ③ test 上报
    probs_s, thrs_s = decide(tl_s, ptr_s, pseg_s, ts, tlg)
    overall = metrics_hybrid(y_s, probs_s, thrs_s)
    buckets = {}
    for lo, hi, name in ((0, SHORT_MAX, "≤128 token"), (SHORT_MAX + 1, 10 ** 9, ">128 token")):
        idx = [i for i, L in enumerate(tl_s) if lo <= L <= hi]
        sub_y = [y_s[i] for i in idx]
        buckets[name] = {"n": len(idx), "pos": int(sum(sub_y)),
                         **metrics_hybrid(sub_y, np.array([probs_s[i] for i in idx]),
                                          [thrs_s[i] for i in idx])}
        print(f"  桶 {name}: n={len(idx)} pos={sum(sub_y)} "
              f"F1 {buckets[name]['F1']} R {buckets[name]['R']}%")
    print(f"[test 整体] P {overall['P']}% R {overall['R']}% F1 {overall['F1']} "
          f"(TP{overall['TP']}/FP{overall['FP']}/FN{overall['FN']})")

    dod = {"truncated_bucket_recall_test": buckets[">128 token"]["R"],
           "threshold": RECALL_FLOOR,
           "pass": buckets[">128 token"]["R"] >= RECALL_FLOOR}
    print(f"[DoD] 截断桶召回 {dod['truncated_bucket_recall_test']}% vs "
          f"{RECALL_FLOOR}% → {'通过' if dod['pass'] else '未通过'}")

    out = {"protocol": "短档(≤128 token)截断 + 长档(>128 token)切窗；**约束式**阈值选择："
                        "先约束长档 tune 召回 ≥70%，再最大化整体 F1；只在 tune 上选、只在 test 上报",
           "model": "v2/model_maxlen128", "gen": "[v2]",
           "chosen": {"thr_short": ts, "thr_long": tlg, "tune_overall": m_tune,
                      "tune_long_recall": round(lr_tune, 1)},
           "tune_pareto": [{"thr_long": t, "long_recall": round(r, 1)} for t, r in pareto],
           "test_overall": overall, "test_buckets": buckets, "dod": dod,
           "reference": {
               "A_truncate128": {"overall_F1": 0.7077, "long_R": 51.2},
               "B_truncate256": {"overall_F1": 0.7206, "long_R": 51.2},
               "D_truncate512": {"overall_F1": 0.71, "long_R": 51.2},
               "C_segment@0.5": {"overall_F1": 0.6034, "long_R": 82.9},
               "C_segment@0.8(tuned)": {"overall_F1": 0.6061, "long_R": 68.3},
           }}
    with open(os.path.join(HERE, "v2", "w1_hybrid_result.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("[写出] v2/w1_hybrid_result.json（覆盖上一版）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
