# -*- coding: utf-8 -*-
# check_edge_cases.py —— 核验"边界案例"页签里 6 条硬编码概率与冻结模型实测是否一致
import json
import os
import sys

import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
BIN_MODEL = os.path.join(HERE, "sound_model")
ML_MODEL = os.path.join(HERE, "multi_label_model")

# 与 demo_sound_v2.py 的 EDGE_CASES 保持一致的 6 条（名称/样例/页面显示值）
CASES = [
    ("委婉表达", "Was expecting a deeper bass given the price point, but it is "
                 "acceptable for casual listening.", "95.4%"),
    ("中性比较", "Not as loud as my previous pair, but the clarity is actually better.",
     "0.1%"),
    ("关键词误触", "It sounds like a great deal, and shipping was fast.", "0.1%"),
    ("评分冲突", "Great product, though the bass is a little muddy.", "98.1%"),
    ("多语言", "La calidad del sonido es regular, esperaba más graves.", "0.0%"),
    ("极短评论", "Meh.", "0.0%"),
]

with open(os.path.join(BIN_MODEL, "threshold.json"), encoding="utf-8") as f:
    THR = float(json.load(f)["threshold"])
with open(os.path.join(HERE, "multi_label_model", "issue_labels.json"),
          encoding="utf-8") as f:
    ISSUES = json.load(f)["names"]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tok = DistilBertTokenizer.from_pretrained(BIN_MODEL)
bin_model = DistilBertForSequenceClassification.from_pretrained(
    BIN_MODEL).to(device).eval()
ml_model = DistilBertForSequenceClassification.from_pretrained(
    ML_MODEL).to(device).eval()

print(f"阈值 {THR:.4f}\n")
print(f"{'类别':<8}{'页面显示':<10}{'实测概率':<12}{'判定':<8}归因（≥0.5）")
print("-" * 66)
bad = []
for name, text, shown in CASES:
    enc = tok(text, padding=True, truncation=True, max_length=128,
              return_tensors="pt")
    enc = {k: v.to(device) for k, v in enc.items()}
    with torch.no_grad():
        p = float(torch.softmax(bin_model(**enc).logits, -1)[0, 1])
        ip = torch.sigmoid(ml_model(**enc).logits)[0].cpu().numpy()
    hit = [ISSUES[k] for k in range(len(ISSUES)) if ip[k] >= 0.5]
    verdict = "负面" if p >= THR else "正常"
    print(f"{name:<8}{shown:<10}{p:.1%}{'':<7}{verdict:<8}{'、'.join(hit) or '—'}")
    shown_v = float(shown.rstrip('%')) / 100
    if abs(shown_v - p) > 0.005:
        bad.append((name, shown, f"{p:.1%}"))

print("\n不一致项：")
if bad:
    for name, shown, actual in bad:
        print(f"  ✗ {name}: 页面显示 {shown} → 实测 {actual}")
else:
    print("  无（6 条全部与实测一致）")
