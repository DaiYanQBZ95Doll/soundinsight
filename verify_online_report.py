# -*- coding: utf-8 -*-
# verify_online_report.py —— 拉取线上批量报告全文并校验关键节与提示行是否齐全
import json
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = sys.argv[1] if len(sys.argv) > 1 else \
    "https://daiyanqbz95doll-soundinsight.ms.show"
CSV = r"C:\deepseek-harness-master\soundinsight\sample_reviews_100.csv"
UA = {"User-Agent": "SoundInsight-deploy-check/1.0"}
s = requests.Session()
s.trust_env = False

data = open(CSV, "rb").read()
r = s.post(f"{BASE}/gradio_api/upload",
           files={"files": ("sample_reviews_100.csv", data)},
           headers=UA, timeout=120)
path = r.json()[0]
r = s.post(f"{BASE}/gradio_api/call/batch_analyze",
           json={"data": [{"path": path, "url": None, "size": len(data),
                           "orig_name": "sample_reviews_100.csv",
                           "mime_type": "text/csv", "is_stream": False,
                           "meta": {"_type": "gradio.FileData"}}]},
           headers=UA, timeout=300)
eid = r.json()["event_id"]
for _ in range(90):
    t = s.get(f"{BASE}/gradio_api/call/batch_analyze/{eid}",
              headers=UA, timeout=300).text
    if "event: complete" in t:
        dl = [ln for ln in t.splitlines() if ln.startswith("data: ")][-1]
        out = json.loads(dl[6:])
        report = out[0]
        print(f"报告字符数：{len(report)}")
        checks = ["## 一、总体概况", "## 二、问题分布", "## 三、典型案例",
                  "## 四、行动建议", "## 五、验证指标", "## 六、附注",
                  "归因概率", "成本对照", "未经校准"]
        for c in checks:
            print(("  OK   " if c in report else "  MISS ") + c)
        print("\n--- 四/五节原文 ---")
        for line in report.splitlines():
            if line.startswith("## 四") or line.startswith("## 五") \
                    or line.startswith("- 紧急") or "中置信" in line \
                    or line.startswith("建议复评"):
                print("  " + line)
        sys.exit(0)
    if "event: error" in t:
        print("event error:", t[:200])
        sys.exit(1)
    time.sleep(2)
print("timeout")
sys.exit(1)
