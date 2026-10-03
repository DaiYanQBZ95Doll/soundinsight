# -*- coding: utf-8 -*-
"""干净评测（修正设计）：对**全部**留出侧闸门外条目打分 → 取**真正触发**的（prob ≥ 阈值）全部，
再配一条随机背景臂。用于回答两个部署相关的问题：
  ① **告警率**：产品在干净语料上到底触发多少（此前的"召回≈0"由此得到精确刻画）；
  ② **告警精确率**：在它触发的条目中，人工认可的比例（干净、从未训练）。

用法：python make_clean_alerts_sheet.py [--thr 0.5] [--bg 100]
产物：docs/gold_set/answer_sheet_clean_alerts.md、docs/gold_set/clean_alerts.csv、
     v2/clean_alerts_ids.json、v2/clean_alert_rate.json
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261005


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--thr", type=float, default=0.5)
    ap.add_argument("--bg", type=int, default=100)
    args = ap.parse_args()

    import importlib.util

    def load_mod(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    mgs = load_mod("mgs", os.path.join(HERE, "make_gold_set.py"))
    rwe = load_mod("rwe", os.path.join(HERE, "realworld_eval.py"))

    texts, labels = [], []
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            texts.append(str(r["text"]))
            labels.append(int(float(r.get("sound_negative_llm") or 0)))
    from sklearn.model_selection import train_test_split
    _tr, va = train_test_split(list(range(len(labels))), test_size=0.2,
                               random_state=42, stratify=labels)
    hold = set(va)
    used = {it["row_index"] for it in json.load(
        open(os.path.join(HERE, "v2", "gold_set_key.json"), encoding="utf-8"))["items"]}
    used |= set(json.load(open(os.path.join(HERE, "v2", "s1_add100_ids.json"),
                               encoding="utf-8")).get("row_index", []))
    with open(os.path.join(HERE, "docs/gold_set/s5_clean_probe.csv"),
              encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if str(r.get("row_index", "")).strip():
                used.add(int(r["row_index"]))
    clean = [i for i in hold
             if len(texts[i]) >= 40 and not mgs.RX.search(texts[i]) and i not in used]
    print(f"干净池（留出侧 + 闸门外 + 未判过）：**{len(clean):,}** 条 → 全量打分")

    cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
    probs = rwe.predict([texts[i] for i in clean], cfg["bin_model_dir"], 128)
    alerts = [(i, p) for i, p in zip(clean, probs) if p >= args.thr]
    rate = len(alerts) / max(1, len(clean))
    print(f"**v1 触发（≥{args.thr}）：{len(alerts)} / {len(clean):,} = {rate*100:.3f}%**")
    print(f"  分数分布：>0.9 {sum(1 for p in probs if p > 0.9)}｜>0.5 "
          f"{sum(1 for p in probs if p > 0.5)}｜(0.1,0.5] "
          f"{sum(1 for p in probs if 0.1 < p <= 0.5)}｜≤0.1 {sum(1 for p in probs if p <= 0.1)}")
    json.dump({"threshold": args.thr, "clean_pool": len(clean), "alerts": len(alerts),
               "alert_rate": round(rate, 6),
               "note": "留出侧 + 闸门外 + 从未训练；v1 触发率即『产品在真实语料上的报警率』"},
              open(os.path.join(HERE, "v2", "clean_alert_rate.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    non_alerts = [i for i in clean if all(i != j for j, _ in alerts)]
    rng = random.Random(SEED)
    bg = rng.sample(non_alerts, min(args.bg, len(non_alerts)))
    picked = [(i, p, "alert") for i, p in sorted(alerts, key=lambda x: -x[1])] + \
             [(i, dict(zip(clean, probs))[i], "background") for i in bg]
    print(f"答题卡条目：告警臂 {len(alerts)}｜背景臂 {len(bg)}｜合计 {len(picked)}")

    mgn = load_mod("mgn", os.path.join(HERE, "make_gold_set_notes.py"))
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    cache = os.path.join(HERE, "v2", "clean_alerts_notes.jsonl")
    done = {}
    if os.path.isfile(cache):
        for line in open(cache, encoding="utf-8", errors="replace"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if "zh" in rec:
                done[rec["uid"]] = rec
    todo = [(f"K{i:03d}", texts[ridx]) for i, (ridx, _p, _arm) in enumerate(picked, 1)
            if f"K{i:03d}" not in done]
    if todo and key:
        print(f"中性翻译与解析 {len(todo)} 条…")
        with open(cache, "a", encoding="utf-8") as fh, \
                cf.ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(mgn.call, t, key): u for u, t in todo}
            for k, fut in enumerate(cf.as_completed(futs), 1):
                fh.write(json.dumps({"uid": futs[fut], **fut.result()}, ensure_ascii=False) + "\n")
                if k % 25 == 0:
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
                data[rec["uid"]] = rec

    sheet = ["# 干净评测 · 答题卡（留出侧 + 闸门外 + 从未训练）", "",
             f"> 干净池 **{len(clean):,}** 条｜其中 **v1 触发（≥{args.thr}）{len(alerts)} 条"
             f"（{rate*100:.3f}%）**｜随机背景臂 {len(bg)} 条｜合计 {len(picked)} 条", "",
             "> **两个臂**：`alert` = 产品会报警的条目（量**告警精确率**）；"
             "`background` = 随机背景（量**基线率**，并为召回提供弱信号）。", "",
             "> 编码：**1 = 是**（在说耳机/耳塞/头戴的音质）｜**0 = 不是**｜**2 = 无法判断**", ""]
    rows_out = []
    for i, (ridx, p, arm) in enumerate(picked, 1):
        uid = f"K{i:03d}"
        d = data.get(uid, {})
        rows_out.append((uid, ridx, p, arm, texts[ridx], d))
        sheet += [f"## {uid}　[{arm}]　（v1 分数 {p:.3f}）", "",
                  f"**原文**：{texts[ridx]}", "",
                  f"**翻译**：{d.get('zh', '')}", "",
                  f"**解释**：产品：{d.get('product', '') or '不确定'}｜声音："
                  f"{d.get('sound', '') or '未提及声音相关内容'}｜其他：{d.get('other', '')}", "",
                  "**判定（决策方填）**：`___`", ""]
    open(os.path.join(HERE, "docs", "gold_set", "answer_sheet_clean_alerts.md"), "w",
         encoding="utf-8", newline="\n").write("\n".join(sheet) + "\n")
    with open(os.path.join(HERE, "docs", "gold_set", "clean_alerts.csv"), "w",
              encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["编号", "臂", "row_index", "v1_prob", "原文", "中文翻译",
                    "人工判定(1=音质差评/0=不是)", "备注"])
        for uid, ridx, p, arm, t, d in rows_out:
            w.writerow([uid, arm, ridx, f"{p:.4f}", t, d.get("zh", ""), "", ""])
    json.dump({"seed": SEED, "threshold": args.thr, "clean_pool": len(clean),
               "alerts": len(alerts), "background": len(bg),
               "ids": [r[0] for r in rows_out], "arm": [r[3] for r in rows_out],
               "row_index": [r[1] for r in rows_out], "v1_prob": [round(r[2], 4) for r in rows_out]},
              open(os.path.join(HERE, "v2", "clean_alerts_ids.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"[写出] answer_sheet_clean_alerts.md / clean_alerts.csv / clean_alert_rate.json"
          f"（{len(picked)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
