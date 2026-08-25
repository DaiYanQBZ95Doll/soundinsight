# -*- coding: utf-8 -*-
# 本脚本用于生成 Demo 推理演示截图：对三条测试评论推理，打印判定与概率，并绘制概率柱状图保存为 demo_output.png。
"""Capture demo inference output: 3 test reviews -> labels, probabilities, chart."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE, "sound_model")
OUT_PNG = os.path.join(BASE, "demo_output.png")

REVIEWS = [
    "The sound quality is terrible, the bass is muddy and there is constant "
    "static.",
    "Great battery life and very comfortable to wear.",
    "Sounds crackle and hiss constantly, completely unusable.",
]

tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
model = DistilBertForSequenceClassification.from_pretrained(MODEL_DIR)
model.eval()
with open(os.path.join(MODEL_DIR, "threshold.json"), encoding="utf-8") as f:
    THR = float(json.load(f)["threshold"])

results = []
print("SoundInsight Demo 推理结果")
print(f"判定阈值: {THR:.2f}")
for i, text in enumerate(REVIEWS, 1):
    enc = tok(text, padding=True, truncation=True, max_length=128,
              return_tensors="pt")
    with torch.no_grad():
        prob = float(torch.softmax(model(**enc).logits, -1)[0, 1])
    label = "音质负面" if prob >= THR else "音质正常"
    results.append((text, label, prob))
    print(f"评论 {i}: {text}")
    print(f"  预测: {label} | 音质负面概率: {prob:.1%}")

labels = ["评论1\n低音浑浊+杂音", "评论2\n续航与舒适", "评论3\n爆音+嘶嘶声"]
probs = [r[2] for r in results]
heights = [max(p * 100, 1.2) if p > 0 else p * 100 for p in probs]
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
fig, ax = plt.subplots(figsize=(7, 4.5))
bars = ax.bar(labels, heights,
              color=["#c0392b", "#27ae60", "#c0392b"])
ax.axhline(y=THR * 100, color="gray", linestyle="--", linewidth=1)
ax.text(2.42, THR * 100 + 1.5, f"阈值 {THR:.0%}", color="gray", fontsize=9)
for b, p in zip(bars, probs):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f"{p:.1%}",
            ha="center", fontsize=11)
ax.set_ylim(0, 105)
ax.set_ylabel("音质负面概率 (%)")
ax.set_title("SoundInsight 三条测试评论的音质负面概率")
fig.tight_layout()
plt.savefig(OUT_PNG, dpi=150)
print(f"图表已保存: {OUT_PNG}")
