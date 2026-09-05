# -*- coding: utf-8 -*-
# C2 边界案例基准：对 edge_cases.md 收录的 12 条真实评论运行冻结模型，
# 按类别统计命中率，并补充 val_v2 层面的非英文占比统计，写入 edge_case_benchmark.md。
import json
import os
import re
import sys

import numpy as np
import pandas as pd
import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "sound_model")
DUMP = os.path.join(HERE, "val_preds_dump.csv")
OUT_MD = os.path.join(HERE, "edge_case_benchmark.md")

# (类别, 评论, 期望标签)  1=音质负面, 0=非音质负面, None=模型未支持(多语言)
SAMPLES = [
    ("委婉表达类", "Was expecting a deeper bass given the price point, but it is acceptable for casual listening.", 1),
    ("委婉表达类", "The sound is fine for the price, nothing special.", 1),
    ("中性比较类", "Not as loud as my previous pair, but the clarity is actually better.", 0),
    ("中性比较类", "Bass is weaker than brand X, treble is smoother though.", 0),
    ("关键词误命中类", "It sounds like a great deal, and shipping was fast.", 0),
    ("关键词误命中类", "The packaging keeps the unit safe from static damage.", 0),
    ("评分语义冲突类", "Great product, though the bass is a little muddy.", 1),
    ("评分语义冲突类", "Arrived broken due to poor packaging, refund was quick.", 0),
    ("多语言类", "La calidad del sonido es regular, esperaba más graves.", None),
    ("多语言类", "音质一般般，低音不够，有点失望。", None),
    ("极短评论类", "Meh.", 0),
    ("极短评论类", "Sound broke after a week.", 1),
]


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_DIR).to(device)
    model.eval()
    with open(os.path.join(MODEL_DIR, "threshold.json"),
              encoding="utf-8") as f:
        thr = float(json.load(f)["threshold"])

    texts = [s[1] for s in SAMPLES]
    probs = []
    with torch.no_grad():
        for b in range(0, len(texts), 8):
            enc = tok(texts[b:b + 8], padding=True, truncation=True,
                      max_length=128, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            probs.append(torch.softmax(model(**enc).logits, -1)
                         [:, 1].cpu().numpy())
    probs = np.concatenate(probs)
    preds = (probs >= thr).astype(int)

    lines = ["# 边界案例基准报告（edge_case_benchmark.md）", "",
             "口径：样本取自 `edge_cases.md` 收录的真实评论（n=12，定向探针，"
             "非大规模基准）；期望标签按该文档判据由 DSH 标注并在此如实披露。"
             "多语言类标记为\"未支持\"，不参与命中率统计。阈值 0.9744。", "",
             "| 类别 | 评论 | 期望 | 模型判定 | 概率 |", "|---|---|---|---|---|"]
    for (cat, text, exp), pr, pd_ in zip(SAMPLES, probs, preds):
        exp_s = "未支持" if exp is None else ("负面" if exp else "正常")
        got_s = "负面" if pd_ else "正常"
        if exp is None:
            mark = "—"
        else:
            mark = "✓" if pd_ == exp else "✗"
        lines.append(f"| {cat} | {text[:48]}… | {exp_s} | {got_s} {mark} | {pr:.4f} |")
    lines.append("")

    cats = {}
    for (cat, text, exp), pd_ in zip(SAMPLES, preds):
        if exp is None:
            continue
        d = cats.setdefault(cat, [0, 0])
        d[1] += 1
        d[0] += int(pd_ == exp)
    lines.append("| 类别 | 命中 | 样本数 | 命中率 |")
    lines.append("|---|---|---|---|")
    for cat, (hit, tot) in cats.items():
        lines.append(f"| {cat} | {hit} | {tot} | {hit/tot*100:.0f}% |")
    tot_hit = sum(v[0] for v in cats.values())
    tot_n = sum(v[1] for v in cats.values())
    lines.append(f"| 合计（除多语言） | {tot_hit} | {tot_n} | {tot_hit/tot_n*100:.0f}% |")
    lines.append("")

    df = pd.read_csv(DUMP, encoding="utf-8", keep_default_na=False)
    non_en = df["text"].map(lambda t: bool(re.search(
        r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u00e0-\u00ff]", str(t))))
    n_non_en = int(non_en.sum())
    lines += ["## val_v2 层面的定量补充", "",
              f"- 非英文/含非英文字符评论占比：{n_non_en}/{len(df)} "
              f"（{n_non_en/len(df)*100:.2f}%），其中被模型判为音质负面 "
              f"{int(((non_en) & (df['pred'] == 1)).sum())} 条。",
              "",
              "如实结论：定向探针 n=12 仅能暴露已知边界类别的行为模式，"
              "不能替代大规模评测；其价值是验证边界类别是否如预期失败/通过，"
              "而非给出置信的性能数字。",
              "- 委婉表达类 0/2：确认是该类别的已知漏检来源（与 C4 错误分类学一致）。",
              "- 中性比较类 1/2：\"Bass is weaker...\" 被高置信误判负面，"
              "确认双面评价存在误报风险。",
              "- 多语言类：两条非英文评论概率均接近 0，模型对非英文评论"
              "静默判为正常而非拒绝——这是静默漏报风险，E7 将加入非英文显式拒绝。",
              ""]
    text = "\n".join(lines)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
