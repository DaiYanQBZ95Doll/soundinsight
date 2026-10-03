# -*- coding: utf-8 -*-
"""S6 第二步：复核抽样框（700 条）→ 扩词表标签 → 重训（v3-lite-B）→ 评测。

复用 `review_pool.py` 的复核实现（同提示词、并发、断点、成本核算），
新增"按行号清单复核"入口 `--rows-json`，避免另写一套。

用法：python s6_relabel_retrain.py review   # 只复核
      python s6_relabel_retrain.py train    # 复核完成后重训 + 评测
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))


def patch_review_pool():
    """给 review_pool.py 增 `--rows-json`：按预注册行号清单复核（复用其全部机制）。"""
    P = os.path.join(HERE, "review_pool.py")
    s = open(P, encoding="utf-8").read()
    if "--rows-json" in s:
        print("  [查] review_pool 已支持 --rows-json")
        return True
    pairs = [
        ('    ap.add_argument("--report", action="store_true")',
         '    ap.add_argument("--report", action="store_true")\n'
         '    ap.add_argument("--rows-json", default="",\n'
         '                    help="按预注册行号清单复核（S6）：JSON 内含 row_index 列表")'),
        ('    pool = build_pool(args.layer)\n    if args.limit:',
         '    if args.rows_json:\n'
         '        rows_want = json.load(open(args.rows_json, encoding="utf-8"))["label_row_index"]\n'
         '        pool = []\n'
         '        with open(CORPUS, encoding="utf-8", errors="replace") as fh:\n'
         '            want = set(rows_want)\n'
         '            for i, r in enumerate(csv.DictReader(fh)):\n'
         '                if i in want:\n'
         '                    pool.append({"row_index": i, "text": str(r.get("text") or ""),\n'
         '                                 "words": len(str(r.get("text") or "").split())})\n'
         '        print(f"[s6] 按清单复核 {len(pool)} 条")\n'
         '    else:\n'
         '        pool = build_pool(args.layer)\n    if args.limit:'),
        ('    out_path = os.path.join(OUT, f"review_{args.layer}.jsonl")',
         '    out_path = os.path.join(OUT, f"review_{args.layer}.jsonl")\n'
         '    if args.rows_json:\n'
         '        out_path = os.path.join(OUT, "review_s6_vocab.jsonl")'),
    ]
    for old, new in pairs:
        if s.count(old) != 1:
            print(f"  [跳过] review_pool.py：命中 {s.count(old)}（{old[:40]!r}）")
            return False
    for old, new in pairs:
        s = s.replace(old, new, 1)
    try:
        ast.parse(s)
    except SyntaxError as e:
        print(f"  [失败] review_pool.py 未写盘：{e}")
        return False
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  [改] review_pool.py：新增 --rows-json（按预注册清单复核）")
    return True


def do_review():
    if not patch_review_pool():
        return 1
    cmd = [sys.executable, "review_pool.py", "--layer", "s6",
           "--rows-json", os.path.join("v2", "s6_preregistration.json"), "--workers", "12"]
    print("  运行：" + " ".join(cmd))
    return subprocess.call(cmd, cwd=HERE)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["review", "train"])
    a = ap.parse_args()
    if a.stage == "review":
        sys.exit(do_review())
    print("train 阶段：见 v3lite_train.py 的扩词表版本（下一步实现）")
