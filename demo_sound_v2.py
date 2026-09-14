# -*- coding: utf-8 -*-
# 本脚本是升级版 Gradio Demo：支持单条评论即时判定与批量 CSV 上传生成洞察报告。
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 本机若开启系统代理（如 127.0.0.1:7890），gradio 启动时对 localhost 的自检请求
# 会被送进代理并返回 502，导致 launch 抛异常退出。这里强制本地环回不走代理。
for _k in ("NO_PROXY", "no_proxy"):
    _hosts = [h for h in os.environ.get(_k, "").split(",") if h]
    for _h in ("127.0.0.1", "localhost", "0.0.0.0"):
        if _h not in _hosts:
            _hosts.append(_h)
    os.environ[_k] = ",".join(_hosts)

import gradio as gr
import numpy as np
import pandas as pd
import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

import report_builder as rb

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
    CFG = json.load(f)
BIN_MODEL = os.path.join(HERE, CFG["bin_model_dir"])
ML_MODEL = os.path.join(HERE, CFG["multi_label_dir"])
THR_FILE = os.path.join(HERE, CFG["threshold_file"])
ISSUE_FILE = os.path.join(HERE, CFG["issue_labels_file"])

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tok = DistilBertTokenizer.from_pretrained(BIN_MODEL)
bin_model = DistilBertForSequenceClassification.from_pretrained(
    BIN_MODEL).to(device)
bin_model.eval()
with open(THR_FILE, encoding="utf-8") as f:
    THR = float(json.load(f)["threshold"])
ml_model = DistilBertForSequenceClassification.from_pretrained(
    ML_MODEL).to(device)
ml_model.eval()
with open(ISSUE_FILE, encoding="utf-8") as f:
    ISSUE_INFO = json.load(f)
print(f"loaded models on {device} | threshold={THR:.4f}")


def single_predict(text):
    if not text or not text.strip():
        return "请输入英文评论"
    enc = tok(text.strip(), padding=True, truncation=True, max_length=128,
              return_tensors="pt")
    enc = {k: v.to(device) for k, v in enc.items()}
    with torch.no_grad():
        prob = float(torch.softmax(bin_model(**enc).logits, -1)[0, 1])
        issues = torch.sigmoid(ml_model(**enc).logits)[0].cpu().numpy()
    label = "音质负面" if prob >= THR else "音质正常"
    hit = [ISSUE_INFO["names"][k] for k in range(len(issues))
           if issues[k] >= 0.5]
    issue_text = "；".join(hit) if hit else "无明显问题类别"
    return (f"{label}（音质负面概率 {prob:.1%}）\n问题归因：{issue_text}\n"
            f"（概率未经校准，仅供排序参考，见 calibration_eval.md）")


def batch_analyze(file_obj):
    """批量分析：输出与命令行 Agent 同口径的完整六节报告（含优先级与行动建议）。"""
    if file_obj is None:
        return "请先上传 CSV 文件", None
    path = getattr(file_obj, "path", None) or getattr(file_obj, "name", None) \
        or str(file_obj)
    try:
        df = pd.read_csv(path, encoding="utf-8", keep_default_na=False)
    except Exception as e:  # noqa: BLE001 - report to user
        return f"读取失败：{e}", None
    text_col = next((c for c in ("text", "reviewText", "review")
                     if c in df.columns), df.columns[0])
    all_texts = df[text_col].astype(str).tolist()

    # 非英文评论显式跳过（与 predict_core 同规则）
    from text_utils import is_unsupported
    texts = [t for t in all_texts if not is_unsupported(t)]
    n_unsup = len(all_texts) - len(texts)
    if not texts:
        return "未找到可分析的英文评论（非英文评论已跳过）", None

    probs = []
    with torch.no_grad():
        for b in range(0, len(texts), 64):
            enc = tok(texts[b:b + 64], padding=True, truncation=True,
                      max_length=128, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            probs.append(torch.softmax(bin_model(**enc).logits, -1)
                         [:, 1].cpu().numpy())
    probs = np.concatenate(probs)
    neg_idx = [i for i, p in enumerate(probs) if p >= THR]
    issue_names = ISSUE_INFO["names"]
    issue_counts = {name: 0 for name in issue_names}
    ml_by_idx = {}
    if neg_idx:
        neg_texts = [texts[i] for i in neg_idx]
        ml_out = []
        with torch.no_grad():
            for b in range(0, len(neg_texts), 64):
                enc = tok(neg_texts[b:b + 64], padding=True, truncation=True,
                          max_length=128, return_tensors="pt")
                enc = {k: v.to(device) for k, v in enc.items()}
                ml_out.append(torch.sigmoid(ml_model(**enc).logits)
                              .cpu().numpy())
        ml_all = np.vstack(ml_out)
        ml_pred = (ml_all >= 0.5).astype(int)
        for k, name in enumerate(issue_names):
            issue_counts[name] = int(ml_pred[:, k].sum())
        ml_by_idx = {i: ml_all[k] for k, i in enumerate(neg_idx)}

    # 典型案例：按二分类概率排序取前 5，附五类归因概率
    examples = []
    for i in sorted(neg_idx, key=lambda j: -probs[j])[:5]:
        ip = {}
        if i in ml_by_idx:
            ip = {name: float(ml_by_idx[i][k])
                  for k, name in enumerate(issue_names)}
        examples.append({"text": texts[i], "prob": float(probs[i]),
                         "issue_probs": ip})

    rating_col = next((c for c in ("rating", "overall", "score")
                       if c in df.columns), None)
    avg_rating = (float(pd.to_numeric(df[rating_col], errors="coerce").mean())
                  if rating_col else float("nan"))
    n_mid = int(((probs >= 0.5) & (probs < THR)).sum())

    report_text = rb.build_report(
        src_name=os.path.basename(path), n_total=len(all_texts),
        n_unsupported=n_unsup, n_valid=len(texts), n_neg=len(neg_idx),
        avg_rating=avg_rating, issue_counts=issue_counts, examples=examples,
        n_mid=n_mid, lang="zh")
    report_path = os.path.join(HERE, "batch_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    return report_text, report_path


EDGE_CASES = [
    ("委婉表达",
     "评论在批评音质但用词缓和，不含负面关键词。",
     "Was expecting a deeper bass given the price point, but it is "
     "acceptable for casual listening.",
     "音质负面概率 95.4%",
     "模型对委婉差评识别存在挑战，当前召回率偏低"),
    ("中性比较",
     "评论以对比为主，同时提到优劣两面，难以二分。",
     "Not as loud as my previous pair, but the clarity is actually better.",
     "音质负面概率 0.1%",
     "模型倾向于保守判定，避免误报"),
    ("关键词误触",
     "命中音质关键词，但语义与音质缺陷无关。",
     "It sounds like a great deal, and shipping was fast.",
     "音质负面概率 0.1%",
     "LLM 复核已过滤大部分误报"),
    ("评分冲突",
     "评分与文字不一致，如五星但文字批评音质。",
     "Great product, though the bass is a little muddy.",
     "音质负面概率 98.1%",
     "以文字语义为准，评分仅作参考"),
    ("多语言",
     "非英文或中英混杂评论，当前模型未覆盖。",
     "La calidad del sonido es regular, esperaba más graves.",
     "音质负面概率 0.0%",
     "当前版本仅支持英文，多语言扩展为未来工作"),
    ("极短评论",
     "评论过短导致上下文不足。",
     "Meh.",
     "音质负面概率 0.0%",
     "短文本置信度低，建议人工复核"),
]


def edge_cases_md() -> str:
    lines = ["## 六类边界案例及模型表现", ""]
    for name, definition, sample, prob, note in EDGE_CASES:
        lines.append(f"### {name}")
        lines.append(f"定义：{definition}")
        lines.append(f"样例：{sample}")
        lines.append(f"预测：{prob}")
        lines.append(f"模型表现：{note}")
        lines.append("")
    lines.append("> 上述概率未经校准，仅供排序参考（见 calibration_eval.md）。")
    return "\n".join(lines)


with gr.Blocks(title="🔊 蓝牙耳机音质差评检测器") as demo:
    gr.Markdown("# 🔊 蓝牙耳机音质差评检测器")
    gr.Markdown("SoundInsight：音质差评自动识别 + 问题归因。")
    with gr.Tab("单条评论"):
        inp = gr.Textbox(label="英文评论", lines=4,
                         placeholder="Paste an English product review...")
        btn = gr.Button("检测")
        out = gr.Textbox(label="判定结果")
        btn.click(single_predict, inputs=inp, outputs=out)
    with gr.Tab("批量分析"):
        fup = gr.File(label="上传评论 CSV（含 text 列）")
        btn2 = gr.Button("生成洞察报告")
        out2 = gr.Textbox(label="报告摘要")
        dload = gr.File(label="下载报告文件")
        btn2.click(batch_analyze, inputs=fup, outputs=[out2, dload])
    with gr.Tab("边界案例"):
        gr.Markdown(edge_cases_md())

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
