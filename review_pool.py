# -*- coding: utf-8 -*-
"""并发复核器（B-测量专用）：对指定分层池做 LLM 复核，**逐条记录 token 用量**（用于成本核算）。

设计要点：
  · **提示词与 `v2_w4_mine.py::llm_review` 逐字一致**（保证与既有 W4/闸门外复核同口径）；
  · 线程池并发（默认 12），失败重试 2 次；**断点续跑**（已完成的 row_index 跳过）；
  · 记录每次调用的 prompt/completion tokens → 可算**实测单价**，直接回答红队刺 6（成本是否低估）。

用法：
    python review_pool.py --layer longtext --workers 12      # 长文本桶（闸门外且 >128 词）
    python review_pool.py --layer treble   --workers 12      # 高音关键词桶
    python review_pool.py --layer longtext --limit 200       # 先小批试跑
    python review_pool.py --report                            # 成本与产出汇总

产出：`v2/review_<layer>.jsonl`（逐条）+ `v2/review_<layer>_summary.json`（用量与耗时）
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "v2")
CORPUS = os.path.join(HERE, "labeled_llm.csv")
BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL = "deepseek-chat"
SYS_PROMPT = ("You are a strict annotator. Decide whether the review complains about "
              "headphone SOUND QUALITY (bass/clarity/noise/volume/treble). "
              "Answer JSON only: {\"sound_negative\": 0|1, \"classes\": [\"bass\"|\"clarity\"|"
              "\"noise\"|\"volume\"|\"treble\"], \"why\": \"<=12 words\"}")
KW = ["sound", "audio", "bass", "treble", "clarity", "muffled", "distortion", "static",
      "hiss", "crisp", "muddy", "volume", "pitch", "frequency", "crackling", "popping",
      "sibilance", "tinny", "boomy", "hollow", "scratchy", "buzzing", "rattling"]
TREBLE = ["treble", "pitch", "frequency", "highs", "high-pitched", "sibilance", "tinny"]
RX = re.compile(r"\b(?:" + "|".join(map(re.escape, KW)) + r")\b", re.I)
RX_T = re.compile(r"\b(?:" + "|".join(map(re.escape, TREBLE)) + r")\b", re.I)

_lock = threading.Lock()
_stat = {"ok": 0, "fail": 0, "ptok": 0, "ctok": 0}


def build_pool(layer: str) -> list[dict]:
    rows = []
    with open(CORPUS, encoding="utf-8", errors="replace") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            t = str(r.get("text") or "")
            if len(t) < 40:
                continue
            if layer == "longtext":
                if not RX.search(t) and len(t.split()) > 128:
                    rows.append({"row_index": i, "text": t,
                                 "words": len(t.split())})
            elif layer == "treble":
                if RX_T.search(t):
                    rows.append({"row_index": i, "text": t, "words": len(t.split())})
    return rows


def review_one(item: dict, key: str, retries: int = 2) -> dict:
    body = {"model": MODEL,
            "messages": [{"role": "system", "content": SYS_PROMPT},
                         {"role": "user", "content": item["text"][:4000]}],
            "temperature": 0, "response_format": {"type": "json_object"}}
    last = ""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                BASE.rstrip("/") + "/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {}) or {}
            try:
                parsed = json.loads(content)
            except ValueError:
                parsed = {"parse_error": content[:200]}
            with _lock:
                _stat["ok"] += 1
                _stat["ptok"] += int(usage.get("prompt_tokens") or 0)
                _stat["ctok"] += int(usage.get("completion_tokens") or 0)
            return {"row_index": item["row_index"], "words": item["words"], **parsed,
                    "_usage": usage}
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:80]}"
            time.sleep(1.5 * (attempt + 1))
    with _lock:
        _stat["fail"] += 1
    return {"row_index": item["row_index"], "words": item["words"], "_error": last}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=["longtext", "treble"])
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    if args.report:
        for layer in ("longtext", "treble"):
            p = os.path.join(OUT, f"review_{layer}.jsonl")
            if not os.path.isfile(p):
                print(f"  {layer}: 尚无结果")
                continue
            recs = [json.loads(l) for l in open(p, encoding="utf-8", errors="replace")
                    if l.strip()]
            ok = [r for r in recs if "sound_negative" in r]
            pt = sum(int((r.get("_usage") or {}).get("prompt_tokens") or 0) for r in ok)
            ct = sum(int((r.get("_usage") or {}).get("completion_tokens") or 0) for r in ok)
            pos = sum(int(r["sound_negative"]) for r in ok)
            print(f"  {layer}: 完成 {len(ok)}（失败 {len(recs)-len(ok)}）｜判正 {pos}"
                  f"｜prompt {pt:,} tok｜completion {ct:,} tok")
            if ok:
                print(f"     平均 {pt/len(ok):.0f} prompt tok/条｜"
                      f"按 deepseek-chat 定价（输入 $0.27/M、输出 $1.10/M，缓存未命中）"
                      f"≈ ${(pt/1e6*0.27 + ct/1e6*1.10):.3f}")
        return 0

    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        print("[需要凭证] 未注入 DEEPSEEK_API_KEY")
        return 2
    pool = build_pool(args.layer)
    if args.limit:
        pool = pool[:args.limit]
    out_path = os.path.join(OUT, f"review_{args.layer}.jsonl")
    done = set()
    if os.path.isfile(out_path):
        for line in open(out_path, encoding="utf-8", errors="replace"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if "sound_negative" in rec:
                done.add(int(rec["row_index"]))
    todo = [x for x in pool if x["row_index"] not in done]
    print(f"[{args.layer}] 池 {len(pool):,} 条｜已完成 {len(done):,}｜本次 {len(todo):,}"
          f"｜并发 {args.workers}")
    t0 = time.time()
    with open(out_path, "a", encoding="utf-8") as fh, \
            cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(review_one, it, key): it for it in todo}
        for k, fut in enumerate(cf.as_completed(futs), 1):
            rec = fut.result()
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if k % 200 == 0 or k == len(todo):
                fh.flush()
                el = time.time() - t0
                rate = k / el if el else 0
                eta = (len(todo) - k) / rate / 60 if rate else 0
                print(f"  …{k:,}/{len(todo):,}｜成功 {_stat['ok']}／失败 {_stat['fail']}"
                      f"｜{rate:.1f} 条/秒｜剩余约 {eta:.0f} 分钟")
    el = time.time() - t0
    summary = {"layer": args.layer, "pool": len(pool), "done": len(todo),
               "ok": _stat["ok"], "fail": _stat["fail"],
               "prompt_tokens": _stat["ptok"], "completion_tokens": _stat["ctok"],
               "elapsed_sec": round(el, 1),
               "cost_usd_est": round(_stat["ptok"] / 1e6 * 0.27
                                     + _stat["ctok"] / 1e6 * 1.10, 4)}
    json.dump(summary, open(os.path.join(OUT, f"review_{args.layer}_summary.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[完成] {args.layer}：成功 {_stat['ok']}／失败 {_stat['fail']}｜"
          f"耗时 {el/60:.1f} 分钟｜**实测成本 ≈ ${summary['cost_usd_est']}**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
