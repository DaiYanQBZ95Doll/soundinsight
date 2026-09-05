# -*- coding: utf-8 -*-
# C1 长度分桶评估：val_v2 全量推理结果按字符长度分桶（<=64 / 65-128 / >128），
# 输出各桶 F1/P/R/Acc 与混淆矩阵，写入 length_bucket_eval.md。
import os
import sys

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP = os.path.join(HERE, "val_preds_dump.csv")
OUT_MD = os.path.join(HERE, "length_bucket_eval.md")

BUCKETS = [("<=64字符", 0, 64), ("65-128字符", 65, 128), (">128字符", 129, 10 ** 9)]


def main() -> None:
    df = pd.read_csv(DUMP, encoding="utf-8", keep_default_na=False)
    y, p = df["sound_negative"].to_numpy(), df["pred"].to_numpy()

    lines = ["# 长度分桶评估报告（length_bucket_eval.md）", "",
             "口径：冻结模型 + val_v2（20,000 条），阈值 0.9744，"
             "按评论字符数分桶。与 `results_summary.md` 冻结口径不冲突，"
             "本报告为同一验证集上的分桶视角。", ""]
    for name, lo, hi in BUCKETS:
        m = (df["len_chars"] >= lo) & (df["len_chars"] <= hi)
        yb, pb = y[m], p[m]
        p_, r_, f1, _ = precision_recall_fscore_support(
            yb, pb, average="binary", zero_division=0)
        tp = int(((yb == 1) & (pb == 1)).sum())
        fp = int(((yb == 0) & (pb == 1)).sum())
        fn = int(((yb == 1) & (pb == 0)).sum())
        tn = int(((yb == 0) & (pb == 0)).sum())
        acc = (tp + tn) / len(yb)
        lines += [
            f"## {name}（n={len(yb)}，正例 {int(yb.sum())}，"
            f"占比 {len(yb)/len(df)*100:.1f}%）",
            "",
            f"- Acc={acc:.4f}  Precision={p_:.4f}  Recall={r_:.4f}  F1={f1:.4f}",
            f"- TP={tp}  FP={fp}  FN={fn}  TN={tn}",
            f"- 模型判正率：{pb.mean()*100:.2f}%（真实正例率 {yb.mean()*100:.2f}%）",
            "",
        ]

    text = "\n".join(lines)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
