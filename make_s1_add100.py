# -*- coding: utf-8 -*-
"""生成"闸门外追加 100 条"（层名 **S4**，与首轮 S1 的 100 条**不重复**）：
  ① 用与首轮完全相同的池定义与排除规则；
  ② 种子 20261003，排除首轮 S1 已抽的 100 条（按 row_index）；
  ③ 用与金标同一套**中性提示词 + 判定词闸门**产出 翻译/解释，写成答题卡（原文＋翻译＋解释＋判定位）。

用法：python make_s1_add100.py            # 全量
     python make_s1_add100.py --limit 5    # 试跑
产物：docs/gold_set/answer_sheet_s1_add100.md、docs/gold_set/s1_add100.csv、v2/s1_add100_ids.json
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import json
import os
import random
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GDIR = os.path.join(HERE, "docs", "gold_set")
OUT = os.path.join(HERE, "v2")
SEED = 20261003
N = 100
import re  # noqa: E402

RX = re.compile(r"")          # 与首轮一致：S1 池不含"闸门命中"的行（见 make_gold_set.py 定义）
BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL = "deepseek-chat"
SYS = ("You are a bilingual translator and neutral describer. For the given English product review, "
       "return JSON only: {\"zh\": \"<Chinese translation>\", \"product\": \"<what product it is, "
       "in Chinese, or 不确定>\", \"sound\": \"<what the user says about sound, quoting key English "
       "phrases in parentheses, in Chinese>\", \"other\": \"<other topics mentioned, in Chinese>\"}. "
       "STRICT RULE: describe only. Do NOT judge, rate, or classify whether this is a sound-quality "
       "complaint. Never use words like 抱怨/差评/负面/positive/negative/complaint.")
BAD = re.compile(r"抱怨|差评|负面|好评|complaint|negative|positive|判定|属于音质|是音质|音质问题", re.I)


def load_corpus():
    """与 make_gold_set.py 同源：读语料（沿用其 load_corpus 实现）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("mgs", os.path.join(HERE, "make_gold_set.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load_corpus(), mod.RX


def call(text, key, retries=2):
    body = {"model": MODEL, "messages": [{"role": "system", "content": SYS},
                                         {"role": "user", "content": text[:3000]}],
            "temperature": 0, "response_format": {"type": "json_object"}}
    for a in range(retries + 1):
        try:
            req = urllib.request.Request(BASE.rstrip("/") + "/chat/completions",
                                         data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read().decode("utf-8"))
            p = json.loads(d["choices"][0]["message"]["content"])
            if BAD.search(" ".join(str(v) for v in p.values())):
                continue
            return p
        except Exception:  # noqa: BLE001
            time.sleep(1.2 * (a + 1))
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    key = os.environ.get("DEEPSEEK_API_KEY", "")

    corpus, rx = load_corpus()
    outside = [r for r in corpus if len(r["text"]) >= 40 and not rx.search(r["text"])]
    gate_reviewed = {}
    for l in open(os.path.join(OUT, "gate_outside_review.jsonl"), encoding="utf-8",
                  errors="replace"):
        try:
            rec = json.loads(l)
        except ValueError:
            continue
        if "sound_negative" in rec:
            gate_reviewed[int(rec["row_index"])] = int(rec["sound_negative"])
    pool = [r for r in outside if r["row_index"] in gate_reviewed]
    used = {it["row_index"] for it in json.load(open(os.path.join(OUT, "gold_set_key.json"),
                                                     encoding="utf-8"))["items"]
            if it["stratum"] == "S1"}
    fresh = [r for r in pool if r["row_index"] not in used]
    rng = random.Random(SEED)
    rng.shuffle(fresh)
    picked = fresh[:(args.limit or N)]
    print(f"闸门外已复核池 {len(pool)} 条｜首轮 S1 已用 {len(used)} 条｜"
          f"**可用新样本 {len(fresh)} 条**｜本次抽 {len(picked)} 条（种子 {SEED}）")
    json.dump({"seed": SEED, "stratum": "S4",
               "note": "闸门外随机追加，独立于首轮 S1（按 row_index 排除）",
               "ids": [f"S4-{i:03d}" for i in range(1, len(picked) + 1)],
               "row_index": [r["row_index"] for r in picked],
               "llm_label": [gate_reviewed[r["row_index"]] for r in picked]},
              open(os.path.join(OUT, "s1_add100_ids.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    cache = os.path.join(OUT, "s1_add100_notes.jsonl")
    done = {}
    if os.path.isfile(cache):
        for line in open(cache, encoding="utf-8", errors="replace"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if "zh" in rec:
                done[rec["id"]] = rec
    todo = [(f"S4-{i:03d}", r) for i, r in enumerate(picked, 1) if f"S4-{i:03d}" not in done]
    if todo and not key:
        print("[需要凭证] 有未完成条目但未注入 DEEPSEEK_API_KEY")
        return 2
    if todo:
        print(f"调用模型 {len(todo)} 条（并发 {args.workers}）…")
        with open(cache, "a", encoding="utf-8") as fh, \
                cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(call, r["text"], key): (i, r) for i, r in todo}
            for k, fut in enumerate(cf.as_completed(futs), 1):
                iid, r = futs[fut]
                fh.write(json.dumps({"id": iid, **fut.result()}, ensure_ascii=False) + "\n")
                if k % 25 == 0:
                    fh.flush()
                    print(f"  …{k}/{len(todo)}")
    data = {}
    for line in open(cache, encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "zh" in rec:
            data[rec["id"]] = rec

    sheet = ["# 人工金标 · 闸门外追加 100 条（层 S4）", "",
             "> **与首轮 S1 的 100 条不重复**（按 row_index 排除）｜种子 20261003｜可复算", "",
             "> **目的**：把闸门外真阳性率的 95% CI 从约 1.0%–8.5% 收窄到约 1.7%–5.3%，",
             "> 以便判断覆盖数字能否改口。编码：**1 = 是**｜**0 = 不是**｜**2 = 无法判断**",
             "> （与本项目其余答题卡一致；请在每条的判定位写数字，填多少收多少）", ""]
    rows = []
    for i, r in enumerate(picked, 1):
        iid = f"S4-{i:03d}"
        d = data.get(iid, {})
        rows.append((iid, r["text"], d.get("product", ""), d.get("sound", ""),
                     d.get("other", ""), d.get("zh", "")))
        sheet += [f"## {iid}", "",
                  f"**原文**：{r['text']}", "",
                  f"**翻译**：{d.get('zh', '')}", "",
                  f"**解释**：产品：{d.get('product', '') or '不确定'}｜声音："
                  f"{d.get('sound', '') or '未提及声音相关内容'}｜其他：{d.get('other', '')}", "",
                  "**判定（决策方填）**：`___`", ""]
    open(os.path.join(GDIR, "answer_sheet_s1_add100.md"), "w", encoding="utf-8",
         newline="\n").write("\n".join(sheet) + "\n")
    with open(os.path.join(GDIR, "s1_add100.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["编号", "原文", "产品", "关于声音的表述", "其他提及", "中文翻译",
                    "人工判定(1=音质差评/0=不是)", "备注"])
        for iid, text, prod, snd, oth, zh in rows:
            w.writerow([iid, text, prod, snd, oth, zh, "", ""])
    print(f"[写出] docs/gold_set/answer_sheet_s1_add100.md（{len(picked)} 条）")
    print(f"[写出] docs/gold_set/s1_add100.csv 与 v2/s1_add100_ids.json")
    print(f"[提示] 本轮 LLM 调用 {len(todo)} 条；未填占位保持 `___`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
