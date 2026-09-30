# -*- coding: utf-8 -*-
"""闸门外真阳性率的测量脚本（待凭证触发）。

背景：`docs/difficulty_stratification.md` 披露"评测集继承关键词闸门"——不含一阶关键词的评论
（占语料 86.9%）在构造上不可能被标为正例，因此**闸门外的真阳性率从未测量**。
模型代理测量（`docs/outside_gate_fp.md`）只给出"模型判正率 0.03%"，不能替代真值。

本脚本把它变成**一条命令**：抽样 → LLM 复核 → Wilson CI → 外推 → 全语料召回上界。

用法：
    python v2_gate_outside_probe.py --extract --n 300     # 抽样本（无需凭证）
    python v2_gate_outside_probe.py --review --limit 300  # LLM 复核（需凭证，可断点续跑）
    python v2_gate_outside_probe.py --estimate            # 出结论（无需凭证）

渠道守则与 W4 相同：优先 `DEEPSEEK_API_KEY`；Token Plan 变量需 `DSH_ALLOW_TOKEN_PLAN_FOR_W4=1` 显式放行。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_w4_mine import llm_review, pick_channel  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v2")
CORPUS = os.path.join(HERE, "labeled_llm.csv")
SAMPLE = os.path.join(OUT, "gate_outside_sample.csv")
REVIEW = os.path.join(OUT, "gate_outside_review.jsonl")
SEED = 42
SOUND_KEYWORDS = [
    "sound", "audio", "bass", "treble", "clarity", "muffled", "distortion",
    "static", "hiss", "crisp", "muddy", "volume", "pitch", "frequency",
    "crackling", "popping", "sibilance", "tinny", "boomy", "hollow",
    "scratchy", "buzzing", "rattling",
]
RX = re.compile(r"\b(?:" + "|".join(map(re.escape, SOUND_KEYWORDS)) + r")\b", re.I)


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - r) / d), min(1.0, (c + r) / d)


def extract(n: int) -> int:
    rows = []
    with open(CORPUS, encoding="utf-8", errors="replace") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            t = str(r.get("text") or "")
            if len(t) < 40 or RX.search(t):
                continue
            rows.append({"row_index": i, "text": t,
                         "rating": r.get("rating", "")})
    rng = random.Random(SEED)
    rng.shuffle(rows)
    sample = rows[:n]
    with open(SAMPLE, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["row_index", "rating", "text"])
        w.writeheader()
        w.writerows(sample)
    print(f"[抽样] 闸门外语料 {len(rows):,} 条 → 抽 {len(sample)} 条 → {os.path.basename(SAMPLE)}")
    print("  抽样口径：不含任何一阶关键词、长度 ≥40 字符；seed 42 洗牌后取前 N（可复算）")
    return 0


def review(limit: int) -> int:
    ch = pick_channel()
    if ch is None:
        print("[需要凭证] 未探测到可用 LLM 凭证（顺序：DEEPSEEK_API_KEY → "
              "QWEN_TOKEN_PLAN_API_KEY／TOKEN_PLAN_API_KEY，后者需 DSH_ALLOW_TOKEN_PLAN_FOR_W4=1）")
        return 2
    env, base, model, label = ch
    print(f"[渠道] {label}（{model}）")
    rows = list(csv.DictReader(open(SAMPLE, encoding="utf-8", errors="replace")))
    done = set()
    if os.path.isfile(REVIEW):
        for line in open(REVIEW, encoding="utf-8", errors="replace"):
            try:
                done.add(json.loads(line)["row_index"])
            except (ValueError, KeyError):
                continue
    todo = [r for r in rows if int(r["row_index"]) not in done][:limit or None]
    print(f"[复核] 样本 {len(rows)}，已完成 {len(done)}，本次 {len(todo)}")
    ok = fail = 0
    with open(REVIEW, "a", encoding="utf-8") as fh:
        for k, r in enumerate(todo, 1):
            try:
                res = llm_review(r["text"], env, base, model)
                fh.write(json.dumps({"row_index": int(r["row_index"]), **res},
                                    ensure_ascii=False) + "\n")
                fh.flush()
                ok += 1
            except Exception as e:  # noqa: BLE001
                fail += 1
                print(f"  [失败 {k}] {type(e).__name__}: {str(e)[:100]}")
                if fail >= 5 and ok == 0:
                    print("  [中止] 连续失败，检查凭证/网络后重跑（支持断点续跑）")
                    break
    print(f"[完成] 成功 {ok}／失败 {fail}")
    return 0


def estimate() -> int:
    if not os.path.isfile(REVIEW):
        print("[等待] 尚无 v2/gate_outside_review.jsonl —— 先跑 --review")
        return 0
    k = n = 0
    for line in open(REVIEW, encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "sound_negative" in rec:
            n += 1
            k += int(rec["sound_negative"])
    if n == 0:
        print("[等待] 复核文件无有效记录")
        return 0
    lo, hi = wilson(k, n)
    corpus_rows = sum(1 for _ in open(CORPUS, encoding="utf-8", errors="replace")) - 1
    outside_rows = sum(
        1 for r in csv.DictReader(open(CORPUS, encoding="utf-8", errors="replace"))
        if not RX.search(str(r.get("text") or "")))
    est = k / n * outside_rows
    print(f"[闸门外真阳性率] {k}/{n} = {k/n*100:.2f}%（Wilson 95% CI {lo*100:.2f}–{hi*100:.2f}%）")
    print(f"[外推] 闸门外语料 {outside_rows:,} 条 → 预计真阳性 ≈ **{est:,.0f}** 条"
          f"（95% CI {lo*outside_rows:,.0f} – {hi*outside_rows:,.0f}）")
    print(f"[对照] 闸门内已标注正例 1,280 条")
    if k > 0:
        total = 1280 + est
        print(f"[全语料含义] 若闸门外确有真阳性，正例总量 ≈ {total:,.0f} 条；"
              f"现有指标（关键词可达子集口径）外推到全语料时，召回需按 "
              f"{1280/total*100:.1f}% 折算（**上界口径**）")
    else:
        print("[全语料含义] 该样本未命中真阳性 → 闸门外真阳性率的上界为 "
              f"{hi*100:.2f}%（Wilson 上界），据此闸门外真阳性 ≤ {hi*outside_rows:,.0f} 条")
    json.dump({"n": n, "positives": k, "rate": round(k/n, 4),
               "wilson95": [round(lo, 4), round(hi, 4)],
               "outside_rows": outside_rows,
               "estimate": round(est, 1),
               "estimate_ci95": [round(lo*outside_rows, 1), round(hi*outside_rows, 1)],
               "gate_inside_positives": 1280, "gen": "[v2]"},
              open(os.path.join(OUT, "gate_outside_estimate.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[写出] v2/gate_outside_estimate.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if args.extract:
        return extract(args.n)
    if args.review:
        return review(args.limit)
    if args.estimate:
        return estimate()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
