# -*- coding: utf-8 -*-
# SoundInsight 在线 Demo（ModelScope 创空间版）
# 模型权重在启动时从 ModelScope 模型仓库自动下载（见 download_models 函数），
# 全部参数从 config.json 读取，无任何硬编码路径。
import json
import os
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gradio as gr
import numpy as np
import pandas as pd
import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
    CFG = json.load(f)

BIN_DIR = os.path.join(HERE, CFG.get("bin_model_dir", "sound_model"))
ML_DIR = os.path.join(HERE, CFG.get("multi_label_dir", "multi_label_model"))
MODEL_REPO_ID = CFG.get("model_repo_id", "")  # 用户建仓后填入
MODELSCOPE_API = ("https://modelscope.cn/api/v1/models/{repo}/repo"
                  "?FilePath={fname}")
MAX_LEN = int(CFG.get("max_len", 128))

FILES_BIN = ["config.json", "tokenizer.json", "tokenizer_config.json",
             "threshold.json", "model.safetensors"]
FILES_ML = ["config.json", "tokenizer.json", "tokenizer_config.json",
            "issue_labels.json", "model.safetensors"]


def download_models():
    """启动时从 ModelScope 模型仓库下载权重（已存在则跳过）。"""
    if not MODEL_REPO_ID:
        raise RuntimeError("config.json 中未填写 model_repo_id，"
                           "请先在 ModelScope 建仓并填入")
    for dname, files in [(BIN_DIR, FILES_BIN), (ML_DIR, FILES_ML)]:
        os.makedirs(dname, exist_ok=True)
        for fname in files:
            dst = os.path.join(dname, fname)
            if os.path.exists(dst) and os.path.getsize(dst) > 1000:
                continue
            r = requests.get(MODELSCOPE_API.format(
                repo=MODEL_REPO_ID, fname=f"{dname}/{fname}"),
                timeout=600, stream=True)
            if r.status_code != 200:
                raise RuntimeError(f"下载失败 {fname}: HTTP {r.status_code}")
            with open(dst, "wb") as fp:
                for chunk in r.iter_content(1 << 20):
                    fp.write(chunk)
            print(f"下载 {fname} -> {dname}", flush=True)


download_models()

device = torch.device("cpu")  # 创空间免费环境为 CPU
tok = DistilBertTokenizer.from_pretrained(BIN_DIR)
bin_model = DistilBertForSequenceClassification.from_pretrained(BIN_DIR)
bin_model.eval()
with open(os.path.join(BIN_DIR, "threshold.json"), encoding="utf-8") as f:
    THR = float(json.load(f)["threshold"])
ml_model = DistilBertForSequenceClassification.from_pretrained(ML_DIR)
ml_model.eval()
with open(os.path.join(ML_DIR, "issue_labels.json"), encoding="utf-8") as f:
    ISSUE_INFO = json.load(f)
print(f"模型加载完成 | threshold={THR:.4f}")


def single_predict(text):
    if not text or not text.strip():
        return "请输入英文评论"
    enc = tok(text.strip(), padding=True, truncation=True,
              max_length=MAX_LEN, return_tensors="pt")
    with torch.no_grad():
        prob = float(torch.softmax(bin_model(**enc).logits, -1)[0, 1])
        issues = torch.sigmoid(ml_model(**enc).logits)[0].numpy()
    label = "音质负面" if prob >= THR else "音质正常"
    hit = [ISSUE_INFO["names"][k] for k in range(len(issues))
           if issues[k] >= 0.5]
    issue_text = "；".join(hit) if hit else "无明显问题类别"
    return (f"{label}（音质负面概率 {prob:.1%}）\n问题归因：{issue_text}\n"
            f"（概率未经校准，仅供排序参考）")


def batch_analyze(file_obj):
    if file_obj is None:
        return "请先上传 CSV 文件", None
    try:
        df = pd.read_csv(file_obj.name, encoding="utf-8")
    except Exception as e:  # noqa: BLE001 - 反馈给用户
        return f"读取失败：{e}", None
    text_col = next((c for c in ("text", "reviewText", "review")
                     if c in df.columns), df.columns[0])
    texts = df[text_col].astype(str).tolist()
    probs = []
    with torch.no_grad():
        for b in range(0, len(texts), 32):
            enc = tok(texts[b:b + 32], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            probs.append(torch.softmax(bin_model(**enc).logits, -1)
                         [:, 1].numpy())
    probs = np.concatenate(probs)
    neg_idx = [i for i, p in enumerate(probs) if p >= THR]
    issue_counts = {name: 0 for name in ISSUE_INFO["names"]}
    if neg_idx:
        neg_texts = [texts[i] for i in neg_idx]
        ml_out = []
        with torch.no_grad():
            for b in range(0, len(neg_texts), 32):
                enc = tok(neg_texts[b:b + 32], padding=True, truncation=True,
                          max_length=MAX_LEN, return_tensors="pt")
                ml_out.append(torch.sigmoid(ml_model(**enc).logits).numpy())
        ml_pred = (np.vstack(ml_out) >= 0.5).astype(int)
        for k, name in enumerate(ISSUE_INFO["names"]):
            issue_counts[name] = int(ml_pred[:, k].sum())
    lines = [f"评论总数：{len(texts)}",
             f"音质差评：{len(neg_idx)}（{len(neg_idx) / len(texts):.2%}）",
             "音质问题分布："]
    for name, cnt in sorted(issue_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {name}：{cnt}")
    lines.append("")
    lines.append("差评示例：")
    for i in neg_idx[:5]:
        lines.append(f"- （{probs[i]:.1%}）{texts[i][:100]}")
    lines.append("")
    lines.append("（概率未经校准，仅供排序参考）")
    report_text = "\n".join(lines)
    report_path = os.path.join(HERE, "batch_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    return report_text, report_path


EDGE_CASES = [
    ("委婉表达", "评论在批评音质但用词缓和，不含负面关键词。",
     "Was expecting a deeper bass given the price point, but it is "
     "acceptable for casual listening.", "音质负面概率 95.4%",
     "模型对委婉差评识别存在挑战，当前召回率偏低"),
    ("中性比较", "评论以对比为主，同时提到优劣两面，难以二分。",
     "Not as loud as my previous pair, but the clarity is actually better.",
     "音质负面概率 0.1%", "模型倾向于保守判定，避免误报"),
    ("关键词误触", "命中音质关键词，但语义与音质缺陷无关。",
     "It sounds like a great deal, and shipping was fast.",
     "音质负面概率 0.1%", "LLM 复核已过滤大部分误报"),
    ("评分冲突", "评分与文字不一致，如五星但文字批评音质。",
     "Great product, though the bass is a little muddy.",
     "音质负面概率 98.1%", "以文字语义为准，评分仅作参考"),
    ("多语言", "非英文或中英混杂评论，当前模型未覆盖。",
     "La calidad del sonido es regular, esperaba más graves.",
     "音质负面概率 0.0%", "当前版本仅支持英文，多语言扩展为未来工作"),
    ("极短评论", "评论过短导致上下文不足。",
     "Meh.", "音质负面概率 0.0%", "短文本置信度低，建议人工复核"),
]


def edge_cases_md():
    lines = ["## 六类边界案例及模型表现", ""]
    for name, definition, sample, prob, note in EDGE_CASES:
        lines.append(f"### {name}")
        lines.append(f"定义：{definition}")
        lines.append(f"样例：{sample}")
        lines.append(f"预测：{prob}")
        lines.append(f"模型表现：{note}")
        lines.append("")
    lines.append("> 上述概率未经校准，仅供排序参考。")
    return "\n".join(lines)


EXAMPLES = [
    "The sound quality is terrible, the bass is muddy and there is "
    "constant static.",
    "Great battery life and very comfortable to wear.",
    "Sounds crackle and hiss constantly, completely unusable.",
]

with gr.Blocks(title="🔊 蓝牙耳机音质差评检测器") as demo:
    gr.Markdown("# 🔊 蓝牙耳机音质差评检测器")
    gr.Markdown("SoundInsight：音质差评自动识别 + 五类问题归因。"
                "项目地址：https://github.com/DaiYanQBZ95Doll/soundinsight")
    with gr.Tab("单条评论"):
        inp = gr.Textbox(label="英文评论", lines=4,
                         placeholder="Paste an English product review...")
        btn = gr.Button("检测")
        out = gr.Textbox(label="判定结果")
        btn.click(single_predict, inputs=inp, outputs=out)
        gr.Examples(EXAMPLES, inputs=inp)
    with gr.Tab("批量分析"):
        fup = gr.File(label="上传评论 CSV（含 text 列）")
        btn2 = gr.Button("生成洞察报告")
        out2 = gr.Textbox(label="报告摘要")
        dload = gr.File(label="下载报告文件")
        btn2.click(batch_analyze, inputs=fup, outputs=[out2, dload])
    with gr.Tab("边界案例"):
        gr.Markdown(edge_cases_md())

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
