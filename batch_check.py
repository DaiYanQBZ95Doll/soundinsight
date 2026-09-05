# -*- coding: utf-8 -*-
# 批量分析接口验收：上传 sample_reviews_100.csv -> batch_analyze -> 检查报告内容
import json
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = sys.argv[1] if len(sys.argv) > 1 else \
    "https://daiyanqbz95doll-soundinsight.ms.show"
UA = {"User-Agent": "SoundInsight-deploy-check/1.0"}
CSV = r"C:\deepseek-harness-master\soundinsight\sample_reviews_100.csv"

data = open(CSV, "rb").read()
r = requests.post(f"{BASE}/gradio_api/upload",
                  files={"files": ("sample_reviews_100.csv", data)},
                  headers=UA, timeout=120)
print("upload ->", r.status_code, r.text[:200])
if r.status_code != 200:
    sys.exit(1)
paths = r.json()
path = paths[0] if isinstance(paths, list) else paths.get("files", [None])[0]
print("file path:", path)

t0 = time.time()
r = requests.post(f"{BASE}/gradio_api/call/batch_analyze",
                  json={"data": [{"path": path,
                                  "url": None,
                                  "size": len(data),
                                  "orig_name": "sample_reviews_100.csv",
                                  "mime_type": "text/csv",
                                  "is_stream": False,
                                  "meta": {"_type": "gradio.FileData"}}]},
                  headers=UA, timeout=300)
print("call ->", r.status_code, r.text[:200])
if r.status_code != 200:
    sys.exit(1)
eid = r.json().get("event_id")
for _ in range(90):
    s = requests.get(f"{BASE}/gradio_api/call/batch_analyze/{eid}",
                     headers=UA, timeout=300)
    body = s.text
    if "event: complete" in body:
        dl = [ln for ln in body.splitlines() if ln.startswith("data: ")][-1]
        out = json.loads(dl[6:])
        report = out[0] if isinstance(out, list) else out
        print(f"batch 完成 耗时 {time.time()-t0:.1f}s")
        print(str(report)[:600])
        sys.exit(0)
    if "event: error" in body:
        print("event error:", body[:300])
        sys.exit(1)
    time.sleep(2)
print("timeout")
sys.exit(1)
