# -*- coding: utf-8 -*-
# report_builder.py —— SoundInsight 洞察报告生成共享模块
#
# 三个入口共用同一套口径，避免"命令行 Agent 有完整报告、Demo 只有摘要"的不一致：
#   - soundinsight_agent.py（命令行一键 Agent，md/excel、zh/en）
#   - demo_sound_v2.py（本地 Gradio Demo 批量分析页）
#   - deployment/app.py（ModelScope 创空间在线 Demo）
#
# 报告结构（六节）：总体概况 / 问题分布 / 典型案例 / 行动建议 / 验证指标 / 附注
import math
from datetime import datetime

ISSUE_PRIORITY_DOC = ("优先级规则：占比前三且数量≥总差评数 10% 的类别为高；"
                      "其余有正数的为中；数量为 0 的为低。")


def rank_issues(issue_counts: dict):
    """按数量降序排列并给出优先级。返回 (ranked, priority)。"""
    total = sum(issue_counts.values())
    ranked = sorted(issue_counts.items(), key=lambda x: -x[1])
    priority = {}
    for rank, (name, cnt) in enumerate(ranked):
        if cnt > 0 and rank < 3 and total > 0 and cnt >= max(total, 1) * 0.1:
            priority[name] = "高"
        elif cnt > 0:
            priority[name] = "中"
        else:
            priority[name] = "低"
    return ranked, priority


def verdict(rate: float, lang: str = "zh") -> str:
    """按差评率给出结论一句话。"""
    if lang == "en":
        if rate >= 0.03:
            return ("Severe: sound-quality complaint rate is significantly "
                    "elevated; investigate immediately")
        if rate >= 0.015:
            return "Elevated: monitor closely and start remediation"
        return "Healthy: sound-quality reputation is at a normal level"
    if rate >= 0.03:
        return "严重，音质差评率显著偏高，建议立即排查"
    if rate >= 0.015:
        return "偏高，建议关注并启动整改"
    return "正常，音质口碑处于健康水平"


def cost_line(n: int, lang: str = "zh") -> str:
    """成本对照行（本地推理 0 API 费用 vs LLM 实测单价）。"""
    est = n / 1000 * 0.03
    if lang == "en":
        return (f"- Cost: local inference = 0 API fee; same batch via LLM "
                f"(deepseek-chat, measured ~$0.03/1000) ≈ ${est:.2f} "
                f"(see llm_baseline.md).")
    return (f"- 成本对照：本地推理 0 API 费用；同等 {n} 条若调用 LLM"
            f"（deepseek-chat，实测约 $0.03/1000 条，见 llm_baseline.md）"
            f"约 ${est:.2f}。")


def _example_lines(examples, lang: str = "zh", top_text: int = 120):
    """典型案例：概率 + 原文 + 五类归因概率（模型本就计算了五类概率）。"""
    lines = []
    for i, ex in enumerate(examples, 1):
        text = str(ex.get("text", "")).replace("\n", " ")[:top_text]
        prob = ex.get("prob")
        head = f"{i}. （{prob:.1%}）{text}" if prob is not None else f"{i}. {text}"
        lines.append(head)
        probs = ex.get("issue_probs") or {}
        if probs:
            ranked = sorted(probs.items(), key=lambda x: -x[1])[:3]
            detail = "、".join(f"{k} {v:.2f}" for k, v in ranked)
            label = "归因概率" if lang == "zh" else "issue probs"
            lines.append(f"   {label}：{detail}")
    return lines


def build_report(*, src_name: str, n_total: int, n_unsupported: int,
                 n_valid: int, n_neg: int, avg_rating: float,
                 issue_counts: dict, examples=None, n_mid: int = 0,
                 lang: str = "zh", generated_at: str = None) -> str:
    """生成六节洞察报告（Markdown 文本）。所有数字由调用方传入，不在此处编造。"""
    examples = examples or []
    rate = (n_neg / n_valid) if n_valid else 0.0
    ranked, priority = rank_issues(issue_counts)
    total_issue = sum(issue_counts.values())
    stamp = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M")
    rating_known = not (isinstance(avg_rating, float) and math.isnan(avg_rating))

    if lang == "en":
        lines = ["# SoundInsight Sound Quality Report", "", "## 1. Overview",
                 f"Source: {src_name}", f"Generated: {stamp}",
                 f"Total reviews: {n_total} ({n_unsupported} non-English skipped)",
                 f"Valid reviews: {n_valid}",
                 f"Sound-quality negatives: {n_neg} ({rate:.2%})"]
        if rating_known:
            lines.append(f"Average rating: {avg_rating:.2f}")
        lines.append(f"Verdict: {verdict(rate, 'en')}")
        lines += ["", "## 2. Issue Breakdown",
                  "| Issue | Count | Share | Priority |",
                  "|-------|-------|-------|----------|"]
        for name, cnt in ranked:
            pr = {"高": "High", "中": "Medium", "低": "Low"}[priority[name]]
            lines.append(f"| {name} | {cnt} | "
                         f"{cnt / max(total_issue, 1):.1%} | {pr} |")
        lines += ["", "## 3. Typical Cases"]
        lines += _example_lines(examples, "en") or ["No negative detected."]
        lines += ["", "## 4. Actions"]
        highs = [n for n, _ in ranked if priority[n] == "高"]
        if highs:
            for name in highs:
                lines.append(f"- Urgent ({name}): check related hardware/QC or "
                             f"listing channels to reduce this complaint type.")
        else:
            lines.append("No concentrated issue detected; keep current QC.")
        lines += ["", "## 5. Verification"]
        lines.append("Re-run this analysis in 2-4 weeks and track the "
                     "same-scope complaint-rate change.")
        if n_mid:
            lines.append(f"- {n_mid} review(s) fall in the mid-confidence "
                         f"band (prob 0.5-0.9744): treated as normal but "
                         f"flagged for manual review.")
        lines += ["", "## 6. Notes",
                  "Auto-generated by SoundInsight (DistilBERT fine-tune, "
                  "validation F1 0.687, threshold 0.97, 5-class attribution). "
                  "Edge cases carry error; verify key decisions manually.",
                  "Probabilities are uncalibrated, for ranking only "
                  "(see calibration_eval.md).", cost_line(n_valid, "en")]
        return "\n".join(lines)

    # 中文版
    lines = ["# SoundInsight 音质洞察报告", "", "## 一、总体概况",
             f"分析对象：{src_name}",
             f"分析时间：{stamp}",
             f"评论总数：{n_total} 条（其中非英文 {n_unsupported} 条已跳过）",
             f"有效评论：{n_valid} 条",
             f"音质差评数：{n_neg} 条（占比 {rate:.2%}）"]
    if rating_known:
        lines.append(f"平均评分：{avg_rating:.2f}")
    lines.append(f"结论一句话：{verdict(rate)}")
    lines += ["", "## 二、问题分布",
              "| 问题类别 | 数量 | 占比 | 优先级 |",
              "|---------|------|------|--------|"]
    for name, cnt in ranked:
        lines.append(f"| {name} | {cnt} | "
                     f"{cnt / max(total_issue, 1):.1%} | {priority[name]} |")
    lines += ["", "## 三、典型案例"]
    lines += _example_lines(examples, "zh") or ["未检测到音质负面评论。"]
    lines += ["", "## 四、行动建议"]
    highs = [n for n, _ in ranked if priority[n] == "高"]
    if highs:
        for name in highs:
            obj = "生产/质检" if name in ("杂音", "低音") else "客服/详情页"
            lines.append(f"- 紧急（{name}）：建议检查 {obj} 环节，"
                         f"预期降低该类差评率。")
    else:
        lines.append("未检测到集中性音质问题，建议维持当前品控。")
    lines += ["", "## 五、验证指标",
              "建议复评周期：2-4 周后重新运行批量分析，追踪同口径差评率变化。"]
    if n_mid:
        lines.append(f"- 中置信提示：有 {n_mid} 条评论概率落在 0.5-0.9744 区间，"
                     f"当前判为正常但建议人工抽查（疑似负面）。")
    lines += ["", "## 六、附注",
              "本报告由 SoundInsight 自动生成，判定基于 DistilBERT "
              "微调模型（验证集 F1 0.687，阈值 0.97）与五类多标签归因模型，"
              "边界案例存在一定误差，关键决策建议结合人工抽查。",
              "模型输出概率未经校准，仅供排序参考（见 calibration_eval.md）。",
              cost_line(n_valid, "zh")]
    return "\n".join(lines)
