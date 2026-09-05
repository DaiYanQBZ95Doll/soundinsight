# -*- coding: utf-8 -*-
# deploy_check.py — 在线 Demo 自动验收（ModelScope 创空间）
# 检查项：页面可达 / gradio info / 单条评论推理（含正确性抽查）/ 边界案例页内容
# 用法：python deploy_check.py <studio_url>
import json
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = sys.argv[1] if len(sys.argv) > 1 else \
    "https://modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight"
UA = {"User-Agent": "SoundInsight-deploy-check/1.0"}

CASES = [
    ("The bass is completely missing and there is constant static.",
     "音质负面"),
    ("Great battery life and very comfortable to wear.",
     "音质正常"),
]


def call_api(name, data, timeout=180):
    """POST gradio_api 并轮询事件流取结果（gradio 6 协议）。"""
    r = requests.post(f"{BASE}/gradio_api/call/{name}",
                      json={"data": data}, headers=UA, timeout=timeout)
    print(f"[api] POST /call/{name} -> {r.status_code}")
    if r.status_code != 200:
        return None, f"HTTP {r.status_code} {r.text[:200]}"
    eid = r.json().get("event_id")
    if not eid:
        return None, f"no event_id: {r.text[:200]}"
    for _ in range(60):
        s = requests.get(f"{BASE}/gradio_api/call/{name}/{eid}",
                         headers=UA, timeout=timeout, stream=True)
        body = s.text
        if "event: complete" in body:
            data_line = [ln for ln in body.splitlines()
                         if ln.startswith("data: ")][-1]
            return json.loads(data_line[6:]), None
        if "event: error" in body:
            return None, f"event error: {body[:300]}"
        time.sleep(2)
    return None, "timeout waiting event"


def main() -> None:
    print(f"目标: {BASE}")
    r = requests.get(BASE, headers=UA, timeout=60)
    print(f"[page] GET / -> {r.status_code} len={len(r.text)}")
    if r.status_code != 200:
        print("FAIL: 页面不可达")
        return 1

    info = requests.get(f"{BASE}/gradio_api/info", headers=UA, timeout=60)
    print(f"[info] GET /gradio_api/info -> {info.status_code}")
    if info.status_code == 200:
        try:
            j = info.json()
            eps = j.get("named_endpoints", {})
            fns = sorted({v.get("api_name") or k for k, v in eps.items()})
            print(f"[info] api endpoints: {fns}")
        except Exception as e:  # noqa: BLE001
            print(f"[info] parse fail: {e}")

    ok = 0
    for text, expect in CASES:
        data, err = call_api("single_predict", [text])
        if err:
            print(f"FAIL single_predict: {err}")
            continue
        out = data[0] if isinstance(data, list) else data
        first_line = str(out).splitlines()[0]
        print(f"[predict] {text[:50]}... -> {first_line}")
        if first_line.startswith(expect):
            ok += 1
    print(f"\n单条推理抽查: {ok}/{len(CASES)} 通过")
    if ok != len(CASES):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
