# -*- coding: utf-8 -*-
"""S6 预注册 + 独立检验答题卡生成（**词表先冻结、再看结果**）。

顺序（红队五步，顺序即防线）：
  1. 冻结词表：写 `audio_gate.py` 哈希与时间戳入 `docs/s6_preregistration.md`；
  2. 抽样框：语料中**仅被扩词表覆盖**（`is_newly_covered`）且**排除全部已人工判定行**；
  3. 预注册 n=100（功效计算落盘：最坏 p=0.5、±10%、95% → n=96，取 100）；
  4. 抽样：随机 100 条（种子冻结）作为**独立检验样本**；其余留作 LLM 复核→重训；
  5. 人工盲判：答题卡不含 LLM 判定结果（映射单独存放）。

产物：docs/s6_preregistration.md、docs/gold_set/answer_sheet_vocab_test.md、
     docs/gold_set/vocab_test.csv、v2/s6_preregistration.json
"""
from __future__ import annotations

import concurrent.futures as cf
import csv
import hashlib
import importlib.util
import json
import math
import os
import random
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261006
N_TEST = 100
N_LLM = 700


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


spec = importlib.util.spec_from_file_location("ag", os.path.join(HERE, "audio_gate.py"))
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)

# ---- 1. 冻结 ----
gate_hash = sha(os.path.join(HERE, "audio_gate.py"))
frozen_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f"① 词表冻结：audio_gate.py sha256={gate_hash[:16]}…（{frozen_at}）")

# ---- 2. 抽样框 ----
texts = []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
judged = set()
for it in json.load(open(os.path.join(HERE, "v2", "gold_set_key.json"),
                         encoding="utf-8"))["items"]:
    judged.add(it["row_index"])
judged |= set(json.load(open(os.path.join(HERE, "v2", "s1_add100_ids.json"),
                             encoding="utf-8")).get("row_index", []))
with open(os.path.join(HERE, "docs/gold_set/s5_clean_probe.csv"),
          encoding="utf-8-sig", errors="replace") as fh:
    for r in csv.DictReader(fh):
        if str(r.get("row_index", "")).strip():
            judged.add(int(r["row_index"]))
with open(os.path.join(HERE, "docs/gold_set/clean_alerts.csv"),
          encoding="utf-8-sig", errors="replace") as fh:
    for r in csv.DictReader(fh):
        if str(r.get("row_index", "")).strip():
            judged.add(int(r["row_index"]))
frame_all = [i for i, t in enumerate(texts) if ag.is_newly_covered(t)]
frame = [i for i in frame_all if i not in judged]
print(f"② 抽样框：仅扩词表覆盖 {len(frame_all):,} 条 → 排除已判 {len(judged)} 行后 "
      f"**{len(frame):,} 条**")

# ---- 3. 预注册 ----
p, E, z = 0.5, 0.10, 1.96
n_power = math.ceil(z * z * p * (1 - p) / (E * E))
print(f"③ 功效计算：最坏 p={p}、±{E:.0%}、95% → n={n_power} → 预注册 **n={N_TEST}**"
      f"（±{z*math.sqrt(p*(1-p)/N_TEST)*100:.1f}%）")

# ---- 4. 抽样 ----
rng = random.Random(SEED)
shuffled = frame[:]
rng.shuffle(shuffled)
test_ids = sorted(shuffled[:N_TEST])
label_ids = sorted(shuffled[N_TEST:N_TEST + N_LLM])
print(f"④ 抽样：独立检验 {len(test_ids)} 条｜LLM 复核 {len(label_ids)} 条｜"
      f"其余 {len(shuffled) - N_TEST - len(label_ids):,} 条留观（种子 {SEED}）")

# ---- 5. 答题卡（含中性翻译；不含 LLM 判定）----
spec2 = importlib.util.spec_from_file_location("mgn", os.path.join(HERE, "make_gold_set_notes.py"))
mgn = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(mgn)
cache = os.path.join(HERE, "v2", "vocab_test_notes.jsonl")
done = {}
if os.path.isfile(cache):
    for line in open(cache, encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "zh" in rec:
            done[str(rec["uid"])] = rec
todo = [(f"V{i:03d}", texts[ridx]) for i, ridx in enumerate(test_ids, 1)
        if f"V{i:03d}" not in done]
key = os.environ.get("DEEPSEEK_API_KEY", "")
if todo and key:
    print(f"   生成中性翻译 {len(todo)} 条…")
    with open(cache, "a", encoding="utf-8") as fh, cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(mgn.call, t, key): u for u, t in todo}
        for k, fut in enumerate(cf.as_completed(futs), 1):
            fh.write(json.dumps({"uid": futs[fut], **fut.result()}, ensure_ascii=False) + "\n")
            if k % 25 == 0:
                fh.flush()
                print(f"     …{k}/{len(todo)}")
notes = {}
if os.path.isfile(cache):
    for line in open(cache, encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if "zh" in rec:
            notes[str(rec["uid"])] = rec

sheet = ["# S6 独立检验 · 扩词表答题卡（**词表已冻结**）", "",
         f"> 词表 `audio_gate.py` sha256 = `{gate_hash[:32]}…`｜冻结于 {frozen_at}", "",
         f"> **{len(test_ids)} 条**：从「**仅被扩词表覆盖、原始闸门未覆盖**」的 "
         f"{len(frame):,} 条中随机抽取（种子 {SEED}），**已排除全部已人工判定行**。", "",
         "> **它测什么**：P(真阳 ｜ 扩词表命中)——即**新词表命中的条目里，有多少是真正的音质抱怨**。",
         "> 该估计**不引入基线率**，故与先前的不确定性解耦。", "",
         "> 编码：**1 = 是**（在说耳机/耳塞/头戴的音质）｜**0 = 不是**｜**2 = 无法判断**", "",
         "> 口径（D-Q9 已记录）：**降噪/底噪/漏音等影响听感的问题算 1**；"
         "仅功能故障（连不上、配对失败）不算。", ""]
rows_out = []
for i, ridx in enumerate(test_ids, 1):
    uid = f"V{i:03d}"
    d = notes.get(uid, {})
    rows_out.append((uid, ridx, texts[ridx], d))
    sheet += [f"## {uid}", "",
              f"**原文**：{texts[ridx]}", "",
              f"**翻译**：{d.get('zh', '')}", "",
              f"**解释**：产品：{d.get('product', '') or '不确定'}｜声音："
              f"{d.get('sound', '') or '未提及声音相关内容'}｜其他：{d.get('other', '')}", "",
              "**判定（决策方填）**：`___`", ""]
open(os.path.join(HERE, "docs", "gold_set", "answer_sheet_vocab_test.md"), "w",
     encoding="utf-8", newline="\n").write("\n".join(sheet) + "\n")
with open(os.path.join(HERE, "docs", "gold_set", "vocab_test.csv"), "w",
          encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["编号", "row_index", "原文", "中文翻译", "人工判定(1=音质差评/0=不是)", "备注"])
    for uid, ridx, t, d in rows_out:
        w.writerow([uid, ridx, t, d.get("zh", ""), "", ""])

prereg = {"frozen_at": frozen_at, "gate_module": "audio_gate.py", "gate_sha256": gate_hash,
          "expanded_extra": ag.EXPANDED_EXTRA, "seed": SEED, "n_test": N_TEST, "n_llm": N_LLM,
          "frame_all": len(frame_all), "frame_after_exclusion": len(frame),
          "excluded_judged_rows": len(judged),
          "power_calc": {"p": p, "E": E, "z": z, "n_required": n_power, "n_preregistered": N_TEST},
          "estimand": "P(真阳 | 扩词表命中)，以 D-Q9 记录的口径判定",
          "exclusions": "全部 500 条已人工判定行（S1–S5 + K 系列）",
          "test_row_index": test_ids, "label_row_index": label_ids,
          "analysis_script": "score_vocab_test.py（待写，须与词表同哈希冻结）",
          "decision_rule": "仅报 P 及其 Wilson/Clopper-Pearson 区间与可回收量区间；不做方向性外推"}
json.dump(prereg, open(os.path.join(HERE, "v2", "s6_preregistration.json"), "w",
                       encoding="utf-8"), ensure_ascii=False, indent=2)

MD = f"""# S6 预注册（扩词表独立检验 + 后续重训）

> 冻结于 **{frozen_at}**｜词表模块 `audio_gate.py`｜**全量 sha256 `{gate_hash}`**

## 一、要估计的量（estimand）

**P(真阳 ｜ 扩词表命中)** —— 在「仅被扩词表覆盖、原始闸门未覆盖」的条目中，
判定为真正音质抱怨的比例。**该估计不使用基线率**，故与先前小样本基线的不确定性解耦。

## 二、抽样框与排除

| 项 | 值 |
|---|---|
| 仅扩词表覆盖 | **{len(frame_all):,}** 条 |
| 排除（全部已人工判定行） | **{len(judged)}** 行（S1–S5 与 K 系列，防止重判不独立） |
| **抽样框** | **{len(frame):,}** 条 |

## 三、预注册样本量与功效计算（**先算后抽**）

- 最坏情形 p=0.5、绝对误差 ±{E:.0%}、95% 置信 → **n = {n_power}**；
- **预注册 n = {N_TEST}**（±{z*math.sqrt(p*(1-p)/N_TEST)*100:.1f}%）；
- 声明：p=0.5 为 **sizing 依据**（新词表精确率未知：已知 3 条全命中可能偏高，旧闸门曾只有约 0.3），
  **不是先验结论**。功效计算与词表哈希**同一时刻冻结**，禁止事后调 n。

## 四、抽样（种子已冻结）

- 种子 **{SEED}**；随机取 **{N_TEST}** 条为**独立检验样本**（`answer_sheet_vocab_test.md`）；
- 另取 **{N_LLM}** 条作 LLM 复核 → 用于扩词表重训（v3-lite-B）；其余留观。

## 五、判定与盲法

- 人工判定**不看 LLM 结果**（答题卡只含原文＋中性翻译＋中性解析；映射单独存放于本 JSON）；
- 口径按 **D-Q9 记录**：降噪/底噪/漏音等**影响听感**的问题算 1；仅功能故障不算。

## 六、分析脚本与 CI（须与词表同哈希冻结）

- `score_vocab_test.py`（待写）：报 P 及区间（Wilson 与 Clopper-Pearson **都报**）、
  可回收量 = 匹配总数 × P 的**区间**（点估计不得单独出现）；
- **判读限制**：不得把 P 外推为"召回提升幅度"；召回改善须由重训后在干净池的**实测**给出。

## 七、迭代即作废

词表每改一次，本次验证**作废**；新数字必须用**新样本**重验。
"""
open(os.path.join(HERE, "docs", "s6_preregistration.md"), "w", encoding="utf-8",
     newline="\n").write(MD)
print(f"[写出] docs/s6_preregistration.md、docs/gold_set/answer_sheet_vocab_test.md"
      f"、docs/gold_set/vocab_test.csv、v2/s6_preregistration.json")
