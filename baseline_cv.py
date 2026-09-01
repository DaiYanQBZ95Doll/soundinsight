# -*- coding: utf-8 -*-
# 本脚本用于基线对比与交叉验证：对音质负面标签跑 5 折分层交叉验证乘 3 个随机种子，
# 对比全判正常基线、TF-IDF+逻辑回归、TF-IDF+线性SVM，输出均值与标准差。
import os
import sys

import numpy as np
import pandas as pd
from scipy import sparse as scipy_sparse
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, f1_score, precision_recall_curve)
from sklearn.model_selection import StratifiedKFold
from sklearn.svm import LinearSVC

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_expanded.csv")
SEEDS = [42, 7, 2024]
N_FOLDS = 5
MAX_TRAIN_ROWS = 40000  # 每折训练集最多用 4 万行，控制耗时


def best_threshold_f1(y_true, probs):
    precision, recall, thresholds = precision_recall_curve(y_true, probs)
    f1s = 2 * precision * recall / (precision + recall + 1e-12)
    i = int(np.argmax(f1s))
    return float(f1s[i]), float(thresholds[i]) if i < len(thresholds) else 0.5


def subset(X, idx):
    if scipy_sparse.issparse(X):
        return X[idx]
    return [X[i] for i in idx]


def evaluate(name, X, y, make_model):
    accs, f1_05, f1_best = [], [], []
    for seed in SEEDS:
        skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed)
        for tr, va in skf.split(np.arange(len(y)), y):
            if len(tr) > MAX_TRAIN_ROWS:
                tr = np.random.RandomState(seed).choice(
                    tr, size=MAX_TRAIN_ROWS, replace=False)
            model = make_model()
            model.fit(subset(X, tr), [y[i] for i in tr])
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(subset(X, va))[:, 1]
                pred = (probs >= 0.5).astype(int)
            else:
                probs = model.decision_function(subset(X, va))
                pred = model.predict(subset(X, va))
            yva = np.asarray([y[i] for i in va])
            accs.append(accuracy_score(yva, pred))
            f1_05.append(f1_score(yva, pred, zero_division=0))
            fb, _ = best_threshold_f1(yva, probs)
            f1_best.append(fb)
    print(f"{name}: acc={np.mean(accs):.4f}±{np.std(accs):.4f} | "
          f"f1@0.5={np.mean(f1_05):.4f}±{np.std(f1_05):.4f} | "
          f"f1_best={np.mean(f1_best):.4f}±{np.std(f1_best):.4f}")


def main() -> None:
    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    X = df["text"].astype(str).tolist()
    y = df["sound_negative"].astype(int).tolist()
    print(f"数据: {len(X)} 行 | 正例 {sum(y)} ({sum(y) / len(y):.2%})")

    evaluate("dummy(全判正常)", X, y,
             lambda: DummyClassifier(strategy="most_frequent"))

    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=50000,
                          sublinear_tf=True)
    Xv = vec.fit_transform(X)
    print(f"TF-IDF 特征矩阵: {Xv.shape}")

    def lr():
        return LogisticRegression(max_iter=1000, C=1.0)

    def svc():
        return LinearSVC(C=1.0, max_iter=2000)

    evaluate("TF-IDF+逻辑回归", Xv, y, lr)
    evaluate("TF-IDF+线性SVM", Xv, y, svc)


if __name__ == "__main__":
    main()
