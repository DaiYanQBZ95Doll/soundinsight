# -*- coding: utf-8 -*-
"""W4：四五星音质评论开采（候选提取 + LLM 复核两段式）。

设计要点（对应冻结清单 §二 W4/W4b 与用户规则）：
- **第一段（候选提取）不需要任何凭证**：用与 `label_v3.py` 同源的关键词规则，
  在 4–5★ 评论中找"提到音质但未出现负面极性词"的候选——可直接运行（`--extract-only`）；
- **第二段（LLM 复核）需要凭证**，按下列顺序探测环境变量：
    1. `DEEPSEEK_API_KEY`  → DeepSeek 官方 API（复赛标注所用通道）
    2. `QWEN_TOKEN_PLAN_API_KEY` / `TOKEN_PLAN_API_KEY` → 阿里云百炼 Token Plan
   **渠道守则**：Token Plan 凭证按既定规则**仅用于收尾存证**；若只探测到它，
  必须显式设置 `DSH_ALLOW_TOKEN_PLAN_FOR_W4=1` 才允许用于本步，否则退出并提示。
- **W4b 上界规则**：候选量或新增正例 > 预期 3 倍时，自动改为**分层抽样复核**
  （按星级 × 关键组分层的等距抽样），并记录未复核比例。

产出：
- `v2/w4_candidates.csv`：候选（含星级、命中关键词、长度）
- `v2/w4_review.jsonl`：LLM 复核原始输出（追加写，可断点续跑）
- `v2/w4_summary.json`：计数、抽样策略、未复核比例

用法：
    python v2_w4_mine.py --extract-only          # 只提候选（无需凭证）
    python v2_w4_mine.py --review --limit 300    # 复核前 300 条（需凭证）
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v2")
SOURCE = os.path.join(HERE, "review_meta_v2.csv")       # P0-3 产物（含 rating/asin）
LLM_CSV = os.path.join(HERE, "labeled_llm.csv")
CAND = os.path.join(OUT, "w4_candidates.csv")
REVIEW = os.path.join(OUT, "w4_review.jsonl")
SUMMARY = os.path.join(OUT, "w4_summary.json")
SEED = 42
UPPER_FACTOR = 3          # W4b：超过预期 3 倍即转分层抽样

# 与 label_v3.py 同源的关键词组（音质相关）
SOUND_KW = ("sound", "audio", "bass", "treble", "clarity", "muffled", "distortion",
            "static", "volume", "loud", "quiet", "noise", "hiss", "rattle",
            "crackl", "tinny", "muddy", "vocal", "instrument", "equalizer", "eq")
# 明确正面极性词：仅出现这些而无线索词的，不进候选
POSITIVE_ONLY = ("great sound", "sound great", "excellent sound", "amazing sound",
                 "good sound", "love the sound", "perfect sound")

CHANNELS = (
    ("DEEPSEEK_API_KEY", "https://api.deepseek.com/v1", "deepseek-chat",
     "DeepSeek 官方 API"),
    ("QWEN_TOKEN_PLAN_API_KEY", "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
     "qwen3.7-plus", "阿里云百炼 Token Plan"),
    ("TOKEN_PLAN_API_KEY", "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
     "qwen3.7-plus", "阿里云百炼 Token Plan"),
)


def pick_channel():
    """返回 (env_name, base_url, model, label) 或 None。"""
    for env, base, model, label in CHANNELS:
        if os.environ.get(env):
            if "token-plan" in base and not os.environ.get("DSH_ALLOW_TOKEN_PLAN_FOR_W4"):
                print(f"[守则] 只探测到 {env}（{label}）。按规则该凭证仅用于收尾存证；"
                      f"若确认要用于 W4，请设置 DSH_ALLOW_TOKEN_PLAN_FOR_W4=1 后重跑。")
                return None
            return env, base, model, label
    return None


def extract() -> list[dict]:
    # 4–5★ 且当前标签为非正例（即从未被规则纳入候选）
    # 注意：review_meta_v2.csv **不含 text 列**（P0-3 只登记元数据），
    # 文本按行序从 labeled_llm.csv 取（两者行序已由 P0-3 实测对齐）。
    labels, texts = {}, {}
    with open(LLM_CSV, encoding="utf-8", errors="replace") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            labels[i] = int(float(row.get("sound_negative_llm") or 0))
            texts[i] = str(row.get("text") or "")
    cands = []
    with open(SOURCE, encoding="utf-8", errors="replace") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            rating = int(float(row.get("rating") or 0))
            if rating < 4:
                continue
            if labels.get(i, 0) == 1:      # 已是正例，跳过
                continue
            text = texts.get(i, "")
            if not text:
                continue
            low = text.lower()
            hits = [k for k in SOUND_KW if k in low]
            if not hits:
                continue
            if any(p in low for p in POSITIVE_ONLY):
                continue
            cands.append({"row_index": i, "rating": rating, "hits": ",".join(hits),
                          "n_hits": len(hits), "len_chars": len(text),
                          "text": text})
    return cands


def llm_review(text: str, env: str, base: str, model: str, timeout: int = 60) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content":
             "You are a strict annotator. Decide whether the review complains about "
             "headphone SOUND QUALITY (bass/clarity/noise/volume/treble). "
             "Answer JSON only: {\"sound_negative\": 0|1, \"classes\": [\"bass\"|\"clarity\"|"
             "\"noise\"|\"volume\"|\"treble\"], \"why\": \"<=12 words\"}"},
            {"role": "user", "content": text[:4000]},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {os.environ[env]}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    try:
        parsed = json.loads(content)
    except ValueError:
        parsed = {"parse_error": content[:200]}
    parsed["_usage"] = usage
    return parsed


def stratified_sample(cands: list[dict], n: int) -> tuple[list[dict], dict]:
    """按（星级 × 主关键词）分层等距抽样，返回样本与分层统计。

    W4b 规则：候选量超预期 3 倍时改用分层抽样复核，并**记录未复核比例**。
    """
    groups: dict[tuple, list[dict]] = {}
    for c in cands:
        key = (c["rating"], c["hits"].split(",")[0])
        groups.setdefault(key, []).append(c)
    rng = random.Random(SEED)
    per = max(1, n // max(len(groups), 1))
    sample = []
    for key, items in sorted(groups.items()):
        rng.shuffle(items)
        sample.extend(items[:per])
    sample = sample[:n]
    stats = {"n_groups": len(groups), "per_group": per, "n_sample": len(sample),
             "groups": {f"{k[0]}★/{k[1]}": len(v) for k, v in sorted(groups.items())}}
    return sample, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract-only", action="store_true")
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="复核条数上限（0＝全部）")
    ap.add_argument("--stratify", type=int, default=0,
                    help="按（星级×主关键词）分层抽样 N 条写入 w4_sample.csv（W4b）")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    if not os.path.isfile(SOURCE):
        print(f"[FAIL] 缺少 {os.path.basename(SOURCE)}（请先跑 recover_meta_fields.py）")
        return 1

    if args.extract_only or not args.review:
        cands = extract()
        print(f"[提取] 4–5★ 音质相关候选：{len(cands)} 条")
        if cands:
            by_star = {}
            for c in cands:
                by_star[c["rating"]] = by_star.get(c["rating"], 0) + 1
            print(f"  按星级：{by_star}")
            print(f"  命中关键词数分布：{sorted({c['n_hits'] for c in cands})}")
        with open(CAND, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["row_index", "rating", "hits", "n_hits",
                                               "len_chars", "text"])
            w.writeheader()
            w.writerows(cands)
        print(f"[写出] {os.path.relpath(CAND, HERE)}")
        # 预期量级：三星补漏曾复核 1,271 条确认 479 条（约 37.7%）
        expected = 300
        over = len(cands) > expected * UPPER_FACTOR
        print(f"[W4b 上界规则] 预期 ≈{expected}；实测 {len(cands)}；"
              f"{'> 3 倍 → 应转分层抽样复核' if over else '未触发'}")
        with open(SUMMARY, "w", encoding="utf-8") as fh:
            json.dump({"stage": "extract_only", "n_candidates": len(cands),
                       "by_star": {str(k): v for k, v in
                                   sorted({c['rating']: sum(1 for x in cands if x['rating'] == c['rating'])
                                           for c in cands}.items())},
                      "upper_rule": {"expected": expected, "factor": UPPER_FACTOR,
                                     "triggered": over},
                      "gen": "[v2]"}, fh, ensure_ascii=False, indent=2)
        print(f"[写出] {os.path.relpath(SUMMARY, HERE)}")
        if args.stratify:
            sample, st = stratified_sample(cands, args.stratify)
            sp = os.path.join(OUT, "w4_sample.csv")
            with open(sp, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=["row_index", "rating", "hits",
                                                   "n_hits", "len_chars", "text"])
                w.writeheader()
                w.writerows(sample)
            unrev = 1 - len(sample) / max(len(cands), 1)
            print(f"[W4b 分层抽样] {len(sample)} 条 / 候选 {len(cands)} 条 → "
                  f"未复核比例 {unrev:.2%}；分组 {st['n_groups']} 个（每组 ≈{st['per_group']}）")
            print(f"[写出] {os.path.relpath(sp, HERE)}")
            st["unreviewed_ratio"] = round(unrev, 4)
            st["candidates"] = len(cands)
            with open(os.path.join(OUT, "w4_strata.json"), "w", encoding="utf-8") as fh:
                json.dump(st, fh, ensure_ascii=False, indent=2)
        if not args.review:
            return 0

    # 复核段
    ch = pick_channel()
    if ch is None:
        print("[需要凭证] 未探测到可用 LLM 凭证。可选（按优先级）："
              "DEEPSEEK_API_KEY（DeepSeek 官方）／QWEN_TOKEN_PLAN_API_KEY（百炼 Token Plan，"
              "需 DSH_ALLOW_TOKEN_PLAN_FOR_W4=1）。设置后重跑本命令即可续跑。")
        return 2
    env, base, model, label = ch
    print(f"[渠道] {label}（{model}），环境变量 {env}")
    if not os.path.isfile(CAND):
        print("[FAIL] 缺少候选文件，请先跑 --extract-only")
        return 1
    rows = list(csv.DictReader(open(CAND, encoding="utf-8", errors="replace")))
    done = set()
    if os.path.isfile(REVIEW):
        for line in open(REVIEW, encoding="utf-8", errors="replace"):
            try:
                done.add(json.loads(line)["row_index"])
            except (ValueError, KeyError):
                continue
    todo = [r for r in rows if int(r["row_index"]) not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"[复核] 候选 {len(rows)}，已完成 {len(done)}，本次处理 {len(todo)}")
    ok = fail = 0
    with open(REVIEW, "a", encoding="utf-8") as fh:
        for k, r in enumerate(todo, 1):
            try:
                res = llm_review(r["text"], env, base, model)
                rec = {"row_index": int(r["row_index"]), "rating": int(r["rating"]),
                       "hits": r["hits"], **res}
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                ok += 1
            except Exception as e:  # noqa: BLE001
                fail += 1
                print(f"  [失败 {k}] {type(e).__name__}: {str(e)[:120]}")
                if fail >= 5 and ok == 0:
                    print("  [中止] 连续失败，检查凭证/网络后重跑（支持断点续跑）")
                    break
            if k % 25 == 0:
                print(f"  …{k}/{len(todo)}（成功 {ok}／失败 {fail}）")
    print(f"[复核完成] 成功 {ok}，失败 {fail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
