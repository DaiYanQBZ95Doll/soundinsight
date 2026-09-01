# -*- coding: utf-8 -*-
# 本脚本用于扩充数据：从已下载的 8MB 前缀继续分段拉取 Electronics.jsonl.gz，
# 增量解压解析评论记录，最多保存 10 万条到 electronics_expanded.csv。
import json
import os
import sys
import time
import zlib

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = ("https://mcauleylab.ucsd.edu/public_datasets/data/"
       "amazon_2023/raw/review_categories/Electronics.jsonl.gz")
HERE = os.path.dirname(os.path.abspath(__file__))
PREFIX_FILE = os.path.join(HERE, "electronics_prefix.bin")
OUTPUT_CSV = os.path.join(HERE, "electronics_expanded.csv")
CHUNK = 8 * 1024 * 1024
MAX_PREFIX = 128 * 1024 * 1024   # 最多累计拉取 128MB 前缀
RECORD_CAP = 100_000             # 最多保存 10 万条


def parse_prefix(prefix: bytes):
    dec = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    records = []
    try:
        out = dec.decompress(prefix)
    except zlib.error as e:
        raise RuntimeError(f"gzip decompress failed: {e}") from e
    # 一次性按换行切分，避免逐行 split 的平方级复制开销
    for line in out.split(b"\n"):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records, dec


def fetch_chunk(offset: int) -> bytes:
    for attempt in range(1, 6):
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
        except Exception as e:  # noqa: BLE001 - retry transport errors
            print(f"  [retry {attempt}] {type(e).__name__}; wait {4 * attempt}s",
                  flush=True)
            time.sleep(4 * attempt)
    raise RuntimeError("chunk fetch failed after retries")


def main() -> None:
    import pandas as pd

    if os.path.exists(PREFIX_FILE):
        with open(PREFIX_FILE, "rb") as f:
            prefix = bytearray(f.read())
    else:
        prefix = bytearray()
    print(f"现有前缀: {len(prefix) / (1 << 20):.1f} MB")

    while len(prefix) < MAX_PREFIX:
        body = fetch_chunk(len(prefix))
        with open(PREFIX_FILE, "ab") as f:
            f.write(body)
        prefix += body
        print(f"  前缀 {len(prefix) / (1 << 20):.0f} MB", flush=True)

    records, _ = parse_prefix(bytes(prefix))
    print(f"解析出 {len(records)} 条记录")

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
        if len(rows) >= RECORD_CAP:
            break

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"保存 {len(df)} 行 -> {OUTPUT_CSV}")
    print("rating 分布:")
    print(df["rating"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
