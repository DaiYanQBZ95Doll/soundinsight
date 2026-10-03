# -*- coding: utf-8 -*-
"""S2a/S2b：世代钉死与 manifest（含 Kimi 要求的精度项）。

做什么：
  ① 全量 SHA256（64 位）＋行数＋正例数：各世代标签文件与冻结评测集；
  ② 前缀哈希碰撞实证（解释为何必须全量）：labeled_llm.csv vs labeled_llm_before_mid_remove.csv；
  ③ 复现 v1 划分（before_treble + seed42 + 0.2 + stratify）并与 train_final.log 四数对账；
  ④ val_v2 与复现 val 的文本重合：**定位那 1 行差异**，并分 raw／normalized 两种口径各报重合数；
  ⑤ val_v2 内部重复行披露（行数／唯一数／重复行数／其中正例数）；
  ⑥ 输出 docs/split_manifest.md（v1 已钉／v2 候选输入待佐证／v3-lite 待登记）＋ v2/split_manifest.json

用法：python s2_generation_audit.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))


def sha256_full(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_prefix(path: str, nbytes: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read(nbytes))
    return h.hexdigest()


def load_labels(path: str):
    """→ (texts, labels)；标签列取 sound_negative_llm / sound_negative / label。"""
    texts, labels = [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            texts.append(str(row.get("text") or ""))
            for k in ("sound_negative_llm", "sound_negative", "label"):
                if k in row and str(row[k]).strip() not in ("", "None"):
                    try:
                        labels.append(int(float(row[k])))
                    except ValueError:
                        labels.append(None)
                    break
            else:
                labels.append(None)
    return texts, labels


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("\u3000", " ")).strip()


FILES = {
    "v1 训练输入": "labeled_llm_before_treble.csv",
    "v1 真留出侧": "val_v2.csv",
    "v2 候选训练输入": "labeled_llm.csv",
    "v2 冻结测试集": "val_v3_test.csv",
    "v2 调参侧": "val_v3_tune.csv",
    "另一世代(中间态)": "labeled_llm_before_mid_remove.csv",
    "另一世代(中间态2)": "labeled_llm_before_mid_demote.csv",
}
info = {}
print("=== ① 全量哈希与计数 ===")
for tag, fn in FILES.items():
    p = os.path.join(HERE, fn)
    if not os.path.isfile(p):
        print(f"  [缺] {fn}")
        continue
    texts, labels = load_labels(p)
    pos = sum(1 for x in labels if x == 1)
    uniq = len({norm(t) for t in texts})
    d = {"file": fn, "sha256": sha256_full(p), "sha256_1mb": sha256_prefix(p),
         "rows": len(texts), "positives": pos, "unique_norm": uniq,
         "dup_rows": len(texts) - uniq}
    info[tag] = d
    print(f"  {tag:<16} {fn:<38} rows={d['rows']:>6} pos={pos:>5} "
          f"uniq={uniq:>6} sha={d['sha256'][:16]}")

print("\n=== ② 前缀哈希碰撞实证（为何禁用前缀） ===")
a, b = info.get("v2 候选训练输入"), info.get("另一世代(中间态)")
if a and b:
    same_p = a["sha256_1mb"] == b["sha256_1mb"]
    same_f = a["sha256"] == b["sha256"]
    print(f"  {a['file']} vs {b['file']}")
    print(f"    前 1MB 哈希相同：{same_p}（{a['sha256_1mb'][:12]}）｜全量哈希相同：{same_f}")
    info["prefix_collision_demo"] = {"a": a["file"], "b": b["file"],
                                     "same_1mb": same_p, "same_full": same_f}

print("\n=== ③ 复现 v1 划分并与 train_final.log 对账 ===")
v1 = info.get("v1 训练输入")
if v1:
    texts, labels = load_labels(os.path.join(HERE, v1["file"]))
    from sklearn.model_selection import train_test_split
    tr, va = train_test_split(list(range(len(labels))), test_size=0.2,
                              random_state=42, stratify=labels)
    pos_tr = sum(1 for i in tr if labels[i] == 1)
    pos_va = sum(1 for i in va if labels[i] == 1)
    log = {"train": 80000, "train_pos": 1006, "val": 20000, "val_pos": 251}
    got = {"train": len(tr), "train_pos": pos_tr, "val": len(va), "val_pos": pos_va}
    ok = got == log
    print(f"  日志 {log}｜复现 {got}｜**{'四数全中 ✓' if ok else '不一致 ✗'}**")
    info["v1_reproduction"] = {"log": log, "reproduced": got, "match": ok}

print("\n=== ④ val_v2 与复现 val 的重合（定位那 1 行差异） ===")
if v1:
    val_texts = [texts[i] for i in va]
    raw_val = {hashlib.sha256(t.encode()).hexdigest() for t in val_texts}
    nrm_val = {hashlib.sha256(norm(t).encode()).hexdigest() for t in val_texts}
    v2t, v2l = load_labels(os.path.join(HERE, "val_v2.csv"))
    raw_v2 = [hashlib.sha256(t.encode()).hexdigest() for t in v2t]
    nrm_v2 = [hashlib.sha256(norm(t).encode()).hexdigest() for t in v2t]
    hit_raw = sum(1 for h in set(raw_v2) if h in raw_val)
    hit_nrm = sum(1 for h in set(nrm_v2) if h in nrm_val)
    print(f"  val_v2 唯一文本 {len(set(raw_v2))}｜与复现 val 重合（raw）**{hit_raw}**")
    print(f"  归一化后重合（normalized）**{hit_nrm}** / {len(set(nrm_v2))}")
    miss = [i for i, h in enumerate(raw_v2) if h not in raw_val]
    uniq_miss = sorted({raw_v2[i] for i in miss})
    print(f"  未命中行数 {len(miss)}（唯一 {len(uniq_miss)}）")
    for h in uniq_miss[:3]:
        idx = raw_v2.index(h)
        print(f"    · row {idx}｜norm 命中={nrm_v2[idx] in nrm_val}｜{v2t[idx][:110]!r}")
    info["val_v2_overlap"] = {"raw_hit": hit_raw, "norm_hit": hit_nrm,
                              "unique_v2": len(set(raw_v2)), "unique_val": len(raw_val),
                              "unmatched_rows": len(miss),
                              "unmatched_sample": [v2t[i][:120] for i in miss[:3]]}

print("\n=== ⑤ val_v2 内部重复披露 ===")
v2t, v2l = load_labels(os.path.join(HERE, "val_v2.csv"))
uniq = {}
for t, y in zip(v2t, v2l):
    uniq.setdefault(norm(t), []).append(y)
dups = {k: v for k, v in uniq.items() if len(v) > 1}
dup_rows = sum(len(v) for v in dups.values())
dup_pos = sum(1 for v in dups.values() for y in v if y == 1)
print(f"  行 {len(v2t)}｜唯一 {len(uniq)}｜重复行 {dup_rows}（{dup_rows/len(v2t)*100:.1f}%）"
      f"｜重复行中正例 {dup_pos}")
info["val_v2_duplicates"] = {"rows": len(v2t), "unique": len(uniq),
                             "dup_rows": dup_rows, "dup_positives": dup_pos}

json.dump(info, open(os.path.join(HERE, "v2", "split_manifest.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\n[写出] v2/split_manifest.json（下一步生成 docs/split_manifest.md）")
