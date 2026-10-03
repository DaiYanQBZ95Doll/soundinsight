# -*- coding: utf-8 -*-
"""v3-lite：**只改训练侧标签**（口径纠正），其余全部沿用 v2 配方与**固定划分**。

设计（逐一说明为什么）：
  ① 划分固定：仍用 `train_test_split(test_size=0.2, seed=42, stratify=原标签)`——
     与 v2 完全一致，保证 `val_v3_tune` / `val_v3_test` 仍在训练侧之外（否则评测被污染）；
  ② 只改标签：训练侧中，**口径外（非耳机家族）的 LLM 正例改判为负例**；
     正例从 ~1,024 条降到耳机家族约 424 条；负例不变（含被改判者约 79.6k）；
  ③ 其余不动：架构 DistilBERT、max_len 256、epochs 3、batch 16、lr 2e-5、seed 42；
  ④ 单变量：不改损失、不降采样、不动阈值协议 → 结果可归因于"标签口径"这一项。

用法：python v3lite_train.py [--max-len 256] [--epochs 3] [--out-dir v2/model_inscope]
产物：模型目录 + v2/v3lite_eval_test.json（val_v3_test 全量 + 耳机子集）
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


def load_all():
    texts, labels = [], []
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            texts.append(str(row["text"]))
            labels.append(int(float(row.get("sound_negative_llm") or 0)))
    scope = {}
    with open(os.path.join(HERE, "v2", "scope_rows.jsonl"), encoding="utf-8",
              errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            uid = str(rec.get("uid", ""))
            if uid.startswith("lab:"):
                scope[int(uid.split(":")[1])] = rec.get("category", "unclear")
    return texts, labels, scope


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--out-dir", default=os.path.join("v2", "model_inscope"))
    args = ap.parse_args()

    import torch
    from torch.optim import AdamW
    from torch.utils.data import DataLoader, TensorDataset
    from sklearn.model_selection import train_test_split
    from transformers import DistilBertForSequenceClassification, DistilBertTokenizer

    texts, orig, scope = load_all()
    corrected = []
    flipped = 0
    for i, y in enumerate(orig):
        if y == 1 and scope.get(i, "unclear") not in HP:
            corrected.append(0)          # 口径外正例 → 负例
            flipped += 1
        else:
            corrected.append(y)
    n_pos_o, n_pos_c = sum(orig), sum(corrected)
    print(f"语料 {len(texts):,}｜原正例 {n_pos_o}｜**纠正后正例 {n_pos_c}**"
          f"｜被改判为负 {flipped} 条（口径外）")

    # ① 划分：与 v2 完全一致（用**原标签**分层），保证 tune/test 不在训练侧
    idx = list(range(len(texts)))
    tr_idx, va_idx = train_test_split(idx, test_size=0.2, random_state=SEED, stratify=orig)
    y_tr = [corrected[i] for i in tr_idx]
    print(f"训练侧 {len(tr_idx):,}（正例 {sum(y_tr)}）｜留出侧 {len(va_idx):,}（不参与训练）")
    json.dump({"seed": SEED, "n_train": len(tr_idx), "n_holdout": len(va_idx),
               "pos_original": n_pos_o, "pos_corrected": n_pos_c, "flipped": flipped},
              open(os.path.join(HERE, "v2", "v3lite_split_manifest.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=2)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    base = os.path.join(HERE, "sound_model")
    tok = DistilBertTokenizer.from_pretrained(base)
    print("分词中…")
    tr_texts = [texts[i] for i in tr_idx]
    enc = tok(tr_texts, truncation=True, max_length=args.max_len, padding=True,
              return_tensors="pt")
    dl = DataLoader(TensorDataset(enc["input_ids"], enc["attention_mask"],
                                  torch.tensor(y_tr)),
                    batch_size=args.batch_size, shuffle=True)
    torch.manual_seed(SEED)
    model = DistilBertForSequenceClassification.from_pretrained(base, num_labels=2).to(device)
    opt = AdamW(model.parameters(), lr=args.lr)
    print(f"开始训练（device={device}，{args.epochs} epochs，{len(dl)} steps/epoch）")
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
    out_dir = os.path.join(HERE, args.out_dir) if not os.path.isabs(args.out_dir) else args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    print(f"[保存] {out_dir}")

    # ② 评测：val_v3_test 全量 + 耳机子集（口径内）
    import importlib.util
    spec = importlib.util.spec_from_file_location("w1", os.path.join(HERE, "v2_w1_longtext.py"))
    w1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(w1)
    t_texts, t_labels = w1.load_csv_texts(w1.TEST_CSV)
    model.eval()
    probs = w1.predict(model, tok, t_texts, args.max_len, "truncate", args.max_len, 64, device)
    # 测试集口径（test:<i>）
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
    res = {"model": args.out_dir, "max_len": args.max_len,
           "split": json.load(open(os.path.join(HERE, "v2", "v3lite_split_manifest.json"),
                                   encoding="utf-8")), "groups": {}}
    groups = {"全测试集": list(range(len(t_texts))),
              "耳机家族（范围内）": [i for i in range(len(t_texts)) if sc.get(i) in HP]}
    for name, ids in groups.items():
        y = [t_labels[i] for i in ids]
        p = [probs[i] for i in ids]
        m05 = w1.metrics(y, p, 0.5)
        m06 = w1.metrics(y, p, 0.6)
        res["groups"][name] = {"n": len(ids), "pos": sum(y), "at_0.5": m05, "at_0.6": m06}
        print(f"  [{name}] n={len(ids)} 正例={sum(y)}｜F1@0.5={m05['F1']}｜F1@0.6={m06['F1']}"
              f"｜P@0.5={m05['P']}｜R@0.5={m05['R']}")
    json.dump(res, open(os.path.join(HERE, "v2", "v3lite_eval_test.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[写出] v2/v3lite_eval_test.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
