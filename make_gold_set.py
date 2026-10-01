# -*- coding: utf-8 -*-
"""生成**独立人工金标集**（盲评）：三层各 100 条 + 工作表（CSV/Markdown）+ 映射密钥。

为什么需要（红队刺 1、刺 2）：当前全部验证标签（含 val_v3_test）都出自 LLM，模型也由 LLM 标签
训练——等于「同一个证人既当眼睛又当尺子」。本工具产出一块**非 LLM 来源**的人工金标，
用于：① 校准 LLM 判定的可靠度（一致率与 κ）；② 此后对外 F1/召回改在人工金标上报。

分层（各 100 条，seed 42 可复算）：
  S1 闸门外随机      —— 校准「闸门外真阳性 1.33%」这一说法
  S2 四五星候选池     —— 校准 W4 的 1.0%／3.1%
  S3 现有已标注集     —— **标签质量本身**（50 条 LLM 正例 + 50 条 LLM 负例）

盲评：工作表只给「编号 + 原文」；LLM 判定与模型分数存放在 `v2/gold_set_key.json`（**勿给标注者**）。
用法：python make_gold_set.py [--per-stratum 100]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v2")
GDIR = os.path.join(HERE, "docs", "gold_set")
SEED = 42
KW = ["sound", "audio", "bass", "treble", "clarity", "muffled", "distortion", "static",
      "hiss", "crisp", "muddy", "volume", "pitch", "frequency", "crackling", "popping",
      "sibilance", "tinny", "boomy", "hollow", "scratchy", "buzzing", "rattling"]
RX = re.compile(r"\b(?:" + "|".join(map(re.escape, KW)) + r")\b", re.I)


def load_corpus():
    rows = []
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            rows.append({"row_index": i, "text": str(r.get("text") or ""),
                         "rating": r.get("rating", ""),
                         "llm_label": r.get("sound_negative_llm", "")})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-stratum", type=int, default=100)
    args = ap.parse_args()
    n = args.per_stratum
    os.makedirs(GDIR, exist_ok=True)
    rng = random.Random(SEED)
    corpus = load_corpus()

    # S1/S2 必须从**已复核过**的条目里抽——否则没有 LLM 判定可对齐，算不出一致率与 κ。
    outside = [r for r in corpus if len(r["text"]) >= 40 and not RX.search(r["text"])]
    gate_reviewed = {int(json.loads(l)["row_index"]) for l in
                     open(os.path.join(OUT, "gate_outside_review.jsonl"),
                          encoding="utf-8", errors="replace") if "sound_negative" in l}
    s1_pool = [r for r in outside if r["row_index"] in gate_reviewed]
    rng.shuffle(s1_pool)
    s1 = s1_pool[:n]

    w4_reviewed = {}
    for line in open(os.path.join(OUT, "w4_review.jsonl"), encoding="utf-8",
                     errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "sound_negative" in rec:
            w4_reviewed[int(rec["row_index"])] = int(rec["sound_negative"])
    cands = []
    with open(os.path.join(OUT, "w4_candidates.csv"), encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            idx = int(r["row_index"])
            if idx in w4_reviewed:
                cands.append({"row_index": idx, "text": r["text"],
                              "rating": r["rating"], "llm_label": w4_reviewed[idx]})
    rng.shuffle(cands)
    s2 = cands[:n]

    pos = [r for r in corpus if str(r["llm_label"]) == "1"]
    neg = [r for r in corpus if str(r["llm_label"]) == "0" and len(r["text"]) >= 40]
    rng.shuffle(pos)
    rng.shuffle(neg)
    s3 = pos[:n // 2] + neg[:n // 2]
    rng.shuffle(s3)

    items, key = [], []
    # S1 的「LLM 判定」必须是**探测复核**的判定（校准 1.33% 用），
    # 不是语料里的管线标签（闸门外那批在管线里恒为 0，不反映复核结论）
    gate_labels = {}
    for line in open(os.path.join(OUT, "gate_outside_review.jsonl"), encoding="utf-8",
                     errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "sound_negative" in rec:
            gate_labels[int(rec["row_index"])] = int(rec["sound_negative"])
    for r in s1:
        r["llm_label"] = gate_labels.get(int(r["row_index"]), "")

    for tag, group in (("S1", s1), ("S2", s2), ("S3", s3)):
        for r in group:
            iid = f"{tag}-{len([x for x in items if x['stratum'] == tag]) + 1:03d}"
            items.append({"id": iid, "stratum": tag, "text": r["text"]})
            key.append({"id": iid, "stratum": tag, "row_index": r["row_index"],
                        "rating": r.get("rating", ""), "llm_label": r.get("llm_label", "")})
    rng.shuffle(items)          # 打乱层间顺序，进一步降偏

    # 工作表（CSV，带 BOM 便于 Excel 打开；人工只填「人工判定」列）
    csv_path = os.path.join(GDIR, "worksheet.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["编号", "原文", "人工判定(1=音质差评/0=不是)", "备注(可选)"])
        for it in items:
            w.writerow([it["id"], it["text"], "", ""])

    md_path = os.path.join(GDIR, "worksheet.md")
    with open(md_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# 人工金标工作表（盲评）\n\n"
                 "> **只依据原文判断**：这条评论是否在抱怨**耳机/耳塞/头戴**的音质"
                 "（低音／清晰度／杂音／音量／高音）？\n"
                 "> 判为**是**填 `1`，**不是**填 `0`；无法判断产品是不是耳机 → 填 `?`。\n"
                 "> 请在 `docs/gold_set/worksheet.csv` 的「人工判定」列填写（Excel 可直接打开）。\n"
                 "> 工作表**不含**任何 LLM 判定或模型分数（盲评）；映射见 `v2/gold_set_key.json`。\n\n"
                 "| 编号 | 原文（截断显示） |\n|---|---|\n")
        for it in items:
            t = it["text"].replace("|", "｜").replace("\n", " ")[:160]
            fh.write(f"| {it['id']} | {t} |\n")

    with open(os.path.join(OUT, "gold_set_key.json"), "w", encoding="utf-8") as fh:
        json.dump({"seed": SEED, "per_stratum": n, "items": key,
                   "note": "**勿给标注者**；用于评分时对齐 LLM 判定与人工判定"},
                  fh, ensure_ascii=False, indent=2)

    print(f"[写出] {os.path.relpath(csv_path, HERE)}（{len(items)} 条，待人工填写）")
    print(f"[写出] {os.path.relpath(md_path, HERE)}")
    print(f"[写出] v2/gold_set_key.json（映射密钥，勿给标注者）")
    print(f"\n人工耗时估计：{len(items)} 条 × 20–35 秒 ≈ "
          f"{len(items)*20/60:.0f}–{len(items)*35/60:.0f} 分钟")
    print("填写后运行：python score_gold_set.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
