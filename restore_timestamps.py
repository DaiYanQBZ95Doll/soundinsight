# -*- coding: utf-8 -*-
# 本脚本用于 D 批次数据考古修复：重新解析原始前缀，重建 electronics_expanded.csv，
# 在保持原行顺序与 text/rating 完全一致的前提下恢复 timestamp 列。
import json
import os
import sys
import zlib

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PREFIX_FILE = os.path.join(HERE, "electronics_prefix.bin")
OUT_CSV = os.path.join(HERE, "electronics_expanded.csv")
RECORD_CAP = 100_000


def main() -> None:
    with open(PREFIX_FILE, "rb") as f:
        data = f.read()
    d = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    out = d.decompress(data)

    old = pd.read_csv(OUT_CSV, encoding="utf-8", keep_default_na=False)
    old_texts = old["text"].astype(str).tolist()

    rows = []
    for line in out.split(b"\n"):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        text, rating = rec.get("text"), rec.get("rating")
        if text is None or rating is None:
            continue
        text = str(text).strip()
        try:
            rating = int(float(rating))
        except (TypeError, ValueError):
            continue
        if text == "" or not (1 <= rating <= 5):
            continue
        ts = rec.get("timestamp")
        rows.append({"text": text, "rating": rating, "timestamp": ts})
        if len(rows) >= RECORD_CAP:
            break

    new_texts = [r["text"] for r in rows]
    assert len(new_texts) == len(old_texts), \
        f"行数不一致 {len(new_texts)} vs {len(old_texts)}"
    mism = sum(1 for a, b in zip(new_texts, old_texts) if a != b)
    assert mism == 0, f"{mism} 行 text 不一致，中止重建"
    print(f"对齐校验通过：{len(rows)} 行 text 完全一致")

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    n_ts = int(df["timestamp"].notna().sum())
    print(f"保存 -> {OUT_CSV} | 含时间戳 {n_ts}/{len(df)}")
    ts_min = pd.to_datetime(df["timestamp"].min(), unit="ms", utc=True)
    ts_max = pd.to_datetime(df["timestamp"].max(), unit="ms", utc=True)
    print(f"时间范围: {ts_min} ~ {ts_max}")


if __name__ == "__main__":
    main()
