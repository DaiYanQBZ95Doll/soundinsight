# -*- coding: utf-8 -*-
# 本脚本用于显著性检验：重跑 SVM 5 折得到逐折 F1，与 DistilBERT 5 折 F1 做 t 检验，
# 结果保存 significance_test.md。
import os
import sys

import numpy as np
from scipy import stats
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score, precision_recall_curve
from sklearn.model_selection import StratifiedKFold
from sklearn.svm import LinearSVC

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_llm.csv")
OUT_MD = os.path.join(HERE, "significance_test.md")

DISTILBERT_F1 = [0.6655, 0.6151, 0.6325, 0.6054, 0.5983]


def main() -> None:
    import pandas as pd

    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    texts = df["text"].astype(str).tolist()
    labels = df["sound_negative_llm"].astype(int).tolist()

    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=50000,
                          sublinear_tf=True)
    X = vec.fit_transform(texts)
    print(f"TF-IDF: {X.shape}")

    svm_f1s = []
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    for tr, va in skf.split(np.arange(len(labels)), labels):
        model = LinearSVC(C=1.0, max_iter=2000)
        model.fit(X[tr], labels[tr] if isinstance(labels, np.ndarray)
                  else np.asarray(labels)[tr])
        probs = model.decision_function(X[va])
        y = np.asarray(labels)[va]
        precision, recall, thrs = precision_recall_curve(y, probs)
        f1s = 2 * precision * recall / (precision + recall + 1e-12)
        svm_f1s.append(float(f1s.max()))
        print(f"fold f1_best={svm_f1s[-1]:.4f}", flush=True)

    t_stat, p_value = stats.ttest_ind(DISTILBERT_F1, svm_f1s,
                                      equal_var=False)
    lines = [
        "# 显著性检验结果",
        "",
        f"DistilBERT 5 折调优 F1: {[round(v, 4) for v in DISTILBERT_F1]}",
        f"均值 {np.mean(DISTILBERT_F1):.4f} ± {np.std(DISTILBERT_F1):.4f}",
        "",
        f"SVM 5 折调优 F1: {[round(v, 4) for v in svm_f1s]}",
        f"均值 {np.mean(svm_f1s):.4f} ± {np.std(svm_f1s):.4f}",
        "",
        f"Welch t 检验: t = {t_stat:.4f}, p = {p_value:.6f}",
        "",
        f"结论: {'DistilBERT 显著优于 SVM (p < 0.05)' if p_value < 0.05 else '差异不显著 (p >= 0.05)'}",
        "",
        "说明: 两组均为清洗标签上同折划分的调优阈值 F1，"
        "SVM 为本次重跑的五折结果，非近似生成。",
    ]
    text = "\n".join(lines)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"保存 -> {OUT_MD}")
    print(text)


if __name__ == "__main__":
    main()
