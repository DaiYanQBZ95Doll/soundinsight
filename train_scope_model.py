# -*- coding: utf-8 -*-
"""P0 品类模型：用现有 **11,979** 条口径标签训本地小模型（DistilBERT 多分类）。

用途（出厂功能）：
  · **精确率过滤器**：非耳机家族的告警可被过滤（40 条人工告警上 37.5% → 58.3%）；
  · 报告显示"品类"字段；
  · **单点故障可测**：其「耳机」判定的精确率必须报出（Kimi 指出：旁路若启用，它决定召回链）。
**不启用旁路**（预试已证否）。

划分：按 `scope_rows.jsonl` 的 uid 前缀分层（lab/test/s6），test: 段整体留出评测，
训练只用 lab: + s6: ——避免与既有权重/评测混用。
用法：python train_scope_model.py [--epochs 3]
产物：v2/model_scope/、v2/scope_model_eval.json
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CATS = ["headphone", "earbud", "headset", "speaker", "soundbar", "other_audio",
        "cable", "non_audio", "unclear"]
C2I = {c: i for i, c in enumerate(CATS)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--max-len", type=int, default=192)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--out-dir", default=os.path.join("v2", "model_scope"))
    a = ap.parse_args()

    texts = []
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            texts.append(str(r.get("text") or ""))
    recs = []
    # ⚠️ uid 语义：`lab:<i>`／`s6:<i>` 是**语料行号**；`test:<i>` 是 **val_v3_test 的行号**，
    # 必须用**内容哈希**映射回语料。首版直接把 i 当语料行号 → 标签贴错文本、模型学成垃圾（已修正）。
    import hashlib
    import re

    def _h(t):
        return hashlib.sha256(re.sub(r"\s+", " ", str(t)).strip()
                              .encode("utf-8", "replace")).hexdigest()
    idx_by_hash = {}
    for _i, _t in enumerate(texts):
        idx_by_hash.setdefault(_h(_t), _i)
    test_row = []
    with open(os.path.join(HERE, "val_v3_test.csv"), encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            test_row.append(str(r.get("text") or ""))
    unmapped = 0
    for line in open(os.path.join(HERE, "v2", "scope_rows.jsonl"), encoding="utf-8",
                     errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        u, c = str(rec.get("uid", "")), rec.get("category")
        if not c or c not in C2I:
            continue
        k = int(u.split(":")[1])
        if u.startswith("test:"):
            if k >= len(test_row):
                continue
            i = idx_by_hash.get(_h(test_row[k]), -1)
        else:
            i = k
        if 0 <= i < len(texts):
            recs.append((u, i, C2I[c]))
        else:
            unmapped += 1
    print(f"口径标签 {len(recs):,} 条（类别 {len(CATS)}）｜无法映射 {unmapped}")
    tr = [(i, y) for u, i, y in recs if not u.startswith("test:")]
    te = [(i, y) for u, i, y in recs if u.startswith("test:")]
    print(f"训练 {len(tr):,}（lab+s6）｜留出评测 {len(te):,}（test: 段整体留出）")
    json.dump({"categories": CATS, "n_train": len(tr), "n_test": len(te),
               "input": "v2/scope_rows.jsonl (11,979 labels)",
               "split_rule": "uid 前缀：test: 整体留出；lab:/s6: 用于训练"},
              open(os.path.join(HERE, "v2", "scope_model_manifest.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=2)

    import numpy as np
    import torch
    from torch.optim import AdamW
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import DistilBertForSequenceClassification, DistilBertTokenizer
    device = "cuda" if torch.cuda.is_available() else "cpu"
    base = os.path.join(HERE, "sound_model")
    tok = DistilBertTokenizer.from_pretrained(base)
    enc = tok([texts[i] for i, _y in tr], truncation=True, max_length=a.max_len,
              padding=True, return_tensors="pt")
    dl = DataLoader(TensorDataset(enc["input_ids"], enc["attention_mask"],
                                  torch.tensor([y for _i, y in tr])),
                    batch_size=a.batch_size, shuffle=True)
    torch.manual_seed(42)
    model = DistilBertForSequenceClassification.from_pretrained(
        base, num_labels=len(CATS), ignore_mismatched_sizes=True).to(device)
    # 类别权重：按**部署分布**（test: 段）与训练分布之比校正，缓解域错位
    import collections
    tr_cnt = collections.Counter(y for _i, y in tr)
    te_cnt = collections.Counter(y for _i, y in te)
    n_tr, n_te = max(1, sum(tr_cnt.values())), max(1, sum(te_cnt.values()))
    class_weights = torch.tensor(
        [max(0.2, min(8.0, (te_cnt.get(c, 0) / n_te) / max(1e-6, tr_cnt.get(c, 0) / n_tr)))
         for c in range(len(CATS))], dtype=torch.float).to(device)
    print("  类别权重：" + "｜".join(f"{CATS[i]}={float(class_weights[i]):.2f}"
                                    for i in range(len(CATS))), flush=True)
    opt = AdamW(model.parameters(), lr=a.lr)
    print(f"训练（device={device}，{a.epochs} epochs，{len(dl)} steps/epoch）", flush=True)
    for ep in range(a.epochs):
        model.train()
        tot = 0.0
        for k, (ids, att, y) in enumerate(dl, 1):
            ids, att, y = ids.to(device), att.to(device), y.to(device)
            out = model(input_ids=ids, attention_mask=att)
            loss = torch.nn.functional.cross_entropy(out.logits, y, weight=class_weights)
            loss.backward()
            opt.step()
            opt.zero_grad()
            tot += float(loss)
            if k % 100 == 0:
                print(f"  [ep{ep+1}] {k}/{len(dl)} loss={tot/k:.4f}", flush=True)
        print(f"[epoch {ep+1}] mean loss={tot/max(len(dl),1):.4f}", flush=True)
    out = os.path.join(HERE, a.out_dir)
    os.makedirs(out, exist_ok=True)
    model.save_pretrained(out)
    tok.save_pretrained(out)
    print(f"[保存] {out}", flush=True)

    # 评测：留出段整体 + 关键混淆（耳机家族三类的合并精确率）
    model.eval()
    probs = []
    with torch.no_grad():
        for b in range(0, len(te), 64):
            batch = [texts[i] for i, _y in te[b:b + 64]]
            e = tok(batch, padding=True, truncation=True, max_length=a.max_len,
                    return_tensors="pt")
            e = {k: v.to(device) for k, v in e.items()}
            probs.append(torch.softmax(model(**e).logits, -1).cpu().numpy())
    P = np.vstack(probs)
    pred = P.argmax(1)
    y = np.array([t for _i, t in te])
    acc = float((pred == y).mean())
    hp_true = np.isin(y, [C2I["headphone"], C2I["earbud"], C2I["headset"]])
    hp_pred = np.isin(pred, [C2I["headphone"], C2I["earbud"], C2I["headset"]])
    tp = int((hp_true & hp_pred).sum())
    prec = tp / max(1, int(hp_pred.sum()))
    rec = tp / max(1, int(hp_true.sum()))
    print(f"  留出段 acc={acc:.4f}｜**耳机家族合并：精确率 {prec:.3f}／召回 {rec:.3f}**"
          f"（n={len(te):,}，真耳机 {int(hp_true.sum()):,}）")
    per = {}
    for c, i in C2I.items():
        m = y == i
        if m.sum():
            per[c] = {"n": int(m.sum()), "acc": round(float((pred[m] == i).mean()), 4)}
    json.dump({"acc": round(acc, 4), "hp_precision": round(prec, 4), "hp_recall": round(rec, 4),
               "n_test": len(te), "per_class": per},
              open(os.path.join(HERE, "v2", "scope_model_eval.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("[写出] v2/model_scope/、v2/scope_model_eval.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
