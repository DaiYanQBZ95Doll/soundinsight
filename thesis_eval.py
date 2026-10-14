# -*- coding: utf-8 -*-
"""论文统一评测台：所有方法共用同一套指标与区间，避免"各算各的"。

用法：
    python thesis_eval.py --pred v2/exp_b2_test.json --split test --name "B2 TF-IDF+LR"
    python thesis_eval.py --mcnemar v2/exp_a_test.json v2/exp_b_test.json

预测文件格式（JSON）：{"<row_index>": <prob>, ...}（只含被评估划分的条目）

指标：P/R/F1（Wilson 区间；F1 用 bootstrap）、AUC-PR、ECE（10 桶）、混淆计数；
      McNemar 配对检验（同一批条目上比较两方法）。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = os.path.join(HERE, "v2", "thesis_split.json")
CORPUS = os.path.join(HERE, "labeled_llm.csv")


def load_labels():
    """返回 {row_index: 1/0}（主标签 sound_negative_llm）。"""
    lab = {}
    with open(CORPUS, encoding="utf-8", errors="replace") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            lab[i] = 1 if str(r.get("sound_negative_llm")) == "1" else 0
    return lab


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


def prf(y, p, thr=0.5):
    tp = sum(1 for a, b in zip(y, p) if a == 1 and b >= thr)
    fp = sum(1 for a, b in zip(y, p) if a == 0 and b >= thr)
    fn = sum(1 for a, b in zip(y, p) if a == 1 and b < thr)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "P": prec, "R": rec, "F1": f1}


def auc_pr(y, p):
    order = sorted(range(len(p)), key=lambda i: -p[i])
    tp = fp = 0
    P = sum(y)
    if P == 0:
        return 0.0
    prev_r = 0.0
    ap = 0.0
    for i in order:
        if y[i] == 1:
            tp += 1
        else:
            fp += 1
        r = tp / P
        if y[i] == 1:
            ap += (r - prev_r) * (tp / (tp + fp))
            prev_r = r
    return ap


def ece(y, p, bins=10):
    tot = len(p)
    e = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, q in enumerate(p) if (lo <= q < hi) or (b == bins - 1 and q == 1.0)]
        if not idx:
            continue
        conf = sum(p[i] for i in idx) / len(idx)
        acc = sum(y[i] for i in idx) / len(idx)
        e += (len(idx) / tot) * abs(acc - conf)
    return e


def boot_f1(y, p, thr, n=1000, seed=42):
    rng = random.Random(seed)
    vals = []
    N = len(y)
    for _ in range(n):
        idx = [rng.randrange(N) for _ in range(N)]
        yy = [y[i] for i in idx]
        pp = [p[i] for i in idx]
        vals.append(prf(yy, pp, thr)["F1"])
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def best_thr(y, p):
    cands = sorted({0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9} | {round(q, 3) for q in p})
    best, bt = -1.0, 0.5
    for t in cands:
        f = prf(y, p, t)["F1"]
        if f > best:
            best, bt = f, t
    return bt, best


def cmd_eval(a) -> int:
    sp = json.load(open(SPLIT, encoding="utf-8"))
    lab = load_labels()
    idx = sp["row_index"][a.split]
    pred = json.load(open(a.pred, encoding="utf-8"))
    y, p, miss = [], [], 0
    for i in idx:
        v = pred.get(str(i), pred.get(i))
        if v is None:
            miss += 1
            continue
        y.append(lab[i])
        p.append(float(v))
    if miss:
        print(f"  [警告] {miss}/{len(idx)} 条无预测（按缺失跳过）")
    m = prf(y, p, 0.5)
    lo_p, hi_p = wilson(m["tp"], m["tp"] + m["fp"])
    lo_r, hi_r = wilson(m["tp"], m["tp"] + m["fn"])
    lo_f, hi_f = boot_f1(y, p, 0.5)
    bt, bf = best_thr(y, p)
    res = {"name": a.name or os.path.basename(a.pred), "split": a.split, "n": len(y),
           "pos": sum(y), "thr0.5": m,
           "P_ci": [round(lo_p, 4), round(hi_p, 4)], "R_ci": [round(lo_r, 4), round(hi_r, 4)],
           "F1_ci": [round(lo_f, 4), round(hi_f, 4)],
           "auc_pr": round(auc_pr(y, p), 4), "ece": round(ece(y, p), 4),
           "best_thr_on_this_split": bt, "best_f1_oracle": round(bf, 4)}
    print(f"\n[{res['name']}] split={a.split} n={len(y)} pos={sum(y)}")
    print(f"  P {m['P']*100:.1f}%（CI {lo_p*100:.0f}–{hi_p*100:.0f}）"
          f"｜R {m['R']*100:.1f}%（CI {lo_r*100:.0f}–{hi_r*100:.0f}）"
          f"｜F1 {m['F1']*100:.1f}%（CI {lo_f*100:.0f}–{hi_f*100:.0f}）")
    print(f"  AUC-PR {res['auc_pr']:.3f}｜ECE {res['ece']:.3f}"
          f"｜混淆 TP{m['tp']}/FP{m['fp']}/FN{m['fn']}"
          f"｜最优阈值(本集上界) {bt} → F1 {bf*100:.1f}%")
    outp = a.out or a.pred.replace(".json", "_metrics.json")
    json.dump(res, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  [写出] {os.path.relpath(outp, HERE)}")
    return 0


def cmd_mcnemar(a) -> int:
    sp = json.load(open(SPLIT, encoding="utf-8"))
    lab = load_labels()
    idx = sp["row_index"][a.split]
    pa = json.load(open(a.mcnemar[0], encoding="utf-8"))
    pb = json.load(open(a.mcnemar[1], encoding="utf-8"))
    n01 = n10 = both = neither = 0
    for i in idx:
        ya = 1 if float(pa.get(str(i), pa.get(i, 0))) >= 0.5 else 0
        yb = 1 if float(pb.get(str(i), pb.get(i, 0))) >= 0.5 else 0
        t = lab[i]
        ca, cb = (ya == t), (yb == t)
        if ca and cb:
            both += 1
        elif ca and not cb:
            n01 += 1
        elif cb and not ca:
            n10 += 1
        else:
            neither += 1
    b, c = n01, n10
    if b + c == 0:
        chi, pv = 0.0, 1.0
    else:
        chi = (abs(b - c) - 1) ** 2 / (b + c)     # 连续性校正
        pv = math.erfc(math.sqrt(chi / 2))
    print(f"\n[McNemar] {os.path.basename(a.mcnemar[0])} vs {os.path.basename(a.mcnemar[1])}"
          f"｜split={a.split} n={len(idx)}")
    print(f"  都对 {both}｜只 A 对 {n01}｜只 B 对 {n10}｜都错 {neither}")
    print(f"  χ²(校正) {chi:.3f}｜p ≈ {pv:.4f}"
          f" → {'差异显著（p<0.05）' if pv < 0.05 else '未观察到显著差异'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred")
    ap.add_argument("--split", default="test", choices=["train", "val", "test"])
    ap.add_argument("--name", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--mcnemar", nargs=2)
    a = ap.parse_args()
    if a.mcnemar:
        return cmd_mcnemar(a)
    if not a.pred:
        ap.error("需要 --pred 或 --mcnemar")
    return cmd_eval(a)


if __name__ == "__main__":
    raise SystemExit(main())
