# -*- coding: utf-8 -*-
"""P0-3 原始字段恢复：从 `electronics_prefix.bin` 解析出 asin / parent_asin /
verified_purchase / user_id / helpful_vote / title，并与现有数据集对齐。

**对齐方法（与 `restore_timestamps.py` 同一套已验证做法）**：
原始前缀中混有 text 缺失或评分越界的记录，`electronics_expanded.csv` 是在解析时
**过滤后**再截断到 10 万行生成的，因此"原始记录序号 = CSV 行号"**不成立**
（实测在第 1,824 条记录处开始偏移）。正确做法是复现同一套过滤，再按 **text 序列**
逐行比对作为对齐证据。

过滤条件（照抄 restore_timestamps.py）：text 与 rating 均存在、text 非空、
rating 归一后落在 1–5；随后截断到 100,000 条。

隐私边界（冻结清单 §二 P0-3）：
- `user_id` 仅用于聚合统计（去重/集中度），不输出到任何对外材料；
- 输出文件含 user_id，按 .gitignore 不入库（只保留在本地供 W14/W15 复算）。

用法：
    python recover_meta_fields.py                 # 全量（100k）
    python recover_meta_fields.py --limit 5000    # 快速自测
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAW = "electronics_prefix.bin"
BASE_CSV = "electronics_expanded.csv"
OUT_CSV = "review_meta_v2.csv"
FIELDS = ("parent_asin", "asin", "verified_purchase", "user_id",
          "helpful_vote", "title")
RECORD_CAP = 100_000


def _num(v):
    """rating 归一为 float（原始为 '3.0'，基准 CSV 为 '3'）。"""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_filtered(limit: int):
    """按 restore_timestamps.py 的同一套过滤解析，产出对齐后的记录序列。"""
    kept = 0
    dropped = Counter()
    with gzip.open(RAW, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                dropped["解析失败"] += 1
                continue
            text, rating = rec.get("text"), rec.get("rating")
            if text is None or rating is None:
                dropped["缺 text/rating"] += 1
                continue
            text = str(text).strip()
            r = _num(rating)
            if text == "":
                dropped["空 text"] += 1
                continue
            if r is None or not (1 <= r <= 5):
                dropped["评分越界"] += 1
                continue
            rec["_text"] = text
            rec["_rating"] = int(r)
            yield rec
            kept += 1
            if kept >= limit:
                return


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=RECORD_CAP)
    args = ap.parse_args()

    if not os.path.isfile(RAW):
        print(f"[FAIL] 缺少原始前缀文件 {RAW}")
        return 1

    base_text, base_rating = [], []
    with open(BASE_CSV, encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            base_text.append(str(row.get("text", "")))
            base_rating.append(str(row.get("rating", "")).strip())
    print(f"基准 {BASE_CSV}：{len(base_text)} 行")

    rows, text_mismatch, rating_mismatch = [], [], []
    nonempty = Counter()
    for idx, rec in enumerate(parse_filtered(args.limit)):
        item = {k: rec.get(k) for k in FIELDS}
        for k in FIELDS:
            if item[k] not in (None, "", [], "[]"):
                nonempty[k] += 1
        got_text = rec["_text"]
        if idx < len(base_text) and got_text != base_text[idx]:
            if len(text_mismatch) < 3:
                text_mismatch.append(idx)
        a, b = _num(rec["_rating"]), _num(base_rating[idx]) if idx < len(base_rating) else None
        if a != b:
            if len(rating_mismatch) < 3:
                rating_mismatch.append((idx, a, b))
        rows.append([idx, rec.get("timestamp")] + [item[k] for k in FIELDS]
                    + [rec["_rating"]])

    n = len(rows)
    scope = min(n, len(base_text))
    partial = n < len(base_text)
    print(f"解析后（同一套过滤）：{n} 行")
    ok_text = not text_mismatch
    scope_note = f"（仅比对前 {scope} 行，--limit 自测模式）" if partial else "（全量逐行）"
    print(f"对齐校验（text 序列）：{'✓ 一致' if ok_text else f'✗ 不一致，例如行 {text_mismatch}'}{scope_note}")
    print(f"对齐校验（rating 数值）：{'✓ 一致' if not rating_mismatch else f'✗ {rating_mismatch}'}{scope_note}")
    print("字段非空率：")
    for k in FIELDS:
        print(f"  {k:<18} {nonempty[k]:>6}/{n} ({nonempty[k] / max(n, 1) * 100:.1f}%)")

    users = Counter(r[5] for r in rows if r[5])
    dup_users = sum(1 for _, c in users.items() if c > 1)
    verified_false = sum(1 for r in rows if str(r[4]).lower() == "false")
    pa = Counter(r[2] for r in rows if r[2])
    print(f"不同 user_id {len(users)}；多评用户 {dup_users}；单人最多 {max(users.values()) if users else 0}")
    print(f"verified_purchase=False {verified_false} ({verified_false / max(n, 1) * 100:.1f}%)")
    print(f"不同 parent_asin {len(pa)}；单 ASIN 最多 {max(pa.values()) if pa else 0}")

    if not ok_text or rating_mismatch:
        print("\n[FAIL] 对齐未通过：字段与现有数据集不可按行序关联，"
              "须先解决再供 W4/W14/W15 使用（不得静默忽略）。")
        return 2

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row_index", "timestamp"] + list(FIELDS) + ["rating"])
        w.writerows(rows)
    print(f"\n[PASS] 已写出 {OUT_CSV}（{n} 行，对齐证据＝text 序列逐行一致）。"
          "含 user_id，按隐私边界不入库。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
