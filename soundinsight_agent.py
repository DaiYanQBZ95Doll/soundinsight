# -*- coding: utf-8 -*-
# 本脚本是 SoundInsight 一键洞察 Agent：输入评论 CSV，自动完成音质差评识别、
# 问题归因与统计，输出洞察报告（markdown/excel）并打印摘要。一条命令即可运行。
# 支持 --lang en 英文报告；非英文评论经 predict_core.is_unsupported 跳过并计数。
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
sys.path.insert(0, HERE)
from predict_core import is_unsupported  # noqa: E402

with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
    CFG = json.load(f)
BIN_MODEL = os.path.join(HERE, CFG["bin_model_dir"])
ML_MODEL = os.path.join(HERE, CFG["multi_label_dir"])
THR_FILE = os.path.join(HERE, CFG["threshold_file"])
ISSUE_FILE = os.path.join(HERE, CFG["issue_labels_file"])
BATCH = int(CFG["batch_size"])
MAX_LEN = int(CFG["max_len"])


def load():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = DistilBertTokenizer.from_pretrained(BIN_MODEL)
    bin_model = DistilBertForSequenceClassification.from_pretrained(
        BIN_MODEL).to(device)
    bin_model.eval()
    with open(THR_FILE, encoding="utf-8") as f:
        thr = float(json.load(f)["threshold"])
    ml_model = DistilBertForSequenceClassification.from_pretrained(
        ML_MODEL).to(device)
    ml_model.eval()
    with open(ISSUE_FILE, encoding="utf-8") as f:
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


def analyze(csv_path: str, export: bool = False, lang: str = "zh") -> str:
    device, tok, bin_model, thr, ml_model, issue_info = load()
    df = pd.read_csv(csv_path, encoding="utf-8")
    text_col = next((c for c in ("text", "reviewText", "review")
                     if c in df.columns), df.columns[0])
    df["_text"] = df[text_col].astype(str)
    n_unsup = int(df["_text"].map(is_unsupported).sum())
    df = df[~df["_text"].map(is_unsupported)].reset_index(drop=True)
    texts = df["_text"].tolist()
    print(f"分析 {len(texts)} 条评论 (device={device})，"
          f"跳过非英文 {n_unsup} 条")

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

    # 优先级规则：占比前三且数量 >= 总差评数 10% 的类别 -> 高；
    # 其余有正数的类别 -> 中；数量为 0 的类别 -> 低
    total_issue = sum(issue_counts.values())
    ranked = sorted(issue_counts.items(), key=lambda x: -x[1])
    priority = {}
    for rank, (name, cnt) in enumerate(ranked):
        if cnt > 0 and rank < 3 and total_issue > 0 and \
                cnt >= max(total_issue, 1) * 0.1:
            priority[name] = "高"
        elif cnt > 0:
            priority[name] = "中"
        else:
            priority[name] = "低"

    rate = n_neg / n if n else 0.0
    if rate >= 0.03:
        verdict = "严重，音质差评率显著偏高，建议立即排查"
    elif rate >= 0.015:
        verdict = "偏高，建议关注并启动整改"
    else:
        verdict = "正常，音质口碑处于健康水平"

    src_name = os.path.basename(csv_path)
    if lang == "en":
        lines = _report_en(src_name, n, n_neg, rate, avg_rating, verdict,
                           ranked, priority, neg_idx, probs, texts, n_unsup)
        out_path = os.path.join(HERE, "insight_report_v2_en.md")
    else:
        lines = _report_zh(src_name, n, n_neg, rate, avg_rating, verdict,
                           ranked, priority, neg_idx, probs, texts, n_unsup)
        out_path = os.path.join(HERE, "insight_report_v2.md")
    report = "\n".join(lines)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"报告已保存 -> {out_path}")
    if export:
        export_excel(csv_path, n, rate, avg_rating, verdict, ranked,
                     priority, neg_idx, probs, texts)
    return report


def _cost_lines(n: int, lang: str):
    """E6 成本对照行：本地推理 0 API 费用 vs LLM 按实测价估算。"""
    llm_est = n / 1000 * 0.03
    if lang == "en":
        return [
            f"- Inference cost: local = 0 API fee; same batch via LLM "
            f"(deepseek-chat, measured ~$0.03/1000) ≈ ${llm_est:.2f} "
            f"(estimate based on llm_baseline.md)."]
    return [
        f"- 成本对照：本地推理 0 API 费用；同等 {n} 条若调用 LLM"
        f"（deepseek-chat，实测约 $0.03/1000 条，见 llm_baseline.md）"
        f"约 ${llm_est:.2f}。"]


def _report_zh(src_name, n, n_neg, rate, avg_rating, verdict, ranked,
               priority, neg_idx, probs, texts, n_unsup):
    lines = []
    lines.append("# SoundInsight 音质洞察报告")
    lines.append("")
    lines.append("## 一、总体概况")
    lines.append(f"分析对象：{src_name}")
    lines.append(f"分析时间：{datetime.now():%Y-%m-%d %H:%M}")
    lines.append(f"评论总数：{n + n_unsup} 条（其中非英文 {n_unsup} 条已跳过）")
    lines.append(f"有效评论：{n} 条")
    lines.append(f"音质差评数：{n_neg} 条（占比 {rate:.2%}）")
    if not np.isnan(avg_rating):
        lines.append(f"平均评分：{avg_rating:.2f}")
    lines.append(f"结论一句话：{verdict}")
    lines.append("")
    lines.append("## 二、问题分布")
    lines.append("| 问题类别 | 数量 | 占比 | 优先级 |")
    lines.append("|---------|------|------|--------|")
    for name, cnt in ranked:
        pct = f"{cnt / max(total_issue_of(ranked), 1):.1%}"
        lines.append(f"| {name} | {cnt} | {pct} | {priority[name]} |")
    lines.append("")
    lines.append("## 三、典型案例")
    shown = 0
    neg_sorted = sorted(neg_idx, key=lambda i: -probs[i])
    for i in neg_sorted[:5]:
        lines.append(f"{shown + 1}. （{probs[i]:.1%}）{texts[i][:120]}")
        shown += 1
    if shown == 0:
        lines.append("未检测到音质负面评论。")
    lines.append("")
    lines.append("## 四、行动建议")
    highs = [name for name, cnt in ranked if priority[name] == "高"]
    for name in highs:
        obj = "生产/质检" if name in ("杂音", "低音") else "客服/详情页"
        lines.append(f"- 紧急（{name}）：建议检查 {obj} 环节，"
                     f"预期降低该类差评率。")
    if not highs:
        lines.append("未检测到集中性音质问题，建议维持当前品控。")
    lines.append("")
    lines.append("## 五、验证指标")
    lines.append("建议复评周期：2-4 周后重新运行批量分析，"
                 "追踪同口径差评率变化。")
    lines.append("")
    lines.append("## 六、附注")
    lines.append("本报告由 SoundInsight 自动生成，判定基于 DistilBERT "
                 "微调模型（验证集 F1 0.687，阈值 0.97）与五类多标签归因"
                 "模型，边界案例存在一定误差，关键决策建议结合人工抽查。")
    lines.append("模型输出概率未经校准，仅供排序参考（见 calibration_eval.md）。")
    lines += _cost_lines(n, "zh")
    return lines


def _report_en(src_name, n, n_neg, rate, avg_rating, verdict, ranked,
               priority, neg_idx, probs, texts, n_unsup):
    en_verdict = {"严重，音质差评率显著偏高，建议立即排查":
                  "Severe: sound-quality complaint rate is significantly "
                  "elevated; investigate immediately",
                  "偏高，建议关注并启动整改":
                  "Elevated: monitor closely and start remediation",
                  "正常，音质口碑处于健康水平":
                  "Healthy: sound-quality reputation is at a normal level"}
    lines = []
    lines.append("# SoundInsight Sound Quality Report")
    lines.append("")
    lines.append("## 1. Overview")
    lines.append(f"Source: {src_name}")
    lines.append(f"Generated: {datetime.now():%Y-%m-%d %H:%M}")
    lines.append(f"Total reviews: {n + n_unsup} "
                 f"({n_unsup} non-English skipped)")
    lines.append(f"Valid reviews: {n}")
    lines.append(f"Sound-quality negatives: {n_neg} ({rate:.2%})")
    if not np.isnan(avg_rating):
        lines.append(f"Average rating: {avg_rating:.2f}")
    lines.append(f"Verdict: {en_verdict.get(verdict, verdict)}")
    lines.append("")
    lines.append("## 2. Issue Breakdown")
    lines.append("| Issue | Count | Share | Priority |")
    lines.append("|-------|-------|-------|----------|")
    for name, cnt in ranked:
        pct = f"{cnt / max(total_issue_of(ranked), 1):.1%}"
        pr = {"高": "High", "中": "Medium", "低": "Low"}[priority[name]]
        lines.append(f"| {name} | {cnt} | {pct} | {pr} |")
    lines.append("")
    lines.append("## 3. Examples")
    shown = 0
    neg_sorted = sorted(neg_idx, key=lambda i: -probs[i])
    for i in neg_sorted[:5]:
        lines.append(f"{shown + 1}. ({probs[i]:.1%}) {texts[i][:120]}")
        shown += 1
    if shown == 0:
        lines.append("No sound-quality negatives detected.")
    lines.append("")
    lines.append("## 4. Actions")
    highs = [name for name, cnt in ranked if priority[name] == "高"]
    for name in highs:
        lines.append(f"- Urgent ({name}): check the related hardware/QC or "
                     f"listing channels to reduce this complaint type.")
    if not highs:
        lines.append("No concentrated issue detected; keep current QC.")
    lines.append("")
    lines.append("## 5. Follow-up")
    lines.append("Re-run this analysis in 2-4 weeks and track the "
                 "same-scope complaint-rate change.")
    lines.append("")
    lines.append("## 6. Notes")
    lines.append("Auto-generated by SoundInsight (DistilBERT fine-tune, "
                 "validation F1 0.687, threshold 0.97, 5-class attribution). "
                 "Edge cases carry error; verify key decisions manually. "
                 "Probabilities are uncalibrated, for ranking only "
                 "(see calibration_eval.md).")
    lines += _cost_lines(n, "en")
    return lines


def total_issue_of(ranked):
    return sum(c for _, c in ranked)


def export_excel(csv_path, n, rate, avg_rating, verdict, ranked, priority,
                 neg_idx, probs, texts):
    """导出 Excel 版报告：总体概况 / 问题分布（高优先级标红）/ 典型案例。"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "总体概况"
    rows1 = [["指标", "数值"],
             ["分析对象", os.path.basename(csv_path)],
             ["评论总数", n],
             ["音质差评数", f"{len(neg_idx)}（{rate:.2%}）"],
             ["平均评分", f"{avg_rating:.2f}"],
             ["结论", verdict]]
    for r in rows1:
        ws1.append(r)

    ws2 = wb.create_sheet("问题分布")
    ws2.append(["问题类别", "数量", "占比", "优先级"])
    total_issue = sum(c for _, c in ranked)
    red_font = Font(color="FF0000", bold=True)
    red_fill = PatternFill("solid", fgColor="FFC7CE")
    for name, cnt in ranked:
        ws2.append([name, cnt,
                    f"{cnt / max(total_issue, 1):.1%}", priority[name]])
        if priority[name] == "高":
            for cell in ws2[ws2.max_row]:
                cell.font = red_font
                cell.fill = red_fill

    ws3 = wb.create_sheet("典型案例")
    ws3.append(["概率", "类别", "评论原文"])
    for i in sorted(neg_idx, key=lambda j: -probs[j])[:5]:
        ws3.append([f"{probs[i]:.1%}", "音质负面", texts[i][:500]])

    xlsx_path = os.path.join(HERE, "insight_report.xlsx")
    wb.save(xlsx_path)
    print(f"Excel 报告已保存 -> {xlsx_path}")
    return xlsx_path


def main() -> None:
    ap = argparse.ArgumentParser(description="SoundInsight 一键洞察 Agent")
    ap.add_argument("--csv", required=True, help="待分析评论 CSV 路径")
    ap.add_argument("--format", choices=["md", "excel"], default="md",
                    help="报告格式：md 或 excel")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh",
                    help="报告语言：zh 中文（默认）或 en 英文")
    args = ap.parse_args()
    report = analyze(args.csv, export=(args.format == "excel"),
                     lang=args.lang)
    print("\n" + report)


if __name__ == "__main__":
    main()
