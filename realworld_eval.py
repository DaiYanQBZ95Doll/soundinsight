# -*- coding: utf-8 -*-
"""真实场景性能（**此前从未测过**）：用人工真值当标准答案，测出厂模型与 v2 候选的精确率/召回。

为什么这是最该测的：主指标 0.7220 是在「关键词可达 × 已复核星级」子集上、用 LLM 标签算的；
而产品的实际使用场景是**卖家上传自己的评论**（多数不含我们的闸门关键词）。
本脚本用决策方人工判定的 500 条（300 金标 + 100 追加 + 100 干净探针）作真值，
按「是否在说耳机音质」这一**人工口径**衡量模型——这是部署相关口径。

用法：python realworld_eval.py
产物：docs/realworld_eval.md、v2/realworld_eval.json
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
COL = "人工判定(1=音质差评/0=不是)"


def load_human():
    """→ [(uid, text, human(0/1/None))]"""
    out = []
    # 金标 300（含 LLM 标签，用于对照）
    ws = {r["编号"]: r["原文"] for r in csv.DictReader(
        open(os.path.join(HERE, "docs", "gold_set", "worksheet.csv"),
             encoding="utf-8-sig", errors="replace"))}
    v = {r["编号"]: (r.get(COL) or "").strip() for r in csv.DictReader(
        open(os.path.join(HERE, "docs", "gold_set", "assisted_worksheet.csv"),
             encoding="utf-8-sig", errors="replace"))}
    for i, t in ws.items():
        x = v.get(i, "")
        out.append((i, t, 1 if x == "1" else (0 if x == "0" else None)))
    # S4 追加 100
    for r in csv.DictReader(open(os.path.join(HERE, "docs", "gold_set", "s1_add100.csv"),
                                 encoding="utf-8-sig", errors="replace")):
        x = (r.get(COL) or "").strip()
        out.append((r["编号"], r["原文"], 1 if x == "1" else (0 if x == "0" else None)))
    # S5 干净探针 100
    for r in csv.DictReader(open(os.path.join(HERE, "docs", "gold_set", "s5_clean_probe.csv"),
                                 encoding="utf-8-sig", errors="replace")):
        x = (r.get(COL) or "").strip()
        out.append((r["编号"], r["原文"], 1 if x == "1" else (0 if x == "0" else None)))
    return [r for r in out if r[1].strip()]


def predict(texts, model_dir, max_len):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_dir)
    mdl = AutoModelForSequenceClassification.from_pretrained(model_dir)
    mdl.eval()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    mdl.to(dev)
    probs = []
    with torch.no_grad():
        for i in range(0, len(texts), 32):
            batch = texts[i:i + 32]
            enc = tok(batch, padding=True, truncation=True, max_length=max_len,
                      return_tensors="pt").to(dev)
            p = torch.softmax(mdl(**enc).logits, -1)[:, 1]
            probs += [float(x) for x in p.cpu()]
    return probs


def prf(y, p, thr):
    tp = sum(1 for a, b in zip(y, p) if a == 1 and b >= thr)
    fp = sum(1 for a, b in zip(y, p) if a == 0 and b >= thr)
    fn = sum(1 for a, b in zip(y, p) if a == 1 and b < thr)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(prec, 4),
            "recall": round(rec, 4), "f1": round(f1, 4)}


def pr_auc(y, p):
    order = sorted(range(len(p)), key=lambda i: -p[i])
    tp = fp = 0
    P = sum(y)
    if P == 0:
        return float("nan")
    prev, area = 0.0, 0.0
    for i in order:
        tp, fp = (tp + 1, fp) if y[i] == 1 else (tp, fp + 1)
        rec = tp / P
        area += (tp / (tp + fp)) * (rec - prev)
        prev = rec
    return round(area, 4)


def main() -> int:
    rows = load_human()
    labelled = [r for r in rows if r[2] is not None]
    texts = [r[1] for r in labelled]
    y = [r[2] for r in labelled]
    print(f"人工真值：{len(rows)} 条（可比对 {len(labelled)}，正例 {sum(y)}）")
    cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
    res = {"n": len(labelled), "human_positive": sum(y), "models": {}}
    jobs = [("出厂模型 v1（产品路径）", cfg["bin_model_dir"], 128,
             float(cfg.get("threshold", 0.5)))]
    v2t = os.path.join(HERE, "v2", "threshold.json")
    if os.path.isfile(v2t):
        t2 = json.load(open(v2t, encoding="utf-8"))
        jobs.append(("v2 候选（max_len=256）", os.path.join(HERE, "v2", "model_maxlen256"), 256,
                     float(t2.get("thr", 0.6))))
    print(f"{'模型':<24}{'阈值':>7}{'TP':>5}{'FP':>5}{'FN':>5}{'精确':>8}{'召回':>8}{'F1':>8}{'PR-AUC':>9}")
    for name, d, ml, thr in jobs:
        if not os.path.isdir(d):
            print(f"  [跳过] {name}：目录不存在 {d}")
            continue
        p = predict(texts, d, ml)
        m05 = prf(y, p, 0.5)
        mt = prf(y, p, thr)
        auc = pr_auc(y, p)
        res["models"][name] = {"dir": os.path.relpath(d, HERE), "max_len": ml,
                               "thr_tuned": thr, "at_0.5": m05, "at_tuned": mt, "pr_auc": auc,
                               "probs": p}
        print(f"{name:<24}{thr:>7.2f}{mt['tp']:>5}{mt['fp']:>5}{mt['fn']:>5}"
              f"{mt['precision']:>8.3f}{mt['recall']:>8.3f}{mt['f1']:>8.3f}{auc:>9.3f}")
    json.dump(res, open(os.path.join(HERE, "v2", "realworld_eval.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    md = ["# 真实场景性能（人工真值口径，此前从未测量）", "",
          f"> 真值：决策方人工判定 **{len(labelled)} 条**（金标 300＋追加 100＋干净探针 100 中已判者），"
          f"其中**人工确认为耳机音质差评 {sum(y)} 条**", "",
          "> 与主指标的区别：主指标 0.7220 报在「关键词可达 × 已复核星级」子集上、以 **LLM 标签**为准；"
          "本表**以人工判定为准**，且样本覆盖闸门外，故更接近产品实际使用场景。", "",
          "| 模型 | 调优阈值 | TP | FP | FN | 精确率 | 召回 | F1 | PR-AUC |",
          "|---|---|---|---|---|---|---|---|---|"]
    for name, d in res["models"].items():
        m = d["at_tuned"]
        md.append(f"| {name} | {d['thr_tuned']} | {m['tp']} | {m['fp']} | {m['fn']} | "
                  f"{m['precision']} | {m['recall']} | {m['f1']} | {d['pr_auc']} |")
    md += ["", "## 读法（必须与主指标并列引用）", "",
           "- 本表是**部署相关口径**：卖家上传的评论大多不含我们的闸门关键词，正例率约 1%；",
           "- 正例数很少（人工确认的耳机音质差评仅 " + str(sum(y)) + " 条），故**召回的点估计极不稳定**；",
           "- 若本表召回显著低于主指标口径，说明**主指标高估了真实可用性**——这一点必须写进材料。"]
    open(os.path.join(HERE, "docs", "realworld_eval.md"), "w", encoding="utf-8",
         newline="\n").write("\n".join(md) + "\n")
    print("\n[写出] docs/realworld_eval.md、v2/realworld_eval.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
