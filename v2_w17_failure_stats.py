# -*- coding: utf-8 -*-
"""W17 支撑：从冻结预测里抽取**真实**失败案例并计算发生率分母。

输出 → `v2/w17_failure_stats.json`（供 `docs/w17_failure_cases.md` 引用）
口径：
- 预测来自冻结 v1 模型在 val_v2 上的既有输出（`val_preds_dump.csv`）；
- 元数据按**文本**连接（下标不可用，见 v2_meta_analysis.py 的说明）；
- 每个失败类型都给出**分母与比例**（W17 DoD 要求，孤立的失败是噪音）。
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from v2_meta_analysis import (ISSUES, ISSUE_CN, LLM_CSV, build_text_index,  # noqa: E402
                              fnum, load_all, join_val, read_rows)

BUCKETS = ((0, 64, "≤64"), (65, 128, "65–128"), (129, 10 ** 9, ">128"))


def main() -> int:
    rows, placeholder = load_all()
    pred_rows = read_rows(os.path.join(HERE, "val_preds_dump.csv"))
    dummy = []
    preds = join_val(pred_rows, build_text_index(rows), dummy)

    # 长度桶（按字符数近似）。**必须在连接结果上就地计算**：
    # join_val 会跳过未命中行，若再用 zip(preds, pred_rows) 回填文本会整体错位
    # （2026-09-30 实测由此产生过错误的漂移结论，故文本由 join_val 直接带上）。
    for p in preds:
        n = len(p["text"])
        p["bucket"] = next(name for lo, hi, name in BUCKETS if lo <= n <= hi)

    fp = [p for p in preds if p["pred"] == 1 and p["label"] == 0]
    fn = [p for p in preds if p["pred"] == 0 and p["label"] == 1]
    tp = [p for p in preds if p["pred"] == 1 and p["label"] == 1]
    tn = [p for p in preds if p["pred"] == 0 and p["label"] == 0]
    n_pos = len(tp) + len(fn)
    n_neg = len(fp) + len(tn)
    print(f"val 集：n={len(preds)} 正例={n_pos} 负例={n_neg} | TP={len(tp)} FP={len(fp)} FN={len(fn)} TN={len(tn)}")

    stats = {"n": len(preds), "n_pos": n_pos, "n_neg": n_neg,
             "TP": len(tp), "FP": len(fp), "FN": len(fn), "TN": len(tn),
             "placeholder_rows": placeholder, "modes": [], "exemplars": {}}

    # 1) 按星级的误报/漏报率
    star_tab = {}
    for star in range(1, 6):
        sub = [p for p in preds if p["star"] == star]
        s_fp = sum(1 for p in sub if p["pred"] == 1 and p["label"] == 0)
        s_fn = sum(1 for p in sub if p["pred"] == 0 and p["label"] == 1)
        s_pos = sum(1 for p in sub if p["label"] == 1)
        s_neg = len(sub) - s_pos
        star_tab[star] = {"n": len(sub), "pos": s_pos, "neg": s_neg,
                          "FP": s_fp, "FN": s_fn,
                          "FP_rate_neg": round(s_fp / s_neg * 100, 2) if s_neg else None,
                          "FN_rate_pos": round(s_fn / s_pos * 100, 2) if s_pos else None}
    stats["by_star"] = star_tab

    # 2) 按长度桶
    buck_tab = {}
    for lo, hi, name in BUCKETS:
        sub = [p for p in preds if p["bucket"] == name]
        s_fp = sum(1 for p in sub if p["pred"] == 1 and p["label"] == 0)
        s_fn = sum(1 for p in sub if p["pred"] == 0 and p["label"] == 1)
        s_pos = sum(1 for p in sub if p["label"] == 1)
        s_neg = len(sub) - s_pos
        buck_tab[name] = {"n": len(sub), "pos": s_pos,
                          "FP": s_fp, "FN": s_fn,
                          "FP_rate_neg": round(s_fp / s_neg * 100, 2) if s_neg else None,
                          "FN_rate_pos": round(s_fn / s_pos * 100, 2) if s_pos else None}
    stats["by_bucket"] = buck_tab

    # 3) 已验证购买 vs 未验证
    ver_tab = {}
    for name, key in (("verified_true", True), ("verified_false", False)):
        sub = [p for p in preds if p["verified"] is key]
        s_fp = sum(1 for p in sub if p["pred"] == 1 and p["label"] == 0)
        s_neg = sum(1 for p in sub if p["label"] == 0)
        ver_tab[name] = {"n": len(sub), "neg": s_neg, "FP": s_fp,
                         "FP_rate_neg": round(s_fp / s_neg * 100, 2) if s_neg else None}
    stats["by_verified"] = ver_tab

    # 4) 漏报按问题类别分布（金标准标签口径）
    #    注意：不能要求候选行当前 label==1——val_v2 标签冻结于旧版标签集，
    #    现行 labeled_llm 对同一文本可能已改为 0；这里只取该文本的五类标签。
    fn_issue = Counter()
    text_idx = build_text_index(rows)
    for p in fn:
        cand = text_idx.get(p["text"])
        if not cand:
            continue
        row = cand[0]
        for k in ISSUES:
            if row["issues"][k]:
                fn_issue[ISSUE_CN[k]] += 1
    stats["fn_issue_dist"] = dict(fn_issue.most_common())
    stats["fn_issue_note"] = ("口径：对每条漏报取同一文本在当前标签集中的五类标签；"
                              "可多标签并存；命中率低说明该漏报文本在当前标签集中未被标为任何类别。")

    # 4b) 关键区分：模型错 vs 标签代际漂移
    #     val_v2 标签冻结于旧标签集；现行 labeled_llm 对同一文本可能已改判。
    #     若现行标签与模型预测一致，则该"错误"实为代际口径差异，不是模型能力问题。
    #     实现说明：直接用 labeled_llm 建"文本 → 现行标签"映射（不经 rows 下标，
    #     避免重复文本取行歧义；2026-09-30 修正了此前的取反错误）。
    cur_label = {}
    with open(LLM_CSV, encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            t = str(r["text"])
            if t not in cur_label:
                cur_label[t] = int(fnum(r.get("sound_negative_llm"), 0) or 0)
    drift = {"FN": {"total": len(fn), "found": 0, "current_label_1": 0,
                    "current_label_0": 0},
             "FP": {"total": len(fp), "found": 0, "current_label_1": 0,
                    "current_label_0": 0}}
    drift_fp_examples = []
    for name, group in (("FN", fn), ("FP", fp)):
        for p in group:
            t = str(p["text"])
            cl = cur_label.get(t)
            if cl is None:
                cl = cur_label.get(t.strip())
            if cl is None:
                continue
            drift[name]["found"] += 1
            if cl == 1:
                drift[name]["current_label_1"] += 1
            else:
                drift[name]["current_label_0"] += 1
            if name == "FP" and cl == 1 and len(drift_fp_examples) < 3:
                drift_fp_examples.append({"text": p["text"][:160].replace("\n", " "),
                                          "prob": round(p["prob"], 4),
                                          "star": p["star"]})
    drift["FP_examples_current_positive"] = drift_fp_examples
    drift["note"] = ("found=能在现行标签集中定位到的条数；current_label_1/0=现行标签为"
                     "正例/负例的条数。current_label_1 的 FP 表示：现行标签已认同模型的"
                     "判正，该差异属代际口径漂移而非模型误报；"
                     "current_label_0 的 FN 反之（现行标签已认同模型的判负）。")
    stats["label_drift"] = drift
    print("代际漂移：", json.dumps(drift, ensure_ascii=False)[:400])

    # 5) 真实案例：FP 取概率最高的 5 条；FN 取概率最低的 5 条
    def brief(p):
        return {"text": p["text"][:220].replace("\n", " "),
                "prob": round(p["prob"], 4), "star": p["star"],
                "verified": p["verified"], "asin": p["asin"],
                "len_chars": len(p["text"]), "bucket": p["bucket"]}
    stats["exemplars"]["FP_top"] = [brief(p) for p in
                                    sorted(fp, key=lambda x: -x["prob"])[:5]]
    stats["exemplars"]["FN_low"] = [brief(p) for p in
                                    sorted(fn, key=lambda x: x["prob"])[:5]]

    os.makedirs(os.path.join(HERE, "v2"), exist_ok=True)
    with open(os.path.join(HERE, "v2", "w17_failure_stats.json"), "w",
              encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2)
    print("[写出] v2/w17_failure_stats.json")
    print("按星级：", {k: {kk: vv for kk, vv in v.items() if kk in
                       ("n", "FP", "FN", "FP_rate_neg", "FN_rate_pos")}
                   for k, v in star_tab.items()})
    print("按长度：", buck_tab)
    print("已验证：", ver_tab)
    print("漏报问题分布：", dict(fn_issue.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
