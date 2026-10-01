# -*- coding: utf-8 -*-
"""跨模型独立判定（DSH-R1 已获批；**等 Token Plan key 即可跑**）。

用途：用**另一个模型家族**（qwen3.7-plus，阿里云百炼 Token Plan）对金标工作表的同一批 300 条
做第二判定，产出**跨模型一致率与 Cohen's κ**。
定位（必须与结论同时出现）：这**不是**人类真值，只能把"LLM 自证"降级为"跨家族一致 + 未经人工校准"。

用法：
    set QWEN_TOKEN_PLAN_API_KEY=...      # 或 TOKEN_PLAN_API_KEY
    set DSH_ALLOW_TOKEN_PLAN_FOR_W4=1    # 显式放行（沿用既有守则）
    python cross_model_review.py --limit 300

产出：`v2/cross_model_review.jsonl` + `docs/decision_queue.md` 之外的汇总（`v2/cross_model_agreement.json`）
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import json
import os
import sys
import threading
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v2")
SHEET = os.path.join(HERE, "docs", "gold_set", "worksheet.csv")
KEYJSON = os.path.join(OUT, "gold_set_key.json")
REVIEW = os.path.join(OUT, "cross_model_review.jsonl")
SUMMARY = os.path.join(OUT, "cross_model_agreement.json")
BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen3.7-plus"
SYS = ("You are a strict annotator. Decide whether the review complains about "
       "headphone SOUND QUALITY (bass/clarity/noise/volume/treble). "
       "Answer JSON only: {\"sound_negative\": 0|1, \"classes\": [\"bass\"|\"clarity\"|"
       "\"noise\"|\"volume\"|\"treble\"], \"why\": \"<=12 words\"}")
_lock = threading.Lock()
_stat = {"ok": 0, "fail": 0}


def pick_key():
    if os.environ.get("DSH_ALLOW_TOKEN_PLAN_FOR_W4") != "1":
        return None, "未设置 DSH_ALLOW_TOKEN_PLAN_FOR_W4=1（Token Plan 使用需显式放行）"
    for v in ("QWEN_TOKEN_PLAN_API_KEY", "TOKEN_PLAN_API_KEY"):
        if os.environ.get(v):
            return os.environ[v], v
    return None, "未找到 QWEN_TOKEN_PLAN_API_KEY／TOKEN_PLAN_API_KEY"


def one(text: str, key: str, retries: int = 2):
    body = {"model": MODEL, "messages": [{"role": "system", "content": SYS},
                                        {"role": "user", "content": text[:4000]}],
            "temperature": 0, "response_format": {"type": "json_object"}}
    last = ""
    for a in range(retries + 1):
        try:
            req = urllib.request.Request(
                BASE + "/chat/completions", data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8"))
            parsed = json.loads(data["choices"][0]["message"]["content"])
            with _lock:
                _stat["ok"] += 1
            return parsed
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:80]}"
            time.sleep(1.5 * (a + 1))
    with _lock:
        _stat["fail"] += 1
    return {"_error": last}


def kappa(pairs):
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(1 for a, b in pairs if a == b) / n
    a1 = sum(1 for a, _ in pairs if a == 1) / n
    b1 = sum(1 for _, b in pairs if b == 1) / n
    pe = a1 * b1 + (1 - a1) * (1 - b1)
    return (po - pe) / (1 - pe) if pe != 1 else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    key, why = pick_key()
    if not key:
        print(f"[需要凭证] {why}")
        print("  决策方已同意提供（DSH-R1）；拿到后：")
        print("    $env:QWEN_TOKEN_PLAN_API_KEY='…'; $env:DSH_ALLOW_TOKEN_PLAN_FOR_W4='1'")
        print("    python cross_model_review.py --limit 300")
        return 2
    items = {r["编号"]: r["原文"] for r in csv.DictReader(
        open(SHEET, encoding="utf-8-sig", errors="replace"))}
    llm = {it["id"]: it.get("llm_label") for it in
           json.load(open(KEYJSON, encoding="utf-8"))["items"]}
    done = set()
    if os.path.isfile(REVIEW):
        for line in open(REVIEW, encoding="utf-8", errors="replace"):
            try:
                done.add(json.loads(line)["id"])
            except (ValueError, KeyError):
                continue
    todo = [(i, t) for i, t in items.items() if i not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"跨模型判定：{len(todo)} 条待跑（已完成 {len(done)}）｜并发 {args.workers}｜模型 {MODEL}")
    with open(REVIEW, "a", encoding="utf-8") as fh, \
            cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(one, t, key): i for i, t in todo}
        for k, fut in enumerate(cf.as_completed(futs), 1):
            i = futs[fut]
            res = fut.result()
            fh.write(json.dumps({"id": i, **res}, ensure_ascii=False) + "\n")
            if k % 50 == 0:
                fh.flush()
                print(f"  …{k}/{len(todo)}｜成功 {_stat['ok']}／失败 {_stat['fail']}")
    recs = {}
    for line in open(REVIEW, encoding="utf-8", errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if "sound_negative" in r:
            recs[r["id"]] = int(r["sound_negative"])
    pairs = [(int(llm[i]), recs[i]) for i in recs
             if i in llm and str(llm[i]) in ("0", "1")]
    agree = sum(1 for a, b in pairs if a == b) / len(pairs) * 100 if pairs else float("nan")
    kap = kappa(pairs)
    json.dump({"n": len(recs), "comparable": len(pairs), "agreement_pct": round(agree, 1),
               "kappa": round(kap, 3), "models": {"A": "deepseek-chat（标注方）", "B": MODEL},
               "caveat": "跨模型一致≠人类真值；材料须继续标注「未经人工校准」"},
              open(SUMMARY, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n[完成] 可比对 {len(pairs)} 条｜一致率 {agree:.1f}%｜κ {kap:.3f}")
    print(f"[写出] {os.path.relpath(SUMMARY, HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
