# -*- coding: utf-8 -*-
"""范围内重评（D-Q8 相关，决策方批准的第 3 项）：
把冻结点测集**按产品口径切分**，分别报告指标——
  · 全测试集（现状口径）
  · **耳机家族**（headphone/earbud/headset）——即"名副其实的耳机音质"口径
  · 口径外（音箱/线缆/非音频…）
纯后处理：使用现成概率缓存 `v2/w5_probs_test.csv`（不重跑模型、不碰冻结资产）。

用途：回答"限定在范围内时我们的指标是多少"，并量化口径污染对指标的影响。

用法：python inscope_reeval.py
产物：docs/inscope_reeval.md、v2/inscope_reeval.json
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
HP = {"headphone", "earbud", "headset"}


def load_probs():
    rows = []
    with open(os.path.join(HERE, "v2", "w5_probs_test.csv"), encoding="utf-8",
              errors="replace") as fh:
        for r in csv.DictReader(fh):
            try:
                rows.append((r["text"], int(float(r["label"])), float(r["prob"])))
            except (TypeError, ValueError):
                continue
    return rows


def load_scope():
    """{text_index: category}（test:<i> → 第 i 行 val_v3_test）。"""
    out = {}
    p = os.path.join(HERE, "v2", "scope_rows.jsonl")
    if os.path.isfile(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if str(rec.get("uid", "")).startswith("test:"):
                out[int(rec["uid"].split(":")[1])] = rec["category"]
    return out


def test_texts():
    with open(os.path.join(HERE, "val_v3_test.csv"), encoding="utf-8",
              errors="replace") as fh:
        return [r["text"] for r in csv.DictReader(fh)]


def prf(y, p, thr):
    tp = sum(1 for a, b in zip(y, p) if a == 1 and b >= thr)
    fp = sum(1 for a, b in zip(y, p) if a == 0 and b >= thr)
    fn = sum(1 for a, b in zip(y, p) if a == 1 and b < thr)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"n": len(y), "pos": sum(y), "pred_pos": tp + fp, "tp": tp, "fp": fp, "fn": fn,
            "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}


def pr_auc(y, p):
    """平均精确率（PR-AUC 的阶梯近似）。"""
    order = sorted(range(len(p)), key=lambda i: -p[i])
    tp = fp = 0
    prev_rec = 0.0
    area = 0.0
    P = sum(y)
    if P == 0:
        return float("nan")
    for i in order:
        if y[i] == 1:
            tp += 1
        else:
            fp += 1
        rec = tp / P
        prec = tp / (tp + fp)
        area += prec * (rec - prev_rec)
        prev_rec = rec
    return round(area, 4)


def main() -> int:
    thr_tuned = 0.6
    tp_path = os.path.join(HERE, "v2", "threshold.json")
    if os.path.isfile(tp_path):
        try:
            thr_tuned = float(json.load(open(tp_path, encoding="utf-8")).get("thr", 0.6))
        except (ValueError, TypeError):
            pass
    probs = load_probs()
    scope = load_scope()
    texts = test_texts()
    print(f"概率缓存 {len(probs)} 条｜口径判定 {len(scope)}/{len(texts)} 条｜调优阈值 {thr_tuned}")
    if len(scope) < len(texts) * 0.9:
        print("[等待] 口径判定尚未完成（<90%），先跑 python scope_classify.py")
        return 0
    # 以文本对齐（缓存与测试集同源，顺序一致；仍按文本校验）
    by_text = {t: (lab, pr) for t, lab, pr in probs}
    groups = {"全测试集": [], "耳机家族（范围内）": [], "明确口径外": [], "无法判断（unclear）": []}
    for i, t in enumerate(texts):
        if t not in by_text:
            continue
        lab, pr = by_text[t]
        cat = scope.get(i, "unclear")
        item = (lab, pr)
        groups["全测试集"].append(item)
        if cat in HP:
            groups["耳机家族（范围内）"].append(item)
        elif cat == "unclear":
            groups["无法判断（unclear）"].append(item)
        else:
            groups["明确口径外"].append(item)
    res = {"threshold_tuned": thr_tuned, "protocol": "阈值取自 v2/threshold.json；纯后处理，不重跑模型",
           "groups": {}}
    print(f"\n{'组':<18}{'n':>7}{'正例':>6}{'F1@0.5':>9}{'F1@调优':>10}{'PR-AUC':>9}{'精确':>8}{'召回':>8}")
    for name, items in groups.items():
        if not items:
            continue
        y = [a for a, _ in items]
        p = [b for _, b in items]
        m05 = prf(y, p, 0.5)
        mt = prf(y, p, thr_tuned)
        auc = pr_auc(y, p)
        res["groups"][name] = {"n": m05["n"], "pos": m05["pos"], "f1_0.5": m05["f1"],
                               "f1_tuned": mt["f1"], "pr_auc": auc,
                               "precision_0.5": m05["precision"], "recall_0.5": m05["recall"],
                               "tp": m05["tp"], "fp": m05["fp"], "fn": m05["fn"]}
        print(f"{name:<18}{m05['n']:>7}{m05['pos']:>6}{m05['f1']:>9.4f}{mt['f1']:>10.4f}"
              f"{auc:>9.4f}{m05['precision']:>8.3f}{m05['recall']:>8.3f}")
    json.dump(res, open(os.path.join(HERE, "v2", "inscope_reeval.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    g = res["groups"]
    md = ["# 范围内重评：按产品口径切分冻结点测集", "",
          f"> 阈值 **{thr_tuned}**（取自 `v2/threshold.json`）｜**纯后处理**：用现成概率缓存 "
          "`v2/w5_probs_test.csv`，未重跑模型、未改任何冻结资产。", "",
          "> **口径判定的可靠性**：分类器在同一批人工真值上 **召回 92%、误报 17%、精确率 71%**"
          "（验证集＝S3 的 50 条 LLM 正例，见 `docs/gold_set/gold_standard_findings.md`）——"
          "故下表的组间切分**自带该量级误差**，结论应读作「量级与方向」，不是精确值。", "",
          "| 组 | n | 正例 | F1@0.5 | F1@调优 | PR-AUC | 精确率@0.5 | 召回@0.5 | TP/FP/FN |",
          "|---|---|---|---|---|---|---|---|---|"]
    for name, d in g.items():
        md.append(f"| {name} | {d['n']:,} | {d['pos']} | {d['f1_0.5']} | {d['f1_tuned']} | "
                  f"{d['pr_auc']} | {d['precision_0.5']} | {d['recall_0.5']} | "
                  f"{d['tp']}/{d['fp']}/{d['fn']} |")
    md += ["", "## 读法", "",
           "- **耳机家族**一列即「名副其实的耳机音质」口径——评委最可能追问的那个数；",
           "- 与全测试集之差 = **口径污染对指标的贡献**（若口径外条目多为负例，则它们主要压低精确率）；",
           "- 组内正例数很小（128 条正例被切分），故**不要**据此下「模型在范围内更好/更差」的强结论；",
           "- 该表回答的是「限定范围后指标长什么样」，**不是**新模型的结果。"]
    open(os.path.join(HERE, "docs", "inscope_reeval.md"), "w", encoding="utf-8",
         newline="\n").write("\n".join(md) + "\n")
    print("\n[写出] docs/inscope_reeval.md、v2/inscope_reeval.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
