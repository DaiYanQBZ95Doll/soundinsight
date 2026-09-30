# -*- coding: utf-8 -*-
"""泄漏核查：val_v2 的文本是否落在"当前 labeled_llm 的 80% 训练划分"里。"""
import csv
import sys

from sklearn.model_selection import train_test_split

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


llm = read("labeled_llm.csv")
texts = [str(r["text"]) for r in llm]
labels = [int(float(r.get("sound_negative_llm") or 0)) for r in llm]
print(f"labeled_llm: {len(texts)} 行，正例 {sum(labels)}")

X_tr, X_va, y_tr, y_va = train_test_split(
    texts, labels, test_size=0.2, random_state=42, stratify=labels)
tr_set, va_set = set(X_tr), set(X_va)
print(f"当前 80/20 划分：train {len(X_tr)}（正例 {sum(y_tr)}） / "
      f"val {len(X_va)}（正例 {sum(y_va)}）")

v2 = read("val_v2.csv")
v2_texts = [str(r["text"]) for r in v2]
v2_pos = [r for r in v2 if str(r["sound_negative"]).strip() == "1"]
print(f"val_v2: {len(v2_texts)} 行，正例 {len(v2_pos)}")

in_tr = sum(1 for t in v2_texts if t in tr_set)
in_va = sum(1 for t in v2_texts if t in va_set)
pos_in_tr = sum(1 for r in v2_pos if str(r["text"]) in tr_set)
print(f"\nval_v2 文本落在当前训练集：{in_tr}/{len(v2_texts)}"
      f"（{in_tr / len(v2_texts) * 100:.1f}%）")
print(f"val_v2 文本落在当前验证集：{in_va}/{len(v2_texts)}"
      f"（{in_va / len(v2_texts) * 100:.1f}%）")
print(f"val_v2 的 251 条正例中落在训练集的：{pos_in_tr}"
      f"（{pos_in_tr / max(len(v2_pos), 1) * 100:.1f}%）")
print("\n判读：若正例大量落在训练集，则在 val_v2 上评估用当前 labeled_llm"
      "训练的模型会因记忆而虚高。")
