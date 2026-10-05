# -*- coding: utf-8 -*-
"""判别器（"提到声音 ≠ 抱怨声音"）预注册 + 训练。

设计（**先注册后执行**）：
  · 底座 = **v2**（对 val_v3_test 与留出侧人工样本干净）；
  · 正例 = v1/v2 世代的耳机音质抱怨标签（**训练侧**）；
  · **新增硬负例** = P1 标注中 `functional_not_sound`（功能故障非音质）与 `weak_praise`（弱褒奖）
    且**闸门内**、**训练侧**的条目——这正是人工验收诊断出的两类主误报；
  · 纪律：**绝不使用留出侧**（val_v3_test 与人工卡全在留出侧，保持干净）；
  · 弃用规则（预注册）：若在 val_v3_test 范围内子集上 **召回下降 > 5 点**（LLM 口径）→ 放弃本方案。

用法：python train_discriminator.py [--epochs 3]
产物：v2/model_disc/、v2/disc_eval.json
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
HP = {"headphone", "earbud", "headset"}
BASE = os.path.join(HERE, "v2", "model_maxlen256")     # v2 底座


def load_mod(n, p):
    spec = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mgs = load_mod("mgs", os.path.join(HERE, "make_gold_set.py"))
w1 = load_mod("w1", os.path.join(HERE, "v2_w1_longtext.py"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1.5e-5)
    ap.add_argument("--out", default=os.path.join("v2", "model_disc"))
    a = ap.parse_args()

    texts, labels = [], []
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            texts.append(str(r.get("text") or ""))
            labels.append(int(float(r.get("sound_negative_llm") or 0)))
    from sklearn.model_selection import train_test_split
    tr = set(train_test_split(list(range(len(labels))), test_size=0.2, random_state=42,
                              stratify=labels)[0])

    # 硬负例：P1 的功能故障/弱褒奖，且闸门内、训练侧
    hard = []
    p1 = {}
    for line in open(os.path.join(HERE, "v2", "p1_labels.jsonl"), encoding="utf-8",
                     errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        i = int(rec["row_index"])
        p1[i] = rec
        if (i in tr and rec.get("vague_reason") in ("functional_not_sound", "weak_praise")
                and mgs.RX.search(texts[i])):
            hard.append(i)
    y = [0] * len(texts)
    pos = 0
    for i in range(len(texts)):
        if i in tr and (labels[i] == 1 or p1.get(i, {}).get("sound_complaint") == 1):
            y[i] = 1
            pos += 1
    for i in hard:
        y[i] = 0                                  # 硬负例：明确压成负
    print(f"训练侧：正例 {pos}｜**硬负例 {len(hard)}**（功能故障/弱褒奖且闸门内）"
          f"｜样本总数 {len(tr):,}")
    json.dump({"base": "v2/model_maxlen256", "positives": pos, "hard_negatives": len(hard),
               "hard_negative_rule": "P1 vague_reason ∈ {functional_not_sound, weak_praise} "
                                     "∧ 闸门内 ∧ 训练侧",
               "holdout_rule": "只用 seed42 训练侧；val_v3_test 与人工卡保持干净",
               "abandon_rule": "val_v3_test 范围内召回下降 >5 点则放弃"},
              open(os.path.join(HERE, "v2", "disc_manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    import numpy as np
    import torch
    from torch.optim import AdamW
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import DistilBertForSequenceClassification, DistilBertTokenizer
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = DistilBertTokenizer.from_pretrained(BASE)
    idx = [i for i in range(len(texts)) if i in tr]
    enc = tok([texts[i] for i in idx], truncation=True, max_length=a.max_len, padding=True,
              return_tensors="pt")
    dl = DataLoader(TensorDataset(enc["input_ids"], enc["attention_mask"],
                                  torch.tensor([y[i] for i in idx])),
                    batch_size=16, shuffle=True)
    torch.manual_seed(42)
    m = DistilBertForSequenceClassification.from_pretrained(BASE, num_labels=2).to(dev)
    opt = AdamW(m.parameters(), lr=a.lr)
    print(f"训练（device={dev}，{a.epochs} epochs，{len(dl)} steps/epoch）", flush=True)
    for ep in range(a.epochs):
        m.train()
        tot = 0.0
        for k, (ids, att, yy) in enumerate(dl, 1):
            ids, att, yy = ids.to(dev), att.to(dev), yy.to(dev)
            o = m(input_ids=ids, attention_mask=att, labels=yy)
            o.loss.backward()
            opt.step()
            opt.zero_grad()
            tot += float(o.loss)
            if k % 1000 == 0:
                print(f"  [ep{ep+1}] {k}/{len(dl)} loss={tot/k:.4f}", flush=True)
        print(f"[epoch {ep+1}] mean loss={tot/max(len(dl),1):.4f}", flush=True)
    d = os.path.join(HERE, a.out)
    os.makedirs(d, exist_ok=True)
    m.save_pretrained(d)
    tok.save_pretrained(d)
    print(f"[保存] {a.out}", flush=True)

    # 评测：val_v3_test 范围内子集（弃用规则）
    t_texts, t_labels = w1.load_csv_texts(w1.TEST_CSV)
    sc = {}
    for line in open(os.path.join(HERE, "v2", "scope_rows.jsonl"), encoding="utf-8",
                     errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        u = str(rec.get("uid", ""))
        if u.startswith("test:"):
            sc[int(u.split(":")[1])] = rec.get("category", "unclear")
    ids = [i for i in range(len(t_texts)) if sc.get(i) in HP]
    yv = [t_labels[i] for i in ids]
    rwe = load_mod("rwe", os.path.join(HERE, "realworld_eval.py"))
    res = {}
    for name, dd in (("disc（判别器）", d), ("v2（底座）", BASE)):
        p = rwe.predict([t_texts[i] for i in ids], dd, a.max_len)
        row = {}
        for thr in (0.5, 0.9, 0.95):
            mm = w1.metrics(yv, p, thr)
            row[thr] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in mm.items()}
        res[name] = row
        print(f"  [{name}] 范围内 n={len(ids)}："
              + "｜".join(f"@{t} P{row[t]['P']:.1f}/R{row[t]['R']:.1f}/F1 {row[t]['F1']:.3f}"
                          for t in (0.5, 0.9, 0.95)))
    base_r = res["v2（底座）"][0.5]["R"]
    disc_r = res["disc（判别器）"][0.5]["R"]
    verdict = "**放弃**（召回下降 >5 点）" if (base_r - disc_r) > 5 else "可继续（召回未明显下降）"
    print(f"\n[预注册弃用规则] 底座 R {base_r:.1f} → 判别器 R {disc_r:.1f} ⇒ {verdict}")
    json.dump({"eval": res, "base_R": base_r, "disc_R": disc_r, "verdict": verdict},
              open(os.path.join(HERE, "v2", "disc_eval.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
