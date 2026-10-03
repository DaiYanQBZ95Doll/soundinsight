# -*- coding: utf-8 -*-
"""产品口径判定（D-Q8 的量化基础）：判定每条评论**说的是什么产品**，以估计"口径外"占比。

为什么需要：人工金标显示，随机抽样的 LLM 正例里仅 30.2% 被确认为"耳机音质差评"，
其中 28/30 是口径外产品（音箱/线缆/天线…）。本脚本把该结论**从 50 条样本推广到全量**。

严格中性：只判**产品类型**，不判情感、不判是否抱怨（那是决策方的题）。

目标：① `labeled_llm.csv` 中 LLM 标为正例的 1,280 条；② `val_v3_test.csv` 全部 10,000 条。
用法：python scope_classify.py [--limit N] [--workers 10]
产物：v2/scope_rows.jsonl（可续跑）、v2/scope_summary.json
"""
from __future__ import annotations

import argparse
import collections
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
CACHE = os.path.join(OUT, "scope_rows.jsonl")
BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL = "deepseek-chat"
CATS = ("headphone", "earbud", "headset", "speaker", "soundbar", "cable", "other_audio",
        "non_audio", "unclear")
SYS = ('You classify the PRODUCT TYPE of an Amazon review. Return JSON only: {"category": "<headphone|earbud|headset|speaker|soundbar|cable|other_audio|non_audio|unclear>"}. Rules: (1) headphone/earbud/headset = anything worn on the head or in the ears, including earbuds, in-ear monitors, gaming headsets, bluetooth earbuds, ear cups, headbands, ear tips, ear hooks; if the review discusses the sound of something worn in/on the ears, choose this family. (2) speaker/soundbar = standalone speakers, party speakers, TV soundbars, car speakers. (3) other_audio = audio gear not worn: amplifiers, DACs, receivers, microphones, turntables, audio mixers. (4) cable = cables, adapters, connectors. (5) non_audio = everything else. (6) unclear = ONLY when the text contains no product clue at all. Always pick the single best category; do NOT judge sentiment or complaints.')

_lock = threading.Lock()
_stat = collections.Counter()


def call(text: str, key: str, retries: int = 2) -> dict:
    body = {"model": MODEL, "messages": [{"role": "system", "content": SYS},
                                        {"role": "user", "content": text[:2200]}],
            "temperature": 0, "response_format": {"type": "json_object"}}
    for a in range(retries + 1):
        try:
            req = urllib.request.Request(BASE.rstrip("/") + "/chat/completions",
                                         data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read().decode("utf-8"))
            p = json.loads(d["choices"][0]["message"]["content"])
            c = str(p.get("category", "")).strip().lower()
            if c not in CATS:
                c = "unclear"
            with _lock:
                _stat[c] += 1
            return {"category": c, "why": str(p.get("why", ""))[:40]}
        except Exception:  # noqa: BLE001
            time.sleep(1.0 * (a + 1))
    with _lock:
        _stat["_fail"] += 1
    return {"category": "unclear", "why": "api_fail"}


def target_rows():
    """返回 [(uid, text)]：uid = 'lab:<row_index>'／'test:<i>'／'s6:<row_index>'（S6 扩词表抽样框）。"""
    rows = []
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            if str(r.get("sound_negative_llm", "")) == "1":
                rows.append((f"lab:{i}", str(r.get("text") or "")))
    with open(os.path.join(HERE, "val_v3_test.csv"), encoding="utf-8", errors="replace") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            rows.append((f"test:{i}", str(r.get("text") or "")))
    # S6：扩词表新增覆盖的 LLM 复核条目（重训 v3-lite-B 需要其产品口径分类）
    s6 = os.path.join(OUT, "s6_preregistration.json")
    if os.path.isfile(s6):
        want = set(json.load(open(s6, encoding="utf-8"))["label_row_index"])
        with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8",
                  errors="replace") as fh:
            for i, r in enumerate(csv.DictReader(fh)):
                if i in want:
                    rows.append((f"s6:{i}", str(r.get("text") or "")))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    todo_all = target_rows()
    done = {}
    if os.path.isfile(CACHE):
        for line in open(CACHE, encoding="utf-8", errors="replace"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            done[rec["uid"]] = rec
    todo = [(u, t) for u, t in todo_all if u not in done and t.strip()]
    if args.limit:
        todo = todo[:args.limit]
    print(f"目标 {len(todo_all)} 条｜已完成 {len(done)}｜本次 {len(todo)}｜并发 {args.workers}")
    if todo and not key:
        print("[需要凭证] 未注入 DEEPSEEK_API_KEY")
        return 2
    if todo:
        with open(CACHE, "a", encoding="utf-8") as fh, \
                cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(call, t, key): u for u, t in todo}
            for k, fut in enumerate(cf.as_completed(futs), 1):
                u = futs[fut]
                fh.write(json.dumps({"uid": u, **fut.result()}, ensure_ascii=False) + "\n")
                if k % 200 == 0:
                    fh.flush()
                    print(f"  …{k}/{len(todo)}｜" + "｜".join(
                        f"{c}={n}" for c, n in _stat.most_common(5)))
    # 汇总
    allrec = {}
    for line in open(CACHE, encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        allrec[rec["uid"]] = rec["category"]
    HP = {"headphone", "earbud", "headset"}
    lab = {u: c for u, c in allrec.items() if u.startswith("lab:")}
    tst = {u: c for u, c in allrec.items() if u.startswith("test:")}
    summary = {
        "labeled_positive_total": len([u for u, _ in todo_all if u.startswith("lab:")]),
        "labeled_positive_classified": len(lab),
        "labeled_positive_headphone": sum(1 for c in lab.values() if c in HP),
        "labeled_positive_categories": dict(collections.Counter(lab.values())),
        "test_total": len([u for u, _ in todo_all if u.startswith("test:")]),
        "test_classified": len(tst),
        "test_headphone": sum(1 for c in tst.values() if c in HP),
        "test_categories": dict(collections.Counter(tst.values())),
        "note": "产品口径判定（LLM）；仅判产品类型，未判情感。用于估计口径外占比。",
    }
    json.dump(summary, open(os.path.join(OUT, "scope_summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n=== 汇总 ===")
    print(f"已标注正例：{summary['labeled_positive_classified']}/"
          f"{summary['labeled_positive_total']} 已判｜其中耳机类 "
          f"{summary['labeled_positive_headphone']}"
          f"（{summary['labeled_positive_headphone']/max(1,summary['labeled_positive_classified'])*100:.1f}%）")
    print(f"  类别分布：{summary['labeled_positive_categories']}")
    print(f"测试集：{summary['test_classified']}/{summary['test_total']} 已判｜耳机类 "
          f"{summary['test_headphone']}"
          f"（{summary['test_headphone']/max(1,summary['test_classified'])*100:.1f}%）")
    print(f"  类别分布：{summary['test_categories']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
