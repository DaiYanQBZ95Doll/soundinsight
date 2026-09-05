# -*- coding: utf-8 -*-
# C4 聚合：LLM 错误分类统计 + 抽取 30 条（15 FP / 15 FN，等距抽样）供 DSH 抽查。
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
INP = os.path.join(HERE, "llm_err_input.jsonl")
CLS = os.path.join(HERE, "llm_err_classes.jsonl")
SPOT = os.path.join(HERE, "spot_check_30.jsonl")

FP_CATS = ["fp_neutral_compare", "fp_keyword", "fp_other_issue",
           "fp_label_noise", "fp_short", "fp_other"]
FN_CATS = ["fn_soft", "fn_mixed", "fn_label_noise", "fn_short", "fn_other"]


def main() -> None:
    inp = {}
    with open(INP, encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            inp[o["id"]] = o
    cls = {}
    with open(CLS, encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            cls[o["id"]] = o
    assert len(cls) == len(inp), f"classified {len(cls)}/{len(inp)}"
    fp, fn = [], []
    for i in sorted(inp):
        row = dict(inp[i], **cls[i])
        (fp if row["kind"] == "fp" else fn).append(row)
    print(f"FP={len(fp)} FN={len(fn)}")
    for name, rows, cats in [("FP", fp, FP_CATS), ("FN", fn, FN_CATS)]:
        c = Counter(r["cat"] for r in rows)
        print(f"\n{name} 类别分布:")
        for cat in cats:
            print(f"  {cat}: {c.get(cat, 0)}")
        other = [k for k in c if k not in cats]
        for k in other:
            print(f"  (未知类别 {k}): {c[k]}")

    # 等距抽 30 条
    sel = fp[::max(1, len(fp) // 15)][:15] + fn[::max(1, len(fn) // 15)][:15]
    with open(SPOT, "w", encoding="utf-8") as f:
        for r in sel:
            f.write(json.dumps({
                "id": r["id"], "kind": r["kind"], "text": r["text"],
                "label": r["label"], "prob": r["prob"],
                "cat": r["cat"], "reason": r["reason"],
            }, ensure_ascii=False) + "\n")
    print(f"\nsaved spot-check -> {SPOT} ({len(sel)} rows)")


if __name__ == "__main__":
    main()
