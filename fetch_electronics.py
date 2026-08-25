# -*- coding: utf-8 -*-
# 本脚本用于数据获取：从 McAuley Lab 官方源分段下载 Electronics 评论文件前缀，解析出前五千条评论并保存。
"""Fetch first 5000 Electronics reviews from the OFFICIAL McAuley 2023 dataset.

Source: https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/
        raw/review_categories/Electronics.jsonl.gz (6.47 GB total)
Method: HTTP Range partial download of the file prefix + incremental gzip
decompression; only the first ~tens of MB are transferred. Reuses any local
prefix already downloaded (offline-first).
"""
import json
import os
import random
import sys
import time
import zlib

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = ("https://mcauleylab.ucsd.edu/public_datasets/data/"
       "amazon_2023/raw/review_categories/Electronics.jsonl.gz")
HERE = os.path.dirname(os.path.abspath(__file__))
PREFIX_FILE = os.path.join(HERE, "electronics_prefix.bin")
OUTPUT_CSV = os.path.join(HERE, "local_data.csv")
CHUNK = 8 * 1024 * 1024
MAX_FETCH = 160 * 1024 * 1024
KEEP_ROWS = 5000
RANDOM_SEED = 42


def decompress_records(data: bytes, dec, carry: bytes, records: list[dict]):
    """Feed gzip bytes into an incremental decompressor, collect JSON records."""
    if dec is None:
        dec = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    out = dec.decompress(data) + carry
    while b"\n" in out:
        line, out = out.split(b"\n", 1)
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return dec, out


def fetch_chunk(offset: int) -> bytes:
    """Fetch one 8 MB range chunk with retries against network resets."""
    last_err = None
    for attempt in range(1, 5):
        try:
            headers = {"Range": f"bytes={offset}-{offset + CHUNK - 1}",
                       "User-Agent": "dsh-data-pipeline/1.0"}
            r = requests.get(URL, headers=headers, timeout=120, stream=True)
            if r.status_code != 206:
                raise RuntimeError(f"HTTP {r.status_code}")
            body = b""
            for part in r.iter_content(1 << 20):
                body += part
                if len(body) >= CHUNK:
                    break
            r.close()
            if not body:
                raise RuntimeError("empty body")
            return body
        except Exception as e:  # noqa: BLE001 - retry any transport error
            last_err = e
            wait = 4 * attempt
            print(f"  [retry {attempt}] chunk fetch failed: "
                  f"{type(e).__name__}; waiting {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"chunk fetch failed after retries: {last_err}")


def main() -> None:
    records: list[dict] = []
    dec = None
    carry = b""
    offset = 0

    import os

    if os.path.exists(PREFIX_FILE):
        with open(PREFIX_FILE, "rb") as f:
            existing = f.read()
        offset = len(existing)
        print(f"Reusing local prefix: {offset / (1 << 20):.1f} MB")
        dec, carry = decompress_records(existing, dec, carry, records)
        print(f"Parsed {len(records)} records from local prefix")

    # Count how many VALID rows we already have, to know when to stop fetching
    def valid_rows():
        rows = []
        for rec in records:
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
            rows.append({"text": text, "rating": rating})
            if len(rows) >= KEEP_ROWS:
                break
        return rows

    rows = valid_rows()
    while len(rows) < KEEP_ROWS and offset < MAX_FETCH and not (dec and dec.eof):
        body = fetch_chunk(offset)
        with open(PREFIX_FILE, "ab") as f:
            f.write(body)
        offset += len(body)
        try:
            dec, carry = decompress_records(body, dec, carry, records)
        except zlib.error as e:
            raise RuntimeError(f"gzip decompress failed: {e}") from e
        rows = valid_rows()
        print(f"  fetched total {offset / (1 << 20):.0f} MB, "
              f"{len(records)} records, {len(rows)} valid rows", flush=True)

    if not records:
        raise RuntimeError("no records obtained")
    raw_first = records[0]
    print(f"Total prefix: {offset / (1 << 20):.1f} MB, "
          f"{len(records)} records parsed")

    print("\nRaw schema (first record keys):", sorted(raw_first.keys()))
    print("Raw first record sample:")
    print(json.dumps({k: raw_first[k] for k in ("rating", "asin", "title",
                                                "text", "timestamp")},
                     ensure_ascii=False)[:400])

    import pandas as pd

    df = pd.DataFrame(rows)
    df = df.head(KEEP_ROWS).reset_index(drop=True)
    print(f"valid rows kept: {len(df)}")

    def is_chinese(s: str) -> bool:
        return sum("\u4e00" <= ch <= "\u9fff" for ch in s) > 3

    n_cn = int(df["text"].map(is_chinese).sum())
    print(f"language: English (Chinese-like rows: {n_cn})")

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"Saved -> {OUTPUT_CSV}")

    print("\n=== PREVIEW ===")
    print("1. Total rows:", len(df))
    print("2. First 5 rows:")
    for i, row in enumerate(df.head(5).itertuples(index=False), 1):
        print(f"  [{i}] rating={row.rating} | {row.text[:160]}")
    print("3. Rating distribution:")
    dist = df["rating"].value_counts().sort_index()
    for rating, count in dist.items():
        print(f"  rating={int(rating)}: {count} ({count / len(df):.2%})")
    print("4. 10 random reviews:")
    sample = df.sample(n=min(10, len(df)), random_state=RANDOM_SEED)
    for i, row in enumerate(sample.itertuples(index=False), 1):
        print(f"\n--- Sample {i} (rating={int(row.rating)}) ---")
        print(row.text[:600])

    print("\n=== VALIDATION ===")
    print(f"rows={len(df)} | cols={list(df.columns)} | "
          f"nulls={int(df.isna().sum().sum())}")
    print(f"rating range: {df['rating'].min()}..{df['rating'].max()} | "
          f"unique: {sorted(df['rating'].unique().tolist())}")
    print(f"empty texts: {int((df['text'] == '').sum())} | "
          f"duplicates: {int(df.duplicated().sum())}")
    print(f"avg text length: {df['text'].str.len().mean():.0f} chars")


if __name__ == "__main__":
    main()
