# -*- coding: utf-8 -*-
# 本脚本是 SoundInsight 一键洞察 Agent：输入评论 CSV，自动完成音质差评识别、
# 问题归因与统计，输出洞察报告（markdown）并打印摘要。一条命令即可运行。
import argparse
import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
BIN_MODEL = os.path.join(HERE, "sound_model")
ML_MODEL = os.path.join(HERE, "multi_label_model")
BATCH = 64
MAX_LEN = 128


def load():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = DistilBertTokenizer.from_pretrained(BIN_MODEL)
    bin_model = DistilBertForSequenceClassification.from_pretrained(
        BIN_MODEL).to(device)
    bin_model.eval()
    with open(os.path.join(BIN_MODEL, "threshold.json"), encoding="utf-8") as f:
        thr = float(json.load(f)["threshold"])
    ml_model = DistilBertForSequenceClassification.from_pretrained(
        ML_MODEL).to(device)
    ml_model.eval()
    with open(os.path.join(ML_MODEL, "issue_labels.json"), encoding="utf-8") as f:
        issue_info = json.load(f)
    return device, tok, bin_model, thr, ml_model, issue_info


def predict_probs(model, tok, texts, device):
    probs = []
    with torch.no_grad():
        for b in range(0, len(texts), BATCH):
            enc = tok(texts[b:b + BATCH], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            logits = model(**enc).logits
            probs.append(torch.softmax(logits, -1)[:, 1].cpu().numpy())
    return np.concatenate(probs)


def predict_multilabel(model, tok, texts, device):
    out = []
    with torch.no_grad():
        for b in range(0, len(texts), BATCH):
            enc = tok(texts[b:b + BATCH], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            out.append(torch.sigmoid(model(**enc).logits).cpu().numpy())
    return np.vstack(out)


def analyze(csv_path: str) -> str:
    device, tok, bin_model, thr, ml_model, issue_info = load()
    df = pd.read_csv(csv_path, encoding="utf-8")
    text_col = next((c for c in ("text", "reviewText", "review")
                     if c in df.columns), df.columns[0])
    texts = df[text_col].astype(str).tolist()
    print(f"分析 {len(texts)} 条评论 (device={device})")

    probs = predict_probs(bin_model, tok, texts, device)
    df["sound_negative_prob"] = probs
    df["is_sound_negative"] = (probs >= thr).astype(int)

    n = len(df)
    n_neg = int(df["is_sound_negative"].sum())
    neg_idx = df[df["is_sound_negative"] == 1].index.tolist()

    issue_cols = issue_info["columns"]
    issue_names = issue_info["names"]
    issue_counts = {k: 0 for k in issue_names}
    if neg_idx:
        neg_texts = [texts[i] for i in neg_idx]
        ml_probs = predict_multilabel(ml_model, tok, neg_texts, device)
        ml_pred = (ml_probs >= 0.5).astype(int)
        for k, name in enumerate(issue_names):
            issue_counts[name] = int(ml_pred[:, k].sum())
        df.loc[neg_idx, [c.replace("_llm", "") for c in issue_cols]] = ml_pred

    rating_col = next((c for c in ("rating", "overall", "score")
                       if c in df.columns), None)
    if rating_col is not None:
        avg_rating = float(pd.to_numeric(df[rating_col],
                                         errors="coerce").mean())
    else:
        avg_rating = float("nan")

    lines = []
    lines.append("# SoundInsight 音质洞察报告")
    lines.append(f"生成时间：{datetime.now():%Y-%m-%d %H:%M}")
    lines.append(f"评论总数：{n}")
    lines.append(f"音质差评数：{n_neg}（占比 {n_neg / n:.2%}）")
    if not np.isnan(avg_rating):
        lines.append(f"平均评分：{avg_rating:.2f}")
    lines.append("")
    lines.append("## 音质问题分布")
    for name, cnt in sorted(issue_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {name}：{cnt} 条")
    lines.append("")
    lines.append("## 差评示例")
    for i in neg_idx[:5]:
        lines.append(f"- （{probs[i]:.1%}）{texts[i][:120]}")
    lines.append("")
    lines.append("## 改进建议")
    top = sorted(issue_counts.items(), key=lambda x: -x[1])[0]
    if top[1] > 0:
        lines.append(f"优先处理占比最高的音质问题：{top[0]}，"
                     f"建议结合具体评论样例定位到产品批次或固件版本。")
    else:
        lines.append("未检测到明显音质问题，建议维持当前品控。")
    report = "\n".join(lines)

    out_path = os.path.join(HERE, "insight_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"报告已保存 -> {out_path}")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="SoundInsight 一键洞察 Agent")
    ap.add_argument("--csv", required=True, help="待分析评论 CSV 路径")
    args = ap.parse_args()
    report = analyze(args.csv)
    print("\n" + report)


if __name__ == "__main__":
    main()
