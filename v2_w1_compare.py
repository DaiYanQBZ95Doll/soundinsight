# -*- coding: utf-8 -*-
"""W1 对比：128 与 256 两个变体在无泄漏留出集上的完整分桶结果。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PAIRS = (("max_len=128", "v2/w1_eval_model_maxlen128_truncate(max128)_val_v3_test.json"),
         ("max_len=256", "v2/w1_eval_model_maxlen256_truncate(max256)_val_v3_test.json"))

for tag, path in PAIRS:
    d = json.load(open(path, encoding="utf-8"))
    t = d["thresholds"].get("0.5", {})
    print(f"{tag}: 整体 P {t.get('P')}% R {t.get('R')}% F1 {t.get('F1')} "
          f"(TP{t.get('TP')}/FP{t.get('FP')}/FN{t.get('FN')})")
    for b, v in d["buckets"].items():
        m = v.get("@0.5")
        if m:
            print(f"    桶 {b}: n={v['n']} pos={v['pos']} F1 {m['F1']} "
                  f"R {m['R']}% TP{m['TP']}/FN{m['FN']}")
    print()
