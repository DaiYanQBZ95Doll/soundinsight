# -*- coding: utf-8 -*-
"""B2 基线：TF-IDF + 线性模型（LogisticRegression / LinearSVC）。

协议：在 train 划分上训练（主标签 v2-LLM）→ 在 val 上选阈值（最优 F1）→ 在 test 上报告
（同时给 @0.5 与 val 选定阈值两套数）；输出预测 JSON 供统一评测台与 McNemar 使用。
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

import numpy as np  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.svm import LinearSVC  # noqa: E402
from sklearn.calibration import CalibratedClassifierCV  # noqa: E402


def main() -> int:
    sp = json.load(open(os.path.join(HERE, "v2", "thesis_split.json"), encoding="utf-8"))
    texts, labels = {}, {}
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            texts[i] = r["text"]
            labels[i] = 1 if str(r.get("sound_negative_llm")) == "1" else 0

    Xtr = [texts[i] for i in sp["row_index"]["train"]]
    ytr = np.array([labels[i] for i in sp["row_index"]["train"]])
    Xva = [texts[i] for i in sp["row_index"]["val"]]
    yva = np.array([labels[i] for i in sp["row_index"]["val"]])
    Xte = [texts[i] for i in sp["row_index"]["test"]]
    yte = np.array([labels[i] for i in sp["row_index"]["test"]])
    print(f"  train {len(Xtr)}（正 {ytr.sum()}）｜val {len(Xva)}（正 {yva.sum()}）"
          f"｜test {len(Xte)}（正 {yte.sum()}）")

    t0 = time.time()
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True,
                          strip_accents="unicode", lowercase=True, max_features=400000)
    Xtr_v = vec.fit_transform(Xtr)
    Xva_v = vec.transform(Xva)
    Xte_v = vec.transform(Xte)
    print(f"  向量化完成：{Xtr_v.shape[1]:,} 维｜{time.time()-t0:.1f}s")

    out = {}
    for name, clf in (("lr", LogisticRegression(class_weight="balanced", C=4.0,
                                                max_iter=3000, solver="liblinear")),
                      ("svc", CalibratedClassifierCV(
                          LinearSVC(class_weight="balanced", C=1.0), cv=3))):
        t1 = time.time()
        clf.fit(Xtr_v, ytr)
        pv = clf.predict_proba(Xva_v)[:, 1]
        pt = clf.predict_proba(Xte_v)[:, 1]
        best, bt = -1.0, 0.5
        for thr in np.arange(0.05, 0.96, 0.05):
            tp = int(((pv >= thr) & (yva == 1)).sum())
            fp = int(((pv >= thr) & (yva == 0)).sum())
            fn = int(((pv < thr) & (yva == 1)).sum())
            prec = tp / (tp + fp) if tp + fp else 0.0
            rec = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
            if f1 > best:
                best, bt = f1, float(thr)
        print(f"  [{name.upper()}] 训练 {time.time()-t1:.1f}s｜val 最优阈值 {bt:.2f}"
              f"（val F1 {best*100:.1f}%）")
        json.dump({str(i): float(p) for i, p in zip(sp["row_index"]["val"], pv)},
                  open(os.path.join(HERE, "v2", f"exp_b2{name}_val.json"), "w",
                       encoding="utf-8"))
        json.dump({str(i): float(p) for i, p in zip(sp["row_index"]["test"], pt)},
                  open(os.path.join(HERE, "v2", f"exp_b2{name}_test.json"), "w",
                       encoding="utf-8"))
        json.dump({"model": f"tfidf+{name}", "val_best_thr": bt, "val_best_f1": round(best, 4),
                   "dim": int(Xtr_v.shape[1])},
                  open(os.path.join(HERE, "v2", f"exp_b2{name}_config.json"), "w",
                       encoding="utf-8"), ensure_ascii=False, indent=2)
        out[name] = bt
    print("  [写出] v2/exp_b2{lr,svc}_{val,test}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
