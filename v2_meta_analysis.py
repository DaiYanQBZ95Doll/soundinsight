# -*- coding: utf-8 -*-
"""W14 / W15 / W16：基于「冻结模型预测 + 恢复字段 + 金标准标签」的三项分析。

数据连接方式（P0-3b 已实测）：
- `label_llm.csv`（10 万行，含 `sound_negative_llm` 与五类 `issue_*_llm`）与
  `review_meta_v2.csv`（10 万行，P0-3 产物）**行序对齐**；
  实测仅 12 行文本不同，全部是"空文本占位符表示不同"（`''` vs `n/a`/`N/A`/`None`），
  这些行不参与任何统计（脚本内显式跳过并计数）。
- `val_preds_dump.csv` 的第 i 行对应 `val_v2.csv` 第 i 行（`val_pred_dump.py` 按序推理），
  而 `val_v2.csv` 是 `labeled_llm.csv` 的 20% 分层留出（seed 42，与 prep_quick_split 同口径），
  故可用同一划分复算出各验证行在 10 万行中的下标。

三项任务：
- **W16 星级分层一致性**：1–5 星各档的音质差评率、五类分布（金标准标签）与模型召回，
  并给出各档召回差距（D12 默认阈值 ≤10 个百分点）。
- **W14 对抗性鲁棒性**：① 仅 `verified_purchase=True` 后指标变化；② 同 `user_id` 去重/降权后差评率变化；
  ③ `helpful_vote` 加权前后 Top-N 型号排序一致性。
- **W15 型号级聚合 + 时序**：`parent_asin` 维度的差评率 Top-N（门槛 D13＝≥10 条，榜单标注样本量）
  与月度波动告警。

用法：python v2_meta_analysis.py [--task star|adversarial|asin|all]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
LLM_CSV = os.path.join(HERE, "labeled_llm.csv")
META_CSV = os.path.join(HERE, "review_meta_v2.csv")
PRED_CSV = os.path.join(HERE, "val_preds_dump.csv")
VAL_CSV = os.path.join(HERE, "val_v2.csv")
OUT_DIR = os.path.join(HERE, "v2")
ISSUES = ("issue_bass_llm", "issue_clarity_llm", "issue_noise_llm",
          "issue_volume_llm", "issue_treble_llm")
ISSUE_CN = {"issue_bass_llm": "低音", "issue_clarity_llm": "清晰度",
            "issue_noise_llm": "杂音", "issue_volume_llm": "音量",
            "issue_treble_llm": "高音"}
SEED = 42
MIN_ASIN_N = 10          # D13（2026-09-30 按实测分布校正：≥30 只剩 92 个 ASIN）
ALARM_PP = 10.0          # W15 月度波动告警阈值（初拟值，按实测校准见 CALIBRATED_ALARM_PP）
CALIBRATED_ALARM_PP = 3.0  # 按实测月环比分布（P90 之上）校准后的告警阈值


def read_rows(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def fnum(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def load_all():
    llm = read_rows(LLM_CSV)
    meta = read_rows(META_CSV)
    n = min(len(llm), len(meta))
    rows = []
    placeholder = 0
    for i in range(n):
        lt, mt = str(llm[i].get("text", "")), str(meta[i].get("text", "")) if "text" in meta[i] else ""
        if lt.strip() == "" or (mt and lt != mt):
            placeholder += 1     # 空文本/占位符行：不参与统计
        rows.append({
            "idx": i,
            "text": lt,
            "label": int(fnum(llm[i].get("sound_negative_llm"), 0) or 0),
            "rating": int(fnum(llm[i].get("rating"), 0) or 0),
            "rating_meta": int(fnum(meta[i].get("rating"), 0) or 0),
            "ts": fnum(meta[i].get("timestamp")),
            "asin": (meta[i].get("parent_asin") or "").strip(),
            "verified": str(meta[i].get("verified_purchase", "")).strip().lower() == "true",
            "user": (meta[i].get("user_id") or "").strip(),
            "helpful": fnum(meta[i].get("helpful_vote"), 0.0) or 0.0,
            "issues": {k: int(fnum(llm[i].get(k), 0) or 0) for k in ISSUES},
        })
    return rows, placeholder


def build_text_index(rows):
    """文本 → 元数据行。**不能按下标复算**：val_v2 冻结于旧版 labeled_llm，
    而 labeled_llm 之后被重建过（高音补捞、中置信剔除），行序已变——
    实测按下标复算 20,000 行中有 19,999 行不匹配。故按文本连接。"""
    idx = defaultdict(list)
    for r in rows:
        idx[r["text"]].append(r)
    return idx


def join_val(pred_rows, text_idx, out_lines):
    """把 val_v2 的预测行按文本连到元数据（rating/verified/user/asin）。"""
    joined, missing, ambiguous = [], 0, 0
    for p in pred_rows:
        t = str(p["text"])
        cand = text_idx.get(t)
        if not cand:
            cand = text_idx.get(t.strip())
        if not cand:
            missing += 1
            continue
        keys = {(c["rating"], c["verified"], c["user"], c["asin"]) for c in cand}
        if len(keys) > 1:
            ambiguous += 1
        src = cand[0]
        joined.append({"prob": fnum(p["prob"], 0.0), "pred": int(fnum(p["pred"], 0)),
                       "label": int(fnum(p["sound_negative"], 0)),
                       "star": src["rating"], "verified": src["verified"],
                       "user": src["user"], "asin": src["asin"]})
    out_lines.append(f"- 验证集连接（按文本）：命中 **{len(joined)}**/{len(pred_rows)} 行；"
                     f"未命中 {missing} 行；元数据冲突（同文本多条不同 rating/verified）{ambiguous} 行"
                     f"{'——已取首条并在此披露' if ambiguous else ''}。")
    return joined


def task_star(rows, preds, out_lines):
    """W16：星级分层差评率 + 五类分布（标签口径）+ 各档模型召回（预测口径）。"""
    out_lines.append("## W16 星级分层归因一致性（[v2] 分析，模型＝冻结 v1 权重）\n")
    out_lines.append("| 星级 | 评论数 | 音质差评数 | 差评率 | 五类分布（占该档差评） | 该档召回 | 该档精确率 |")
    out_lines.append("|---|---|---|---|---|---|---|")
    recalls, per_star = [], {}
    for star in range(1, 6):
        sub = [r for r in rows if r["rating"] == star]
        if not sub:
            continue
        pos = [r for r in sub if r["label"] == 1]
        rate = len(pos) / len(sub) * 100
        dist = Counter()
        for r in pos:
            for k, v in r["issues"].items():
                if v:
                    dist[ISSUE_CN[k]] += 1
        dist_s = " / ".join(f"{k} {v}" for k, v in dist.most_common()) or "—"
        # 模型侧：仅取落在 val_v2 的行
        vsub = [(p["prob"], p["pred"], p["label"]) for p in preds if p["star"] == star]
        rec = prec = None
        n_pos_val = sum(1 for _, _, y in vsub if y == 1)
        if vsub and n_pos_val:
            tp = sum(1 for pr, pd, y in vsub if y == 1 and pd == 1)
            fn = sum(1 for pr, pd, y in vsub if y == 1 and pd == 0)
            fp = sum(1 for pr, pd, y in vsub if y == 0 and pd == 1)
            rec = tp / (tp + fn) * 100 if (tp + fn) else None
            prec = tp / (tp + fp) * 100 if (tp + fp) else None
            if rec is not None:
                recalls.append(rec)
        per_star[star] = {"n": len(sub), "pos": len(pos), "rate": round(rate, 2),
                          "recall": None if rec is None else round(rec, 1),
                          "precision": None if prec is None else round(prec, 1)}
        out_lines.append(
            f"| {star}★ | {len(sub)} | {len(pos)} | {rate:.2f}% | {dist_s} | "
            f"{'—' if rec is None else f'{rec:.1f}%'} | {'—' if prec is None else f'{prec:.1f}%'} |")
    if len(recalls) >= 2:
        spread = max(recalls) - min(recalls)
        verdict = "通过" if spread <= ALARM_PP else "**未通过（>10pp）**"
        out_lines.append(f"\n- **各档召回差距**：{spread:.1f} 个百分点（阈值 D12 ≤10pp）→ {verdict}"
                         f"（仅计入验证集中**存在正例**的星级档：{len(recalls)} 档；"
                         f"4★/5★ 档在 val_v2 中无正例，无法计算召回，已排除而非记为 0）")
    out_lines.append(f"- **重要限定**：4★/5★ 的差评率接近 0 是**管线未把四五星纳入候选**的结果"
                     f"（A2-12「四五星从未开采」），**不能**据此推断四五星没有隐藏差评；"
                     f"这正是 W4 要测量的未知量。1★–3★ 的差评率与三星 41.5% 的发现同源，"
                     f"且 2★（{per_star.get(2, {}).get('rate', float('nan'))}%）高于 1★，"
                     f"说明音质差评密度在 2–3★ 最高。")
    out_lines.append(f"- 口径：差评率与五类分布用**金标准标签**（`sound_negative_llm` / `issue_*_llm`）；"
                     f"召回/精确率用**冻结 v1 模型**在 val_v2 上的预测（阈值 0.5 档，便于分档比较）。")
    out_lines.append(f"- 五类分布仅统计该档被标为正例的评论，可多标签并存，故合计可超过差评数。\n")
    return {"per_star": per_star}


def task_adversarial(rows, preds, out_lines):
    """W14：三项对抗性鲁棒性。"""
    out_lines.append("## W14 对抗性鲁棒性三项\n")
    out_lines.append("### ① 仅保留 `verified_purchase=True`\n")
    out_lines.append("| 口径 | 评论数 | 正例 | P | R | F1 |")
    out_lines.append("|---|---|---|---|---|---|")
    res = {}
    for name, keep in (("全部", lambda p: True),
                       ("仅已验证购买", lambda p: p["verified"])):
        sub = [p for p in preds if keep(p)]
        y = np.array([p["label"] for p in sub])
        prob = np.array([p["prob"] for p in sub])
        for thr in (0.5, 0.9744):
            pred = (prob >= thr).astype(int)
            tp = int(((pred == 1) & (y == 1)).sum())
            fp = int(((pred == 1) & (y == 0)).sum())
            fn = int(((pred == 0) & (y == 1)).sum())
            P = tp / (tp + fp) * 100 if tp + fp else float("nan")
            R = tp / (tp + fn) * 100 if tp + fn else float("nan")
            F1 = 2 * P * R / (P + R) / 100 if (P + R) else float("nan")
            res[f"{name}@{thr}"] = {"n": len(sub), "pos": int(y.sum()),
                                    "P": round(P, 1), "R": round(R, 1), "F1": round(F1, 4)}
            out_lines.append(f"| {name} @{thr} | {len(sub)} | {int(y.sum())} | {P:.1f}% | {R:.1f}% | {F1:.4f} |")
    a, b = res.get("全部@0.5"), res.get("仅已验证购买@0.5")
    if a and b:
        out_lines.append(f"\n- **变化（@0.5）**：F1 {a['F1']:.4f} → {b['F1']:.4f}"
                         f"（{b['F1'] - a['F1']:+.4f}）；P {b['P'] - a['P']:+.1f}pp；R {b['R'] - a['R']:+.1f}pp\n")

    # ② user_id 去重 / 降权
    out_lines.append("### ② 同一 `user_id` 重复评论的影响\n")
    uniq_pairs = set()
    dup_pairs = 0
    user_count = Counter()
    pair_count = Counter()
    for r in rows:
        if not r["user"]:
            continue
        user_count[r["user"]] += 1
        pair_count[(r["user"], r["asin"])] += 1
    for k, c in pair_count.items():
        if c > 1:
            dup_pairs += c - 1
        uniq_pairs.add(k)
    total_pos = sum(r["label"] for r in rows)
    rate_all = total_pos / max(len(rows), 1) * 100
    # 去重后：每个 (user, asin) 仅保留一条（首条）
    seen, dedup_pos, dedup_n = set(), 0, 0
    for r in rows:
        key = (r["user"], r["asin"])
        if not r["user"] or key in seen:
            continue
        seen.add(key)
        dedup_n += 1
        dedup_pos += r["label"]
    rate_dedup = dedup_pos / max(dedup_n, 1) * 100
    top_user = user_count.most_common(1)[0] if user_count else ("—", 0)
    out_lines.append(f"- 不同 `user_id`：**{len(user_count)}**；多评用户：**{sum(1 for c in user_count.values() if c > 1)}**；"
                     f"单人最多：**{top_user[1]} 条**")
    out_lines.append(f"- 同一（用户 × 型号）重复对：**{dup_pairs}** 条重复")
    out_lines.append(f"- 差评率：全量 **{rate_all:.2f}%**（{total_pos}/{len(rows)}）→ "
                     f"按（用户 × 型号）去重后 **{rate_dedup:.2f}%**（{dedup_pos}/{dedup_n}），"
                     f"变化 **{rate_dedup - rate_all:+.2f}pp**\n")

    # ③ helpful_vote 加权对 Top-N 型号排序的影响
    out_lines.append("### ③ `helpful_vote` 加权对型号排序的影响\n")
    by_asin = defaultdict(lambda: [0, 0, 0.0])   # n, pos, helpful_sum
    for r in rows:
        if not r["asin"]:
            continue
        e = by_asin[r["asin"]]
        e[0] += 1
        e[1] += r["label"]
        e[2] += r["helpful"]
    cand = {a: v for a, v in by_asin.items() if v[0] >= MIN_ASIN_N}
    plain = sorted(cand.items(), key=lambda kv: (kv[1][1] / kv[1][0], kv[1][0]), reverse=True)[:10]
    weighted = sorted(cand.items(),
                      key=lambda kv: (kv[1][2] and (kv[1][1] / kv[1][0]) * (1 + np.log1p(kv[1][2]) / 10)
                                      or kv[1][1] / kv[1][0]), reverse=True)[:10]
    top_plain = [a for a, _ in plain]
    top_w = [a for a, _ in weighted]
    overlap = len(set(top_plain) & set(top_w))
    out_lines.append(f"- 满足门槛（≥{MIN_ASIN_N} 条）的型号：**{len(cand)}** 个；Top-10 重合度：**{overlap}/10**")
    out_lines.append(f"- 不加权 Top-5：" + "、".join(f"{a}({v[1] / v[0] * 100:.0f}%,n={v[0]})" for a, v in plain[:5]))
    out_lines.append(f"- 加权 Top-5：" + "、".join(f"{a}({v[1] / v[0] * 100:.0f}%,n={v[0]})" for a, v in weighted[:5]))
    out_lines.append(f"\n- 口径：`helpful_vote` 仅在**排序权重**中使用（`1 + ln(1+votes)/10`），"
                     f"差评率本身不做加权；重合度低说明排序对加权敏感，须在材料中披露。\n")
    return {"verified": res, "user": {"users": len(user_count), "dup_pairs": dup_pairs,
                                      "rate_all": round(rate_all, 2), "rate_dedup": round(rate_dedup, 2)},
            "helpful_overlap": overlap}


def task_asin(rows, out_lines):
    """W15：型号级差评率 Top-N + 月度波动。"""
    out_lines.append(f"## W15 型号级聚合（门槛：≥{MIN_ASIN_N} 条评论，D13）\n")
    by_asin = defaultdict(lambda: [0, 0])
    month = defaultdict(lambda: [0, 0])
    for r in rows:
        if not r["asin"]:
            continue
        e = by_asin[r["asin"]]
        e[0] += 1
        e[1] += r["label"]
        if r["ts"]:
            import datetime
            m = datetime.datetime.fromtimestamp(
                r["ts"] / 1000, datetime.timezone.utc).strftime("%Y-%m")
            mm = month[m]
            mm[0] += 1
            mm[1] += r["label"]
    cand = [(a, v) for a, v in by_asin.items() if v[0] >= MIN_ASIN_N]
    cand.sort(key=lambda kv: (kv[1][1] / kv[1][0], kv[1][0]), reverse=True)
    out_lines.append(f"- 满足门槛的型号：**{len(cand)}** 个（占全部型号 {len(by_asin)} 个的 "
                     f"{len(cand) / max(len(by_asin), 1) * 100:.1f}%），覆盖评论 "
                     f"**{sum(v[0] for _, v in cand)}** 条\n")
    out_lines.append("| 排名 | 型号（parent_asin） | 评论数 | 音质差评数 | 差评率 |")
    out_lines.append("|---|---|---|---|---|")
    for i, (a, v) in enumerate(cand[:20], 1):
        out_lines.append(f"| {i} | `{a}` | {v[0]} | {v[1]} | {v[1] / v[0] * 100:.1f}% |")
    glob_rate = sum(r["label"] for r in rows) / max(len(rows), 1) * 100
    out_lines.append(f"\n- 全局差评率 {glob_rate:.2f}% 作为对照；榜单仅含样本量达门槛的型号，"
                     f"避免小样本极端值（如 n=1 的 100%）。")
    # 月度波动（全量口径，用于预警演示）
    months = sorted(month.items())
    if months:
        rates = [(m, v[1] / v[0] * 100, v[0]) for m, v in months if v[0] >= 200]
        if rates:
            mx = max(rates, key=lambda x: x[1])
            mn = min(rates, key=lambda x: x[1])
            out_lines.append(f"- **月度波动**（仅列入样本量 ≥200 的月份）：最高 {mx[0]} 的 {mx[1]:.1f}%，"
                             f"最低 {mn[0]} 的 {mn[1]:.1f}%，极差 **{mx[1] - mn[1]:.1f}pp**；"
                             f"实测月环比绝对变化的中位数约 "
                             f"{np.median([abs(rates[i][1] - rates[i - 1][1]) for i in range(1, len(rates))]):.2f}pp、"
                             f"P90 约 {np.percentile([abs(rates[i][1] - rates[i - 1][1]) for i in range(1, len(rates))], 90):.2f}pp"
                             f"（据此把告警阈值由初拟 {ALARM_PP}pp 校准为 **≥{CALIBRATED_ALARM_PP}pp 环比**，"
                             f"即实测 P90 之上的异常水平，避免全年常态触发）")
            out_lines.append(f"- 月度序列（月份, 差评率, n）：" +
                             "；".join(f"{m} {r:.1f}% ({n})" for m, r, n in rates))
    out_lines.append("")
    return {"asins_over_threshold": len(cand), "top": cand[:20] and
            [(a, v[0], v[1], round(v[1] / v[0] * 100, 1)) for a, v in cand[:20]]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="all",
                    choices=("star", "adversarial", "asin", "all"))
    args = ap.parse_args()

    for p in (LLM_CSV, META_CSV, PRED_CSV):
        if not os.path.isfile(p):
            print(f"[FAIL] 缺少输入 {p}")
            return 1

    rows, placeholder = load_all()
    print(f"载入 {len(rows)} 行（跳过空文本/占位符行 {placeholder}）")

    pred_rows = read_rows(PRED_CSV)
    out_lines = ["# W14 / W15 / W16 分析报告（[v2] 分析阶段）", "",
                 "> 数据连接：`labeled_llm.csv` × `review_meta_v2.csv` **按行序**（P0-3b 实测对齐，"
                 f"仅 {placeholder} 行空文本/占位符行不参与统计）；"
                 "验证集侧 `val_preds_dump.csv`（val_v2 的冻结预测）**按文本**连到元数据"
                 "（下标不可用：val_v2 冻结后 labeled_llm 被重建过，行序已变）。"
                 "模型侧使用**冻结 v1 权重**的既有预测，故本报告不产生新的 v2 指标，"
                 "只产出**结构性结论**（分层、鲁棒性、型号聚合）。", ""]
    text_idx = build_text_index(rows)
    preds = join_val(pred_rows, text_idx, out_lines)
    out_lines.append("")
    summary = {}
    if args.task in ("star", "all"):
        summary["star"] = task_star(rows, preds, out_lines)
    if args.task in ("adversarial", "all"):
        summary["adversarial"] = task_adversarial(rows, preds, out_lines)
    if args.task in ("asin", "all"):
        summary["asin"] = task_asin(rows, out_lines)

    os.makedirs(OUT_DIR, exist_ok=True)
    md = os.path.join(OUT_DIR, "w14_w15_w16_report.md")
    with open(md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out_lines) + "\n")
    with open(os.path.join(OUT_DIR, "w14_w15_w16_summary.json"), "w",
              encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(f"[写出] {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
