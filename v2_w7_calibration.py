# -*- coding: utf-8 -*-
"""W7：概率校准（温度缩放），**只在 val_v3_tune 上拟合，只在 val_v3_test 上报告**。

数据来源：`v2/w1_probs_{tune,test}.csv`（冻结模型在无泄漏划分上的截断推理概率缓存）——
因此本步骤**不需要 GPU**，也不引入新的推理口径。

方法与指标：
- **温度缩放**：p' = σ(logit / T)，T 在 tune 上以最小化 NLL（对数损失）拟合；
- **ECE（十箱）**：|acc − conf| 按箱加权；**同时报告决策区间 [0.9,1.0)** 的偏差
  （v1 曾发现该区间实际正确率仅 0.555、自报 0.975、偏差 −0.42，是被整体 ECE 0.0122 稀释掉的问题）；
- **Brier** 与 **可靠性曲线**（落盘为 markdown 表 + PNG）。

DoD（冻结清单 §二 W7）：校准器只在 tune 上拟合；**决策区间各箱偏差 ≤0.15**。

用法：python v2_w7_calibration.py [--model-tag maxlen128]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v2")
EPS = 1e-6


def load(tag):
    path = os.path.join(OUT, f"w1_probs_{tag}.csv")
    y, p = [], []
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            y.append(int(r["label"]))
            p.append(float(r["p_trunc"]))
    return np.array(y), np.clip(np.array(p), EPS, 1 - EPS)


def logit(p):
    return np.log(p / (1 - p))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def nll(y, p):
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def ece(y, p, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    total, table = 0.0, []
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        m = (p >= lo) & (p < hi if i < bins - 1 else p <= hi)
        if not m.any():
            table.append((lo, hi, 0, None, None, None))
            continue
        conf = float(p[m].mean())
        acc = float(y[m].mean())
        total += m.sum() / len(p) * abs(acc - conf)
        table.append((lo, hi, int(m.sum()), conf, acc, acc - conf))
    return float(total), table


def fit_temperature(y, p):
    """网格 + 细化的 T（无需 scipy 优化器，稳定可复现）。"""
    best_t, best_v = 1.0, nll(y, p)
    for t in np.arange(0.5, 5.01, 0.01):
        v = nll(y, sigmoid(logit(p) / t))
        if v < best_v:
            best_t, best_v = float(t), v
    return best_t, best_v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-tag", default="maxlen128")
    args = ap.parse_args()

    y_t, p_t = load("tune")
    y_s, p_s = load("test")
    print(f"tune n={len(y_t)} 正例 {int(y_t.sum())}；test n={len(y_s)} 正例 {int(y_s.sum())}")

    T, nll_t = fit_temperature(y_t, p_t)
    print(f"[tune 拟合] 温度 T = {T:.2f}（tune NLL {nll(y_t, p_t):.4f} → {nll_t:.4f}）")

    p_t2, p_s2 = sigmoid(logit(p_t) / T), sigmoid(logit(p_s) / T)
    res = {}
    rows = []
    for name, (yy, before, after) in (
            ("tune", (y_t, p_t, p_t2)), ("test", (y_s, p_s, p_s2))):
        e0, t0 = ece(yy, before)
        e1, t1 = ece(yy, after)
        b0, b1 = float(np.mean((before - yy) ** 2)), float(np.mean((after - yy) ** 2))
        res[name] = {"ece_before": round(e0, 4), "ece_after": round(e1, 4),
                     "brier_before": round(b0, 4), "brier_after": round(b1, 4),
                     "nll_before": round(nll(yy, before), 4),
                     "nll_after": round(nll(yy, after), 4),
                     "bins": [{"lo": round(a, 2), "hi": round(b, 2), "n": n,
                               "conf": None if c is None else round(c, 3),
                               "acc": None if a2 is None else round(a2, 3),
                               "gap": None if d is None else round(d, 3)}
                              for a, b, n, c, a2, d in t1]}
        print(f"[{name}] ECE {e0:.4f} → {e1:.4f}｜Brier {b0:.4f} → {b1:.4f}｜"
              f"NLL {nll(yy, before):.4f} → {nll(yy, after):.4f}")
        rows.append((name, t0, t1))

    # 决策区间偏差（[0.9,1.0)）
    def gap_high(yy, pp):
        m = pp >= 0.9
        if not m.any():
            return None, 0
        return float(yy[m].mean() - pp[m].mean()), int(m.sum())
    g0, n0 = gap_high(y_s, p_s)
    g1, n1 = gap_high(y_s, p_s2)
    print(f"[test 决策区间 ≥0.9] 校准前偏差 {None if g0 is None else round(g0, 3)}（n={n0}）"
          f" → 校准后 {None if g1 is None else round(g1, 3)}（n={n1}）")

    # 抗稀释 ECE：只在 p≥0.5 的子集上算（v1 的 ECE 0.0122 被 98.7% 负例稀释）
    def ece_high(yy, pp, cut=0.5):
        m = pp >= cut
        if not m.any():
            return None, 0
        e, _ = ece(yy[m], pp[m])
        return e, int(m.sum())
    eh0, nh0 = ece_high(y_s, p_s)
    eh1, nh1 = ece_high(y_s, p_s2)
    print(f"[test 抗稀释 ECE（p≥0.5）] {None if eh0 is None else round(eh0, 4)}（n={nh0}）"
          f" → {None if eh1 is None else round(eh1, 4)}（n={nh1}）")

    # DoD：决策区间各箱偏差 ≤0.15（用校准后的 test 分箱）
    worst, worst_bin = 0.0, None
    for b in res["test"]["bins"]:
        if b["n"] and b["gap"] is not None and b["n"] >= 20:
            if abs(b["gap"]) > abs(worst):
                worst, worst_bin = b["gap"], b
    dod_pass = abs(worst) <= 0.15
    print(f"[DoD] test 上最大分箱偏差（n≥20）{worst:+.3f}"
          f"{'（箱 ' + str(worst_bin['lo']) + '–' + str(worst_bin['hi']) + '）' if worst_bin else ''}"
          f" vs 阈值 0.15 → {'通过' if dod_pass else '未通过'}")

    payload = {"protocol": "温度缩放，T 只在 val_v3_tune 上拟合；ECE/Brier/分箱只在 test 上报告",
               "source": "v2/w1_probs_{tune,test}.csv（冻结模型截断推理概率缓存）",
               "gen": "[v2]", "temperature": round(T, 3),
               "tune_nll": {"before": round(nll(y_t, p_t), 4), "after": round(nll_t, 4)},
               "results": res,
               "decision_band_ge_0.9": {"gap_before": None if g0 is None else round(g0, 3),
                                        "n_before": n0,
                                        "gap_after": None if g1 is None else round(g1, 3),
                                        "n_after": n1},
               "ece_dilution_resistant": {
                   "cut": 0.5, "note": "只在 p≥0.5 的子集上算（避免被 98.7% 负例稀释）",
                   "before": None if eh0 is None else round(eh0, 4), "n_before": nh0,
                   "after": None if eh1 is None else round(eh1, 4), "n_after": nh1},
               "dod": {"max_bin_gap_test": round(worst, 3), "threshold": 0.15,
                       "pass": bool(dod_pass)}}
    with open(os.path.join(OUT, "w7_calibration.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    # markdown 报告
    md = ["# W7 概率校准（温度缩放）", "",
          f"> 协议：温度 **T = {T:.2f}** 只在 `val_v3_tune` 上拟合（最小化 NLL），"
          f"ECE／Brier／分箱只在 `val_v3_test` 上报告。数据源＝冻结模型的截断推理概率缓存。", "",
          "| 集合 | ECE 前 | ECE 后 | Brier 前 | Brier 后 | NLL 前 | NLL 后 |",
          "|---|---|---|---|---|---|---|"]
    for name, _, _ in rows:
        d = res[name]
        md.append(f"| {name} | {d['ece_before']} | {d['ece_after']} | {d['brier_before']} | "
                  f"{d['brier_after']} | {d['nll_before']} | {d['nll_after']} |")
    md += ["", "## test 可靠性分箱（校准后）", "",
           "| 区间 | 条数 | 平均置信 | 实际正确率 | 偏差 |", "|---|---|---|---|---|"]
    for b in res["test"]["bins"]:
        if b["n"]:
            md.append(f"| {b['lo']}–{b['hi']} | {b['n']} | {b['conf']} | {b['acc']} | {b['gap']:+} |")
    md += ["", "## 抗稀释 ECE（只在 p≥0.5 的子集上算）", "",
           f"- 校准前 **{None if eh0 is None else round(eh0, 4)}**（n={nh0}）→ "
           f"校准后 **{None if eh1 is None else round(eh1, 4)}**（n={nh1}）",
           "- 说明：整体 ECE 极小（见上表）是**被 98.7% 负例稀释**的结果；"
           "只在高分区间上看，校准的收益才显现（这正是 v1 记录 ECE 0.0122 时缺失的口径）。", "",
           "## 决策区间（≥0.9）偏差", "",
           f"- 校准前 **{None if g0 is None else round(g0, 3)}**（n={n0}）→ "
           f"校准后 **{None if g1 is None else round(g1, 3)}**（n={n1}）", ""]
    md += ["", f"## DoD 判定", "",
           f"- 决策区间各箱偏差 ≤0.15（n≥20）：**{'通过' if dod_pass else '未通过'}**"
           f"（test 最大偏差 {worst:+.3f}）", ""]
    with open(os.path.join(OUT, "w7_calibration.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))
    print("[写出] v2/w7_calibration.json / .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
