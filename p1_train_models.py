# -*- coding: utf-8 -*-
"""P1 训练：两个新世代（均在 R34 已登记）。

世代 A：**音质二分类 v5**——监督 =（既有：耳机家族 ∧ 音质抱怨）∪（P1 新标注 sound_complaint=1）
        ＊关键：P1 样本含 **闸门外** 约 17,217 条，故首次获得闸门外监督（预试已证明路由救不了）。
世代 B：**类型/原因多标签**——13 类差评类型 ＋ 7 类不可归因原因（含 sound_complaint 作为对照列）。

划分纪律：与既往一致——只用**训练侧**（seed 42、按原始标签分层），`val_v3_test` 不参与训练。
用法：python p1_train_models.py [--which sound|types|both]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
HP = {"headphone", "earbud", "headset"}
TYPES = ["连接/配对", "续航/充电", "做工/耐用", "佩戴/舒适", "麦克风/通话", "功能/操作",
         "物流/包装", "价格/性价比", "客服/售后", "描述不符/假货", "音质(听感)",
         "非负面/无抱怨", "其他"]
VAGUE = ["NONE", "sound_vague", "anc_only", "functional_not_sound", "weak_praise",
         "not_headphone", "insufficient"]


def load_all():
    texts, orig = [], []
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            texts.append(str(r.get("text") or ""))
            orig.append(int(float(r.get("sound_negative_llm") or 0)))
    scope = {}
    for line in open(os.path.join(HERE, "v2", "scope_rows.jsonl"), encoding="utf-8",
                     errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        u = str(rec.get("uid", ""))
        if u.startswith(("lab:", "s6:")) and rec.get("category"):
            scope[int(u.split(":")[1])] = rec["category"]
    p1 = {}
    p = os.path.join(HERE, "v2", "p1_labels.jsonl")
    if os.path.isfile(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if "sound_complaint" in rec:
                p1[int(rec["row_index"])] = rec
    return texts, orig, scope, p1


def split_train(orig):
    from sklearn.model_selection import train_test_split
    tr, _va = train_test_split(list(range(len(orig))), test_size=0.2, random_state=42,
                               stratify=orig)
    return set(tr)


def train_binary(texts, scope, p1, tr, epochs=3, max_len=256,
                 out=os.path.join("v2", "model_v5_sound")):
    """正例 =（既有：耳机家族 ∧ LLM 判正 ∧ P1 未覆盖）∪（P1 标为音质抱怨者），负例 = 训练侧其余。"""
    y = [0] * len(texts)
    n_old = n_new = 0
    for i in range(len(texts)):
        if i not in tr:
            continue
        is_new = p1.get(i, {}).get("sound_complaint") == 1
        is_old = (i not in p1) and (scope.get(i) in HP)
        if is_new:
            n_new += 1
        elif is_old:
            n_old += 1
        y[i] = 1 if (is_new or is_old) else 0
    print(f"  世代 A 正例：既有 {n_old} ＋ P1 新增 **{n_new}** = {sum(y)}（训练侧）")
    json.dump({"positives_old": n_old, "positives_new_p1": n_new, "positives_total": sum(y),
               "train_side": len(tr), "max_len": max_len},
              open(os.path.join(HERE, "v2", "v5_sound_manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    import torch
    from torch.optim import AdamW
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import DistilBertForSequenceClassification, DistilBertTokenizer
    idx = [i for i in range(len(texts)) if i in tr]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = DistilBertTokenizer.from_pretrained(os.path.join(HERE, "sound_model"))
    enc = tok([texts[i] for i in idx], truncation=True, max_length=max_len, padding=True,
              return_tensors="pt")
    dl = DataLoader(TensorDataset(enc["input_ids"], enc["attention_mask"],
                                  torch.tensor([y[i] for i in idx])),
                    batch_size=16, shuffle=True)
    torch.manual_seed(42)
    m = DistilBertForSequenceClassification.from_pretrained(
        os.path.join(HERE, "sound_model"), num_labels=2).to(dev)
    opt = AdamW(m.parameters(), lr=2e-5)
    print(f"  训练（{dev}，{epochs} epochs，{len(dl)} steps/epoch）", flush=True)
    for ep in range(epochs):
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
                print(f"    [ep{ep+1}] {k}/{len(dl)} loss={tot/k:.4f}", flush=True)
        print(f"  [epoch {ep+1}] mean loss={tot/max(len(dl),1):.4f}", flush=True)
    d = os.path.join(HERE, out)
    os.makedirs(d, exist_ok=True)
    m.save_pretrained(d)
    tok.save_pretrained(d)
    print(f"  [保存] {out}")
    return d


def train_types(texts, p1, tr, epochs=3, max_len=192,
                out=os.path.join("v2", "model_types")):
    """多标签：13 类型 ＋ 7 原因（sigmoid，阈值 0.5）。"""
    labels = TYPES + VAGUE
    idx = [i for i in p1 if i in tr]
    print(f"  世代 B：样本 {len(idx):,}（P1 标注 ∩ 训练侧）｜标签 {len(labels)} 个")
    Y = []
    for i in idx:
        rec = p1[i]
        vec = [1.0 if t in (rec.get("types") or []) else 0.0 for t in TYPES]
        vec += [1.0 if rec.get("vague_reason") == v else 0.0 for v in VAGUE]
        Y.append(vec)
    import torch
    from torch.optim import AdamW
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import DistilBertForSequenceClassification, DistilBertTokenizer
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = DistilBertTokenizer.from_pretrained(os.path.join(HERE, "sound_model"))
    enc = tok([texts[i] for i in idx], truncation=True, max_length=max_len, padding=True,
              return_tensors="pt")
    dl = DataLoader(TensorDataset(enc["input_ids"], enc["attention_mask"],
                                  torch.tensor(Y)), batch_size=16, shuffle=True)
    torch.manual_seed(42)
    m = DistilBertForSequenceClassification.from_pretrained(
        os.path.join(HERE, "sound_model"), num_labels=len(labels),
        problem_type="multi_label_classification", ignore_mismatched_sizes=True).to(dev)
    opt = AdamW(m.parameters(), lr=2e-5)
    print(f"  训练（{dev}，{epochs} epochs，{len(dl)} steps/epoch）", flush=True)
    for ep in range(epochs):
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
                print(f"    [ep{ep+1}] {k}/{len(dl)} loss={tot/k:.4f}", flush=True)
        print(f"  [epoch {ep+1}] mean loss={tot/max(len(dl),1):.4f}", flush=True)
    d = os.path.join(HERE, out)
    os.makedirs(d, exist_ok=True)
    m.save_pretrained(d)
    tok.save_pretrained(d)
    json.dump({"labels": labels, "types": TYPES, "vague": VAGUE, "n_train": len(idx)},
              open(os.path.join(HERE, "v2", "types_model_manifest.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  [保存] {out}")
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", choices=["sound", "types", "both"], default="both")
    a = ap.parse_args()
    texts, orig, scope, p1 = load_all()
    print(f"语料 {len(texts):,}｜口径标签 {len(scope):,}｜P1 标注 {len(p1):,}")
    if not p1:
        print("[等待] P1 标注尚未产出，退出")
        sys.exit(1)
    tr = split_train(orig)
    if a.which in ("sound", "both"):
        train_binary(texts, scope, p1, tr)
    if a.which in ("types", "both"):
        train_types(texts, p1, tr)
    print("完成")
