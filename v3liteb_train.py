# -*- coding: utf-8 -*-
"""v3-lite-B：口径纠正 + **扩词表补标**后的重训（S6 的执行端）。

正例 = 原有耳机家族正例 ∪（S6 复核为音质抱怨 ∧ 耳机家族）——**均限训练侧**；
负例 = 训练侧其余（含口径外的原 LLM 正例，按 D-Q9 口径保持为负）；
划分与配方与 v2/v3-lite **完全一致**（seed 42、用原始标签分层、max_len 256、3 epochs）。

用法：python v3liteb_train.py [--epochs 3] [--out-dir v2/model_inscope_b]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 42
HP = {"headphone", "earbud", "headset"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--out-dir", default=os.path.join("v2", "model_inscope_b"))
    args = ap.parse_args()

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
        if u.startswith(("lab:", "s6:")):
            scope[u] = rec.get("category", "unclear")
    s6_pos = set()
    with open(os.path.join(HERE, "v2", "review_s6_vocab.jsonl"), encoding="utf-8",
              errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if int(rec.get("sound_negative") or 0) == 1:
                s6_pos.add(int(rec["row_index"]))

    corrected = []
    added = 0
    for i, y in enumerate(orig):
        keep_pos = (y == 1 and scope.get(f"lab:{i}", "unclear") in HP)
        if not keep_pos and i in s6_pos and scope.get(f"s6:{i}", "unclear") in HP:
            keep_pos = True
            added += 1
        corrected.append(1 if keep_pos else 0)
    print(f"语料 {len(texts):,}｜原正例 {sum(orig)}｜**纠正后 {sum(corrected)}**"
          f"（其中扩词表新增 **{added}** 条）")

    from sklearn.model_selection import train_test_split
    tr, va = train_test_split(list(range(len(orig))), test_size=0.2, random_state=SEED,
                              stratify=orig)
    y_tr = [corrected[i] for i in tr]
    print(f"训练侧 {len(tr):,}（正例 **{sum(y_tr)}**）｜留出侧 {len(va):,}（不参与训练）")
    json.dump({"positives_total": sum(corrected), "s6_added": added,
               "train_positives": sum(y_tr)}, open(os.path.join(HERE, "v2",
               "v3liteb_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    import torch
    from torch.optim import AdamW
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import DistilBertForSequenceClassification, DistilBertTokenizer
    device = "cuda" if torch.cuda.is_available() else "cpu"
    base = os.path.join(HERE, "sound_model")
    tok = DistilBertTokenizer.from_pretrained(base)
    enc = tok([texts[i] for i in tr], truncation=True, max_length=args.max_len,
              padding=True, return_tensors="pt")
    dl = DataLoader(TensorDataset(enc["input_ids"], enc["attention_mask"],
                                  torch.tensor(y_tr)), batch_size=args.batch_size, shuffle=True)
    torch.manual_seed(SEED)
    model = DistilBertForSequenceClassification.from_pretrained(base, num_labels=2).to(device)
    opt = AdamW(model.parameters(), lr=args.lr)
    print(f"开始训练（device={device}，{args.epochs} epochs，{len(dl)} steps/epoch）", flush=True)
    for ep in range(args.epochs):
        model.train()
        tot = 0.0
        for k, (ids, att, y) in enumerate(dl, 1):
            ids, att, y = ids.to(device), att.to(device), y.to(device)
            out = model(input_ids=ids, attention_mask=att, labels=y)
            out.loss.backward()
            opt.step()
            opt.zero_grad()
            tot += float(out.loss)
            if k % 1000 == 0:
                print(f"  [ep{ep+1}] {k}/{len(dl)} loss={tot/k:.4f}", flush=True)
        print(f"[epoch {ep+1}] mean loss={tot/max(len(dl),1):.4f}", flush=True)
    out_dir = os.path.join(HERE, args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    print(f"[保存] {out_dir}", flush=True)

    import importlib.util
    spec = importlib.util.spec_from_file_location("w1", os.path.join(HERE, "v2_w1_longtext.py"))
    w1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(w1)
    t_texts, t_labels = w1.load_csv_texts(w1.TEST_CSV)
    model.eval()
    probs = w1.predict(model, tok, t_texts, args.max_len, "truncate", args.max_len, 64, device)
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
    res = {"model": args.out_dir, "max_len": args.max_len, "groups": {}}
    for name, ids in (("全测试集", list(range(len(t_texts)))),
                      ("耳机家族（范围内）", [i for i in range(len(t_texts)) if sc.get(i) in HP])):
        y = [t_labels[i] for i in ids]
        p = [probs[i] for i in ids]
        res["groups"][name] = {"n": len(ids), "pos": sum(y),
                               "at_0.5": w1.metrics(y, p, 0.5), "at_0.6": w1.metrics(y, p, 0.6)}
        m = res["groups"][name]["at_0.5"]
        print(f"  [{name}] n={len(ids)} 正例={sum(y)}｜F1@0.5={m['F1']}｜P={m['P']}｜R={m['R']}")
    json.dump(res, open(os.path.join(HERE, "v2", "v3liteb_eval_test.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[写出] v2/v3liteb_eval_test.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
