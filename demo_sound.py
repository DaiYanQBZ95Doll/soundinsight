# -*- coding: utf-8 -*-
# 本脚本是 Gradio 交互演示：加载微调模型，输入英文评论，输出音质负面判定与概率。
"""Step 3: Gradio demo - Bluetooth earphone sound-quality complaint detector."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gradio as gr
import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sound_model")
tok = DistilBertTokenizer.from_pretrained(BASE)
model = DistilBertForSequenceClassification.from_pretrained(BASE)
model.eval()
with open(os.path.join(BASE, "threshold.json"), encoding="utf-8") as f:
    THRESHOLD = float(json.load(f)["threshold"])
print(f"loaded model from {BASE} | decision threshold={THRESHOLD:.3f}")


def predict(text: str) -> str:
    if not text or not text.strip():
        return "请输入英文评论"
    enc = tok(text.strip(), padding=True, truncation=True, max_length=128,
              return_tensors="pt")
    with torch.no_grad():
        logits = model(**enc).logits
    prob = float(torch.softmax(logits, -1)[0, 1])
    label = "音质负面" if prob >= THRESHOLD else "音质正常"
    return f"{label}（音质负面概率 {prob:.1%}，阈值 {THRESHOLD:.2f}）"


demo = gr.Interface(
    fn=predict,
    inputs=gr.Textbox(label="英文评论", lines=4,
                      placeholder="Paste an English product review here..."),
    outputs=gr.Textbox(label="判定结果"),
    title="🔊 蓝牙耳机音质差评检测器",
    description=("DistilBERT 二分类模型，基于 5000 条真实 Amazon Electronics "
                 "评论微调（epochs=3, batch=16, lr=2e-5）。"),
    examples=[
        ["The sound quality is terrible, the bass is muddy and there is "
         "constant static."],
        ["Great battery life and very comfortable fit."],
        ["Sounds crackle and hiss constantly, completely unusable."],
    ],
)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
