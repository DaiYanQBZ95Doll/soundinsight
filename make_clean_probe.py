# -*- coding: utf-8 -*-
"""干净版偏向探针（层 S5）：**未见过条目 + 随机两臂**（决策方批准）。

设计（无记忆污染、有对照组）：
  · 池：闸门外已复核 300 条中**尚未被用过**的剩余 100 条（S1 用 100、S4 用 100）；
  · 随机（种子 20261004）平分两臂：
      - **对照组（50 条）**：只给英文原文（无翻译、无解析）
      - **实验组（50 条）**：原文 + 中文翻译 + 中性解析（与主卡同格式）
  · 两臂**同一批条目**（按 row_index 判定），组间差异 = **材料效应**（between-subjects，无记忆污染）；
  · 额外收益：两臂合计 100 条并入闸门外比率估计（n 195 → 295）。

产物：docs/gold_set/answer_sheet_s5_control.md、answer_sheet_s5_treatment.md、
     docs/gold_set/s5_clean_probe.csv、v2/s5_ids.json
用法：python make_clean_probe.py [--limit N]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import json
import os
import random
import re
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GDIR = os.path.join(HERE, "docs", "gold_set")
OUT = os.path.join(HERE, "v2")
SEED = 20261004
N_ARM = 50
BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL = "deepseek-chat"
SYS = ("You are a bilingual translator and neutral describer. For the given English product review, "
       "return JSON only: {\"zh\": \"<Chinese translation>\", \"product\": \"<what product it is, "
       "in Chinese, or 不确定>\", \"sound\": \"<what the user says about sound, quoting key English "
       "phrases in parentheses, in Chinese>\", \"other\": \"<other topics mentioned, in Chinese>\"}. "
       "STRICT RULE: describe only. Do NOT judge, rate, or classify whether this is a sound-quality "
       "complaint. Never use words like 抱怨/差评/负面/positive/negative/complaint.")
BAD = re.compile(r"抱怨|差评|负面|好评|complaint|negative|positive|判定|属于音质|是音质|音质问题", re.I)


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

    import importlib.util
    spec = importlib.util.spec_from_file_location("mgs", os.path.join(HERE, "make_gold_set.py"))
    mgs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mgs)
    corpus = mgs.load_corpus()
    outside = [r for r in corpus if len(r["text"]) >= 40 and not mgs.RX.search(r["text"])]
    reviewed = {}
    for l in open(os.path.join(OUT, "gate_outside_review.jsonl"), encoding="utf-8",
                  errors="replace"):
        try:
            rec = json.loads(l)
        except ValueError:
            continue
        if "sound_negative" in rec:
            reviewed[int(rec["row_index"])] = int(rec["sound_negative"])
    pool = [r for r in outside if r["row_index"] in reviewed]
    used = set()
    for f, strat in (("gold_set_key.json", "S1"), ("s1_add100_ids.json", "S4")):
        p = os.path.join(OUT, f)
        if not os.path.isfile(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        if f == "gold_set_key.json":
            used |= {it["row_index"] for it in d["items"] if it["stratum"] == strat}
        else:
            used |= set(d.get("row_index", []))
    fresh = [r for r in pool if r["row_index"] not in used]
    rng = random.Random(SEED)
    rng.shuffle(fresh)
    take = fresh[:(args.limit or 2 * N_ARM)]
    control, treatment = take[:len(take) // 2], take[len(take) // 2:]
    print(f"池 {len(pool)}｜已用 {len(used)}｜**未用过 {len(fresh)}**｜"
          f"本次取 {len(take)}（对照组 {len(control)}／实验组 {len(treatment)}）")

    # 只有实验组需要材料
    cache = os.path.join(OUT, "s5_notes.jsonl")
    done = {}
    if os.path.isfile(cache):
        for line in open(cache, encoding="utf-8", errors="replace"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if "zh" in rec:
                done[rec["id"]] = rec
    todo = [(f"T{i:03d}", r) for i, r in enumerate(treatment, 1) if f"T{i:03d}" not in done]
    if todo and key:
        print(f"生成实验组材料 {len(todo)} 条…")
        with open(cache, "a", encoding="utf-8") as fh, \
                cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(call, r["text"], key): (i, r) for i, r in todo}
            for k, fut in enumerate(cf.as_completed(futs), 1):
                iid, _r = futs[fut]
                fh.write(json.dumps({"id": iid, **fut.result()}, ensure_ascii=False) + "\n")
                if k % 20 == 0:
                    fh.flush()
                    print(f"  …{k}/{len(todo)}")
    data = {}
    if os.path.isfile(cache):
        for line in open(cache, encoding="utf-8", errors="replace"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if "zh" in rec:
                data[rec["id"]] = rec

    header = ("# 干净版偏向探针\n\n"
              f"> 固定种子 {SEED}｜条目取自闸门外**未用过**的 {len(fresh)} 条｜"
              "**同一批条目随机分成两臂**，用于无记忆污染地估计「材料效应」。\n"
              "> 编码：**1 = 是**（在说耳机/耳塞/头戴的音质）｜**0 = 不是**｜**2 = 无法判断**\n"
              "> 请在每条判定位写数字；两臂都填（顺序不限）。\n")
    ctl = [header, "\n## 对照组（**只给原文**，50 条）\n"]
    for i, r in enumerate(control, 1):
        ctl += [f"## C{i:03d}", "", f"**原文**：{r['text']}", "",
                "**判定（决策方填）**：`___`", ""]
    trt = [header, "\n## 实验组（**原文＋翻译＋解释**，50 条）\n"]
    for i, r in enumerate(treatment, 1):
        d = data.get(f"T{i:03d}", {})
        trt += [f"## T{i:03d}", "", f"**原文**：{r['text']}", "",
                f"**翻译**：{d.get('zh', '')}", "",
                f"**解释**：产品：{d.get('product', '') or '不确定'}｜声音："
                f"{d.get('sound', '') or '未提及声音相关内容'}｜其他：{d.get('other', '')}", "",
                "**判定（决策方填）**：`___`", ""]
    open(os.path.join(GDIR, "answer_sheet_s5_control.md"), "w", encoding="utf-8",
         newline="\n").write("\n".join(ctl) + "\n")
    open(os.path.join(GDIR, "answer_sheet_s5_treatment.md"), "w", encoding="utf-8",
         newline="\n").write("\n".join(trt) + "\n")
    with open(os.path.join(GDIR, "s5_clean_probe.csv"), "w", encoding="utf-8-sig",
              newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["编号", "臂", "原文", "row_index", "llm_label",
                    "人工判定(1=音质差评/0=不是)", "备注"])
        for i, r in enumerate(control, 1):
            w.writerow([f"C{i:03d}", "control", r["text"], r["row_index"],
                        reviewed[r["row_index"]], "", ""])
        for i, r in enumerate(treatment, 1):
            w.writerow([f"T{i:03d}", "treatment", r["text"], r["row_index"],
                        reviewed[r["row_index"]], "", ""])
    json.dump({"seed": SEED, "pool_unused": len(fresh),
               "control": [r["row_index"] for r in control],
               "treatment": [r["row_index"] for r in treatment],
               "note": "同批条目随机两臂；组间差异 = 材料效应（between-subjects）"},
              open(os.path.join(OUT, "s5_ids.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("  [写出] answer_sheet_s5_control.md（50）｜answer_sheet_s5_treatment.md（50）")
    print("  [写出] s5_clean_probe.csv、v2/s5_ids.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
