# -*- coding: utf-8 -*-
"""W5：二分类 5 折交叉验证（v2 口径）。

与 v1 的区别（缺憾 A1-8 的处置）：
- v1 在**每一折内部**网格搜索阈值并报该阈值下的 F1 → 含**乐观偏置**；
- 本脚本**同时报两个口径**并区分：
  · `f1_fixed@0.6`：用 `val_v3_tune` 上选定的固定阈值 0.6 **不在折内做任何选择** → 无偏；
  · `f1_best_infold`：折内选阈值的 F1（与 v1 口径可比，**标注为偏乐观**）。

训练口径：与 v2 候选一致（`labeled_llm.csv`、seed 42、max_len 256、3 epoch、batch 16、lr 2e-5、
分层 5 折）。**不使用** val_v3 作为折内验证集，避免与主指标集重叠。

输出：`v2/w5_cv.json`（逐折指标 + 均值/标准差 + 波动率）。

用法：python v2_w5_cv.py [--folds 5]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import torch
from sklearn.metrics import precision_recall_fscore_support
from sklearn.model_selection import StratifiedKFold
from torch.optim import AdamW
from torch.utils.data import DataLoader, TensorDataset
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_w1_longtext import load_csv_texts  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_llm.csv")
BASE_MODEL = os.path.join(HERE, "sound_model")
OUT = os.path.join(HERE, "v2")
SEED, MAX_LEN, EPOCHS, BS, LR = 42, 256, 3, 16, 2e-5
FIXED_THR = 0.6          # 来自 val_v3_tune 的扫描结果（v2 调优档）
GRID = [round(0.05 * k, 2) for k in range(1, 20)]


def metrics(y, p, thr):
    pred = (p >= thr).astype(int)
    a, b, c, _ = precision_recall_fscore_support(y, pred, average="binary",
                                                 zero_division=0)
    return round(float(c), 4), round(float(a) * 100, 1), round(float(b) * 100, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    texts, labels = load_csv_texts(INPUT_CSV)
    print(f"device={device} | 样本 {len(texts)}，正例 {sum(labels)} | "
          f"max_len={MAX_LEN} epochs={EPOCHS} folds={args.folds}")
    tok = DistilBertTokenizer.from_pretrained(BASE_MODEL)
    skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=SEED)
    folds = []
    t0 = time.time()
    for k, (tr, va) in enumerate(skf.split(texts, labels), 1):
        tr_texts = [texts[i] for i in tr]
        va_texts = [texts[i] for i in va]
        y_va = np.array([labels[i] for i in va])
        enc = tok(tr_texts, truncation=True, max_length=MAX_LEN, padding=True,
                  return_tensors="pt")
        ds = TensorDataset(enc["input_ids"], enc["attention_mask"],
                           torch.tensor([labels[i] for i in tr]))
        dl = DataLoader(ds, batch_size=BS, shuffle=True)
        torch.manual_seed(SEED + k)
        model = DistilBertForSequenceClassification.from_pretrained(
            BASE_MODEL, num_labels=2).to(device)
        opt = AdamW(model.parameters(), lr=LR)
        for ep in range(EPOCHS):
            model.train()
            tot = 0.0
            for ids, att, y in dl:
                ids, att, y = ids.to(device), att.to(device), y.to(device)
                out = model(input_ids=ids, attention_mask=att, labels=y)
                out.loss.backward()
                opt.step()
                opt.zero_grad()
                tot += float(out.loss)
        model.eval()
        probs = []
        with torch.no_grad():
            for i in range(0, len(va_texts), 64):
                e = tok(va_texts[i:i + 64], truncation=True, max_length=MAX_LEN,
                        padding=True, return_tensors="pt").to(device)
                probs.append(torch.softmax(model(**e).logits, -1)[:, 1].cpu().numpy())
        p_va = np.concatenate(probs) if probs else np.zeros(0)

        f1_fixed, pr_f, rc_f = metrics(y_va, p_va, FIXED_THR)
        best = max(((thr,) + metrics(y_va, p_va, thr) for thr in GRID),
                   key=lambda t: t[1])
        folds.append({"fold": k, "n_val": len(va), "pos_val": int(y_va.sum()),
                      "f1_fixed@%.2f" % FIXED_THR: f1_fixed, "P_fixed": pr_f,
                      "R_fixed": rc_f,
                      "best_thr_infold": best[0], "f1_best_infold": best[1],
                      "P_best": best[2], "R_best": best[3]})
        print(f"[fold {k}] n_val={len(va)} pos={int(y_va.sum())} | "
              f"固定阈值{FIXED_THR}: F1 {f1_fixed} (P{pr_f}/R{rc_f}) | "
              f"折内最优 {best[0]}: F1 {best[1]}")

    fixed = [f["f1_fixed@%.2f" % FIXED_THR] for f in folds]
    bestf = [f["f1_best_infold"] for f in folds]
    summary = {
        "fixed_threshold": FIXED_THR,
        "f1_fixed_mean": round(float(np.mean(fixed)), 4),
        "f1_fixed_std": round(float(np.std(fixed, ddof=1)), 4),
        "f1_fixed_fluctuation_pct": round(float(np.std(fixed, ddof=1) / np.mean(fixed) * 100), 1),
        "f1_best_infold_mean": round(float(np.mean(bestf)), 4),
        "f1_best_infold_std": round(float(np.std(bestf, ddof=1)), 4),
        "note": ("`f1_fixed` 不在折内做任何选择，**无偏**；`f1_best_infold` 与 v1 口径可比但"
                 "**偏乐观**（v1 即 0.6234±0.0240，波动 3.9%）。验收线：波动 ≤5%（看无偏口径）。"),
    }
    print(f"\n[无偏] 固定阈值 {FIXED_THR}: {summary['f1_fixed_mean']} ± "
          f"{summary['f1_fixed_std']}（波动 {summary['f1_fixed_fluctuation_pct']}%）")
    print(f"[对照] 折内选阈值: {summary['f1_best_infold_mean']} ± "
          f"{summary['f1_best_infold_std']}")
    verdict = summary["f1_fixed_fluctuation_pct"] <= 5.0
    print(f"[DoD] CV 波动 ≤5% → {'通过' if verdict else '未通过'}")
    payload = {"gen": "[v2]", "protocol": "5 折分层 CV；同时报无偏（固定阈值）与折内选阈值两种口径",
               "max_len": MAX_LEN, "epochs": EPOCHS, "seed": SEED, "folds": folds,
               "summary": summary, "cv_stability_pass": verdict,
               "elapsed_min": round((time.time() - t0) / 60, 1)}
    with open(os.path.join(OUT, "w5_cv.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"[写出] v2/w5_cv.json（用时 {payload['elapsed_min']} 分钟）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
