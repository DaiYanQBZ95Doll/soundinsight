# -*- coding: utf-8 -*-
"""W1 长文本截断修复：训练变体与推理变体的统一入口。

背景（冻结清单 §二 W1）：v1 用 max_len=128 截断，>128 token 桶 F1 0.565、
召回 54.4%（占数据 18.6%）。本脚本提供四条路线：

    变体 A  train --max-len 256      训练时直接放宽窗口（需重训）
    变体 B  train --max-len 512      同上（更长）
    变体 C  eval --mode segment      不改模型，推理时切窗取最大概率（最省）
    变体 D  eval --mode segment --seg-len 256  配合 A 的模型再切窗

评测口径（与 v1 可比）：
- 训练集：`labeled_llm.csv` 按 `sound_negative_llm` 分层，seed 42，test_size 0.2
  （与 prep_quick_split.py / train_final.py 同一划分，保证与 v1 可比）；
- 评测集：`val_v2.csv`（冻结 20k，正例 251）——**只用于本阶段的可比性对照**；
  v2 的主指标须报在 `val_v3_test`（见 W6 划分协议），本脚本输出会同时给出两套。
- 长度桶：按 tokenizer 编码长度分为 ≤64 / 65–128 / >128（与 length_bucket_eval 同口径），
  截断模式下 >128 桶的输入会被截到 max_len。

用法：
    python v2_w1_longtext.py eval --model sound_model --mode truncate
    python v2_w1_longtext.py eval --model sound_model --mode segment --seg-len 128 --stride 64
    python v2_w1_longtext.py train --max-len 256 --out-dir v2/model_maxlen256
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import torch
from sklearn.metrics import precision_recall_fscore_support
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(HERE, "labeled_llm.csv")
VAL_CSV = os.path.join(HERE, "val_v2.csv")
TUNE_CSV = os.path.join(HERE, "val_v3_tune.csv")
TEST_CSV = os.path.join(HERE, "val_v3_test.csv")
BASE_MODEL = os.path.join(HERE, "sound_model")
BUCKETS = ((0, 64, "<=64"), (65, 128, "65-128"), (129, 10 ** 9, ">128"))


def load_csv_texts(path):
    import csv
    texts, labels = [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        rdr = csv.DictReader(fh)
        for row in rdr:
            texts.append(str(row["text"]))
            for key in ("sound_negative_llm", "sound_negative"):
                if key in row and str(row[key]).strip() not in ("", "None"):
                    labels.append(int(float(row[key])))
                    break
            else:
                labels.append(-1)
    return texts, labels


def metrics(y, p, thr):
    pred = (np.asarray(p) >= thr).astype(int)
    pr, rc, f1, _ = precision_recall_fscore_support(
        y, pred, average="binary", zero_division=0)
    tp = int(((pred == 1) & (np.asarray(y) == 1)).sum())
    fp = int(((pred == 1) & (np.asarray(y) == 0)).sum())
    fn = int(((pred == 0) & (np.asarray(y) == 1)).sum())
    return {"thr": thr, "P": round(float(pr) * 100, 1), "R": round(float(rc) * 100, 1),
            "F1": round(float(f1), 4), "TP": tp, "FP": fp, "FN": fn}


@torch.no_grad()
def predict(model, tok, texts, max_len, mode, seg_len, stride, device, bs=64):
    """返回每条文本的正类概率。segment 模式：切窗后取最大概率。"""
    out = np.zeros(len(texts), dtype=np.float32)
    for i in range(0, len(texts), bs):
        batch = texts[i:i + bs]
        if mode == "truncate":
            enc = tok(batch, truncation=True, max_length=max_len,
                      padding=True, return_tensors="pt").to(device)
            logits = model(**enc).logits
            out[i:i + len(batch)] = torch.softmax(logits, -1)[:, 1].cpu().numpy()
        else:  # segment
            ids = tok(batch, add_special_tokens=False)["input_ids"]
            chunks, owner = [], []
            for j, seq in enumerate(ids):
                if not seq:
                    seq = [tok.unk_token_id]
                starts = list(range(0, max(1, len(seq) - seg_len + 1), stride)) or [0]
                if starts[-1] + seg_len < len(seq):
                    starts.append(max(0, len(seq) - seg_len))
                for s in starts:
                    piece = seq[s:s + seg_len]
                    if not piece:
                        continue
                    chunks.append(tok.prepare_for_model(
                        [tok.cls_token_id] + piece + [tok.sep_token_id],
                        return_tensors="pt")["input_ids"][0])
                    owner.append(j)
            if not chunks:
                continue
            pad = torch.nn.utils.rnn.pad_sequence(
                chunks, batch_first=True, padding_value=tok.pad_token_id).to(device) \
                if hasattr(torch.nn.utils.rnn, "pad_sequence") else None
            if pad is None:
                from torch.nn.utils.rnn import pad_sequence
                pad = pad_sequence(chunks, batch_first=True,
                                   padding_value=tok.pad_token_id).to(device)
            att = (pad != tok.pad_token_id).long().to(device)
            logits = model(input_ids=pad, attention_mask=att).logits
            probs = torch.softmax(logits, -1)[:, 1].cpu().numpy()
            for j, p in zip(owner, probs):
                out[i + j] = max(out[i + j], float(p))
    return out


def evaluate(tag, texts, labels, probs, lengths, thresholds, out):
    res = {"tag": tag, "n": len(texts), "pos": int(sum(1 for x in labels if x == 1)),
           "thresholds": {}, "buckets": {}}
    for thr in thresholds:
        res["thresholds"][f"{thr}"] = metrics(labels, probs, thr)
    for lo, hi, name in BUCKETS:
        idx = [k for k, L in enumerate(lengths) if lo <= L <= hi]
        if not idx:
            continue
        y = [labels[k] for k in idx]
        p = [probs[k] for k in idx]
        if sum(1 for x in y if x == 1) == 0:
            res["buckets"][name] = {"n": len(idx), "pos": 0, "note": "无正例"}
            continue
        entry = {"n": len(idx), "pos": int(sum(1 for x in y if x == 1))}
        for thr in thresholds:
            entry[f"@{thr}"] = metrics(y, p, thr)
        res["buckets"][name] = entry
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    print(f"[写出] {out}")
    for thr, m in res["thresholds"].items():
        print(f"  整体 @{thr}: P {m['P']}% R {m['R']}% F1 {m['F1']} (TP{m['TP']}/FP{m['FP']}/FN{m['FN']})")
    for name, e in res["buckets"].items():
        if "note" in e:
            print(f"  桶 {name}: n={e['n']} {e['note']}")
            continue
        line = f"  桶 {name}: n={e['n']} pos={e['pos']}"
        for thr in thresholds:
            mm = e.get(f"@{thr}")
            if mm:
                line += f" | @{thr} F1 {mm['F1']} R {mm['R']}%"
        print(line)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("eval")
    pe.add_argument("--model", default=BASE_MODEL)
    pe.add_argument("--mode", choices=("truncate", "segment"), default="truncate")
    pe.add_argument("--max-len", type=int, default=128)
    pe.add_argument("--seg-len", type=int, default=128)
    pe.add_argument("--stride", type=int, default=64)
    pe.add_argument("--out", default=None)
    pe.add_argument("--thresholds", default="0.5")

    pt = sub.add_parser("train")
    pt.add_argument("--max-len", type=int, default=256)
    pt.add_argument("--out-dir", required=True)
    pt.add_argument("--epochs", type=int, default=3)
    pt.add_argument("--batch-size", type=int, default=16)
    pt.add_argument("--lr", type=float, default=2e-5)
    pt.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device}")

    if args.cmd == "eval":
        texts, labels = load_csv_texts(VAL_CSV)
        tok = DistilBertTokenizer.from_pretrained(args.model)
        model = DistilBertForSequenceClassification.from_pretrained(
            args.model).to(device).eval()
        thr_path = os.path.join(args.model, "threshold.json")
        thrs = [float(x) for x in args.thresholds.split(",")]
        if os.path.isfile(thr_path):
            cfg = json.load(open(thr_path, encoding="utf-8"))
            tuned = cfg.get("threshold") or cfg.get("best_threshold")
            if tuned and float(tuned) not in thrs:
                thrs.append(float(tuned))
        lengths = [len(tok(t, add_special_tokens=False)["input_ids"]) for t in texts]
        probs = predict(model, tok, texts, args.max_len, args.mode,
                        args.seg_len, args.stride, device)
        tag = f"{os.path.basename(args.model)}/{args.mode}"
        if args.mode == "segment":
            tag += f"(seg{args.seg_len}/stride{args.stride})"
        else:
            tag += f"(max{args.max_len})"
        out = args.out or os.path.join(
            HERE, "v2", f"w1_eval_{tag.replace('/', '_')}.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        evaluate(tag, texts, labels, probs, lengths, sorted(set(thrs)), out)

        # 同时输出到 val_v3_test（若 W6 划分已就绪），供 v2 主指标使用
        if os.path.isfile(TEST_CSV):
            t_texts, t_labels = load_csv_texts(TEST_CSV)
            t_len = [len(tok(t, add_special_tokens=False)["input_ids"]) for t in t_texts]
            t_probs = predict(model, tok, t_texts, args.max_len, args.mode,
                              args.seg_len, args.stride, device)
            out2 = out.replace(".json", "_val_v3_test.json")
            print("\n[val_v3_test]")
            evaluate(tag + "@val_v3_test", t_texts, t_labels, t_probs, t_len,
                     sorted(set(thrs)), out2)
        return 0

    # train
    from torch.optim import AdamW
    from sklearn.model_selection import train_test_split
    from torch.utils.data import DataLoader, TensorDataset
    import csv

    texts, labels = load_csv_texts(INPUT_CSV)
    print(f"训练数据 {len(texts)} 行，正例 {sum(1 for x in labels if x == 1)}")
    X_tr, X_va, y_tr, y_va = train_test_split(
        texts, labels, test_size=0.2, random_state=args.seed, stratify=labels)
    tok = DistilBertTokenizer.from_pretrained(BASE_MODEL)
    enc = tok(list(X_tr), truncation=True, max_length=args.max_len,
              padding=True, return_tensors="pt")
    ds = TensorDataset(enc["input_ids"], enc["attention_mask"],
                       torch.tensor(y_tr))
    dl = DataLoader(ds, batch_size=args.batch_size, shuffle=True)
    torch.manual_seed(args.seed)
    model = DistilBertForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=2).to(device)
    opt = AdamW(model.parameters(), lr=args.lr)
    for ep in range(args.epochs):
        model.train()
        tot = 0.0
        for ids, att, y in dl:
            ids, att, y = ids.to(device), att.to(device), y.to(device)
            out = model(input_ids=ids, attention_mask=att, labels=y)
            out.loss.backward()
            opt.step()
            opt.zero_grad()
            tot += float(out.loss)
        print(f"[epoch {ep + 1}] loss={tot / max(len(dl), 1):.4f}")
    os.makedirs(args.out_dir, exist_ok=True)
    model.save_pretrained(args.out_dir)
    tok.save_pretrained(args.out_dir)
    print(f"[保存] {args.out_dir}")

    # 训练完立即在同口径 val_v2 上评估（截断模式，用训练时的窗口）
    model.eval()
    v_texts, v_labels = load_csv_texts(VAL_CSV)
    v_len = [len(tok(t, add_special_tokens=False)["input_ids"]) for t in v_texts]
    probs = predict(model, tok, v_texts, args.max_len, "truncate", args.max_len,
                    64, device)
    out = os.path.join(HERE, "v2", f"w1_eval_maxlen{args.max_len}.json")
    evaluate(f"maxlen{args.max_len}/truncate", v_texts, v_labels, probs, v_len,
             [0.5], out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
