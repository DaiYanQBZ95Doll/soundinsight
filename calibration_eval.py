# -*- coding: utf-8 -*-
# C3 校准评估：10 等宽置信箱 ECE + 可靠性曲线 calibration_curve.png，
# 写入 calibration_eval.md。
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP = os.path.join(HERE, "val_preds_dump.csv")
OUT_MD = os.path.join(HERE, "calibration_eval.md")
OUT_PNG = os.path.join(HERE, "calibration_curve.png")


def main() -> None:
    df = pd.read_csv(DUMP, encoding="utf-8", keep_default_na=False)
    y = df["sound_negative"].to_numpy()
    prob = df["prob"].to_numpy()
    n = len(y)

    edges = np.linspace(0.0, 1.0, 11)
    lines = ["# 校准评估报告（calibration_eval.md）", "",
             "口径：冻结模型 + val_v2（20,000 条），10 个等宽置信箱，"
             "ECE = Σ(n_k/N)·|acc_k - conf_k|。", "",
             "| 置信区间 | n | 正例数 | 平均置信度 | 正例率 | 偏差 |",
             "|---|---|---|---|---|---|"]
    ece = 0.0
    accs, confs, ws = [], [], []
    for i in range(10):
        lo, hi = edges[i], edges[i + 1]
        m = (prob >= lo) & (prob < hi) if i < 9 else (prob >= lo) & (prob <= hi)
        nk = int(m.sum())
        if nk == 0:
            lines.append(f"| [{lo:.1f},{hi:.1f}) | 0 | — | — | — | — |")
            continue
        yk = y[m]
        conf = float(prob[m].mean())
        acc = float(yk.mean())
        ece += (nk / n) * abs(acc - conf)
        accs.append(acc)
        confs.append(conf)
        ws.append(nk / n)
        lines.append(f"| [{lo:.1f},{hi:.1f}) | {nk} | {int(yk.sum())} | "
                     f"{conf:.3f} | {acc:.3f} | {acc - conf:+.3f} |")
    lines += ["", f"**ECE(10箱) = {ece:.4f}**", "",
              "如实解读：整体 ECE 看似很小，是因为 97% 的样本落在 [0,0.1) 箱"
              "（真实负例率 0.999），该箱权重稀释了决策区间的偏差。"
              "在决策相关区间，模型概率显著过度自信："
              "[0.8,0.9) 置信 0.854 vs 实际正例率 0.229；"
              "[0.9,1.0) 置信 0.975 vs 实际正例率 0.555。"
              "结论：概率值不可当作真实概率解释，产品 UI 不应展示\"负面概率 97%\""
              "式表述；决策应基于阈值与置信分层，而非原始概率数值。", ""]
    text = "\n".join(lines)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)

    plt.figure(figsize=(6, 5))
    plt.plot([0, 1], [0, 1], "k--", lw=1, label="Perfect calibration")
    plt.plot(confs, accs, "o-", lw=2, label=f"Model (ECE={ece:.4f})")
    plt.xlabel("Mean predicted confidence")
    plt.ylabel("Observed positive rate")
    plt.title("Reliability Curve (val_v2, 10 bins)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=150)
    print(f"saved -> {OUT_PNG}")


if __name__ == "__main__":
    main()
