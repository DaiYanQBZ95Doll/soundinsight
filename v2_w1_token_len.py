# -*- coding: utf-8 -*-
"""量取 val_v3_test 的 token 长度分布，判定 256 是否够用、是否需要 512/切窗。"""
import csv
import sys

from transformers import DistilBertTokenizer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
tok = DistilBertTokenizer.from_pretrained("sound_model")

lens = []
with open("val_v3_test.csv", encoding="utf-8", errors="replace") as fh:
    for row in csv.DictReader(fh):
        lens.append(len(tok(str(row["text"]), add_special_tokens=False)["input_ids"]))

n = len(lens)
print(f"val_v3_test 共 {n} 条")
for lo, hi, name in ((0, 128, "≤128 token"), (129, 256, "129–256"),
                     (257, 512, "257–512"), (513, 10 ** 9, ">512 token")):
    c = sum(1 for L in lens if lo <= L <= hi)
    print(f"  {name:<12} {c:>5} 条（{c / n * 100:.1f}%）")
big = sum(1 for L in lens if L > 128)
big2 = sum(1 for L in lens if L > 256)
print(f"\n超过 128 token：{big} 条；其中又超过 256 token：{big2} 条"
      f"（占超长部分的 {big2 / max(big, 1) * 100:.1f}%）")
print(f"最长文本：{max(lens)} token；P95={sorted(lens)[int(n * 0.95)]}；"
      f"P99={sorted(lens)[int(n * 0.99)]}")
