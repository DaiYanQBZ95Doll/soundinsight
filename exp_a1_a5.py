# -*- coding: utf-8 -*-
"""消融 A1（闸门预筛的贡献）与 A5（概率标定）。

A1：闸门预筛带来什么？
    所有 LLM 正例（1,280）**全部落在闸门内**（实测），故闸门外样本几乎全为负例。
    做法：用本文方法给一批**闸门外**样本打分 → 得到闸门外的触发（FP）率 →
          按真实比例（闸门外 87,071 条）外推 → 与"不开闸门"的精确率对比。
A5：温度标定 —— 在 val 上拟合温度 T（最小化 NLL）→ 在 test 上看 ECE/Brier 变化。

产物：v2/exp_a1_gate.json、v2/exp_a5_calibration.json
"""
from __future__ import annotations

import csv
import json
import math
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

import torch  # noqa: E402
from transformers import (DistilBertForSequenceClassification,  # noqa: E402
                          DistilBertTokenizer)

MODEL = "v2/model_thesis_hard"
SAMPLE_OUT = 2000


def ece(y, p, bins=10):
    tot, e = len(p), 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, q in enumerate(p) if (lo <= q < hi) or (b == bins - 1 and q == 1.0)]
        if not idx:
            continue
        conf = sum(p[i] for i in idx) / len(idx)
        acc = sum(y[i] for i in idx) / len(idx)
        e += (len(idx) / tot) * abs(acc - conf)
    return e


def brier(y, p):
    return sum((pi - yi) ** 2 for yi, pi in zip(y, p)) / max(1, len(p))


def main() -> int:
    sp = json.load(open(os.path.join(HERE, "v2", "thesis_split.json"), encoding="utf-8"))
    texts, labels = {}, {}
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            texts[i] = r["text"]
            labels[i] = 1 if str(r.get("sound_negative_llm")) == "1" else 0

    import importlib.util
    spec = importlib.util.spec_from_file_location("g", os.path.join(HERE, "audio_gate.py"))
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    gate_in = [i for i in texts if g.gate(texts[i])]
    gate_out = [i for i in texts if not g.gate(texts[i])]
    pos_out = sum(labels[i] for i in gate_out)
    print(f"  闸门内 {len(gate_in):,}（正例 {sum(labels[i] for i in gate_in)}）｜"
          f"闸门外 {len(gate_out):,}（**正例 {pos_out}**）")

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = DistilBertTokenizer.from_pretrained(os.path.join(HERE, MODEL))
    model = DistilBertForSequenceClassification.from_pretrained(
        os.path.join(HERE, MODEL)).to(dev).eval()

    def score(items, bs=64):
        out = []
        with torch.no_grad():
            for b in range(0, len(items), bs):
                e = tok([texts[i] for i in items[b:b + bs]], padding=True, truncation=True,
                        max_length=256, return_tensors="pt")
                e = {k: v.to(dev) for k, v in e.items()}
                out += torch.softmax(model(**e).logits, -1)[:, 1].cpu().tolist()
        return out

    # ---------- A5：温度标定（用 val 拟合 T） ----------
    val_idx = sp["row_index"]["val"]
    test_idx = sp["row_index"]["test"]
    pv = [float(v) for v in json.load(open(os.path.join(HERE, "v2", "exp_mhard_val.json"),
                                           encoding="utf-8")).values()]
    pt = [float(v) for v in json.load(open(os.path.join(HERE, "v2", "exp_mhard_test.json"),
                                           encoding="utf-8")).values()]
    yv = [labels[i] for i in val_idx]
    yt = [labels[i] for i in test_idx]

    def logit(p):
        p = min(max(p, 1e-6), 1 - 1e-6)
        return math.log(p / (1 - p))

    best_T, best_nll = 1.0, 1e18
    for T in [0.5 + 0.05 * k for k in range(41)]:      # 0.50 – 2.50
        nll = 0.0
        for y, p in zip(yv, pv):
            z = logit(p) / T
            q = 1 / (1 + math.exp(-z))
            nll -= math.log(q if y == 1 else 1 - q)
        nll /= len(yv)
        if nll < best_nll:
            best_T, best_nll = T, nll
    pt_cal = [1 / (1 + math.exp(-logit(p) / best_T)) for p in pt]
    a5 = {"T": round(best_T, 3), "val_nll_before": round(best_nll, 4),
          "test_ece_before": round(ece(yt, pt), 4), "test_ece_after": round(ece(yt, pt_cal), 4),
          "test_brier_before": round(brier(yt, pt), 4),
          "test_brier_after": round(brier(yt, pt_cal), 4)}
    print(f"\n[A5 温度标定] T={a5['T']}｜ECE {a5['test_ece_before']} → **{a5['test_ece_after']}**"
          f"｜Brier {a5['test_brier_before']} → {a5['test_brier_after']}")
    json.dump(a5, open(os.path.join(HERE, "v2", "exp_a5_calibration.json"), "w",
                       encoding="utf-8"), ensure_ascii=False, indent=2)

    # ---------- A1：闸门预筛 ----------
    rng = random.Random(42)
    sample = rng.sample(gate_out, min(SAMPLE_OUT, len(gate_out)))
    ps = score(sample)
    fire_in = sum(1 for p in pt if p >= 0.5)
    tp_in = sum(1 for y, p in zip(yt, pt) if y == 1 and p >= 0.5)
    fire_out_rate = sum(1 for p in ps if p >= 0.5) / len(ps)
    fp_out_est = fire_out_rate * len(gate_out)
    prec_with = tp_in / fire_in if fire_in else 0.0
    prec_without = tp_in / (fire_in + fp_out_est) if (fire_in + fp_out_est) else 0.0
    a1 = {"gate_out_n": len(gate_out), "gate_out_pos": pos_out,
          "gate_in_pos": sum(labels[i] for i in gate_in),
          "sample_out_n": len(sample), "fire_rate_out": round(fire_out_rate, 4),
          "fp_out_est_scaled": round(fp_out_est, 1),
          "precision_with_gate": round(prec_with, 4),
          "precision_without_gate": round(prec_without, 4),
          "note": ("闸门外正例数为 0（实测：全部 1,280 个 LLM 正例都在闸门内），"
                   "故闸门外触发全为 FP；外推按闸门外样本的真实比例缩放")}
    print(f"\n[A1 闸门] 闸门外抽样 {len(sample)}：触发率 {fire_out_rate*100:.1f}% → "
          f"外推 FP ≈ {fp_out_est:,.0f} 条")
    print(f"  精确率：开闸门 **{prec_with*100:.1f}%** vs 不开闸门 **{prec_without*100:.1f}%**")
    json.dump(a1, open(os.path.join(HERE, "v2", "exp_a1_gate.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("  [写出] v2/exp_a1_gate.json、v2/exp_a5_calibration.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
