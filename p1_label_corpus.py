# -*- coding: utf-8 -*-
"""P1 全语料 LLM 标注：一次产出三种标签（是否音质抱怨 / 差评类型 / 不可归因原因）。

设计：并发 12、失败重试 2、**断点续跑**、逐条记录 token 用量（成本可核算）。
提示词与类型表见 docs/p1_preregistration.md（**先注册后执行**）。
用法：python p1_label_corpus.py [--limit N] [--workers 12]
产物：v2/p1_labels.jsonl、v2/p1_labels_summary.json
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
BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL = "deepseek-chat"
TYPES = ["连接/配对", "续航/充电", "做工/耐用", "佩戴/舒适", "麦克风/通话", "功能/操作",
         "物流/包装", "价格/性价比", "客服/售后", "描述不符/假货", "音质(听感)",
         "非负面/无抱怨", "其他"]
VAGUE = ["NONE", "sound_vague", "anc_only", "functional_not_sound", "weak_praise",
         "not_headphone", "insufficient"]
SYS = ("You are a strict annotator for a headphone-seller analytics tool. Read the review and "
       "answer JSON only: {\"sound_complaint\": 0|1, \"types\": [\"...\"], \"vague_reason\": \"...\"}. "
       "sound_complaint=1 only if the review complains about SOUND/listening experience "
       "(bass/clarity/noise/volume/treble/distortion, or ANC/leakage affecting listening); "
       "otherwise 0. types: 0+ items from " + json.dumps(TYPES, ensure_ascii=False) +
       " (use 非负面/无抱怨 for neutral or positive reviews; 音质(听感) when sound is the complaint). "
       "vague_reason: exactly one of " + json.dumps(VAGUE, ensure_ascii=False) +
       " — use anc_only when the only sound-related content is noise-cancelling, sound_vague when "
       "sound is mentioned without a concrete symptom, functional_not_sound for non-sound faults, "
       "weak_praise for mild praise, not_headphone when the product is not a headphone/earbud, "
       "insufficient when there is too little information, NONE otherwise.")

_lock = threading.Lock()
_stat = {"ok": 0, "fail": 0, "ptok": 0, "ctok": 0}


def label_one(item, key, retries=2):
    body = {"model": MODEL, "temperature": 0,
            "messages": [{"role": "system", "content": SYS},
                         {"role": "user", "content": item["text"][:4000]}],
            "response_format": {"type": "json_object"}}
    last = ""
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(
                BASE.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
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
            return {"row_index": item["row_index"], **parsed, "_usage": usage}
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
    with _lock:
        _stat["fail"] += 1
    return {"row_index": item["row_index"], "error": last[:200]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        print("[需要凭证] 未注入 DEEPSEEK_API_KEY")
        return 2
    texts = []
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            texts.append(str(r.get("text") or ""))
    sample = json.load(open(os.path.join(OUT, "p1_label_sample.json"),
                            encoding="utf-8"))["row_index"]
    if a.limit:
        sample = sample[:a.limit]
    out_path = os.path.join(OUT, "p1_labels.jsonl")
    done = set()
    if os.path.isfile(out_path):
        for line in open(out_path, encoding="utf-8", errors="replace"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if "sound_complaint" in rec:
                done.add(int(rec["row_index"]))
    todo = [{"row_index": i, "text": texts[i]} for i in sample if i not in done]
    print(f"样本 {len(sample):,}｜已完成 {len(done):,}｜本次 {len(todo):,}｜并发 {a.workers}")
    t0 = time.time()
    with open(out_path, "a", encoding="utf-8") as fh, \
            cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(label_one, it, key) for it in todo]
        for k, fut in enumerate(cf.as_completed(futs), 1):
            fh.write(json.dumps(fut.result(), ensure_ascii=False) + "\n")
            if k % 500 == 0 or k == len(todo):
                fh.flush()
                el = time.time() - t0
                print(f"  …{k:,}/{len(todo):,}｜成功 {_stat['ok']}／失败 {_stat['fail']}"
                      f"｜{k/el:.1f} 条/秒｜剩余约 {(len(todo)-k)/(k/el)/60:.0f} 分钟", flush=True)
    el = time.time() - t0
    cost = _stat["ptok"] / 1e6 * 0.27 + _stat["ctok"] / 1e6 * 1.10
    print(f"\n[完成] 成功 {_stat['ok']}／失败 {_stat['fail']}｜耗时 {el/60:.1f} 分钟"
          f"｜**实测成本 ≈ ${cost:.4f}**")
    json.dump({"n_sample": len(sample), "ok": _stat["ok"], "fail": _stat["fail"],
               "minutes": round(el / 60, 1), "usd": round(cost, 4),
               "prompt_tokens": _stat["ptok"], "completion_tokens": _stat["ctok"]},
              open(os.path.join(OUT, "p1_labels_summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
