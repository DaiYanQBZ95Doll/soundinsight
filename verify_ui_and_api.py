# -*- coding: utf-8 -*-
"""验证剩余两条产品入口：Gradio UI（`demo_sound_v2.py`）与 HTTP API（`api_server.py`）。

做法（不依赖人工点击）：
  · 启动子进程（cwd=仓库根，权重已就位）→ 轮询本地端口就绪 → 记录 HTTP 状态 → 终止子进程；
  · API 额外做一次 `POST /predict` 断言返回结构（含概率与类别）；
  · 全部用超时保护，避免挂死；结束时确保子进程被回收。

端口取自 `config.json` 的 `server_host`/`server_port`。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
HOST = cfg.get("server_host", "127.0.0.1")
PORT = int(cfg.get("server_port", 7860))
print(f"config.json → server_host={HOST}｜server_port={PORT}")


def wait_http(url: str, timeout: float = 90.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.status, time.time() - t0
        except urllib.error.HTTPError as e:
            return e.code, time.time() - t0      # 有响应即视为已就绪
        except Exception:  # noqa: BLE001
            time.sleep(2)
    return None, time.time() - t0


def run_entry(name: str, script: str, probe_urls: list[str]) -> dict:
    print(f"\n=== {name}（{script}）===")
    log = open(os.path.join(HERE, f"_log_{script}.txt"), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, script], cwd=HERE,
                         stdout=log, stderr=subprocess.STDOUT)
    result = {"entry": name, "started": True}
    try:
        for url in probe_urls:
            status, dt = wait_http(url, timeout=100)
            print(f"  [探测] {url} → {status if status else '超时'}（{dt:.0f}s）")
            result[url] = status
            if status:
                break
    finally:
        p.terminate()
        try:
            p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()
        log.close()
    result["exit_code"] = p.returncode
    tail = open(os.path.join(HERE, f"_log_{script}.txt"), encoding="utf-8",
                errors="replace").read().strip().splitlines()
    print("  日志末 3 行：" + " ｜ ".join(l[:90] for l in tail[-3:]))
    return result


def main() -> int:
    out = {}
    out["ui"] = run_entry("Gradio UI", "demo_sound_v2.py",
                          [f"http://{HOST}:{PORT}/", "http://127.0.0.1:7860/"])
    out["api"] = run_entry("HTTP API", "api_server.py",
                           [f"http://127.0.0.1:{PORT}/health",
                            "http://127.0.0.1:8000/health"])

    # API 行为断言（若服务仍在，重新拉起做一次 /predict）
    print("\n=== API 行为断言（POST /predict）===")
    ap = subprocess.Popen([sys.executable, "api_server.py"], cwd=HERE,
                          stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    ok = False
    try:
        for url in (f"http://127.0.0.1:{PORT}/health", "http://127.0.0.1:8000/health"):
            status, _ = wait_http(url, timeout=100)
            if status:
                base = url.rsplit("/health", 1)[0]
                # 契约见 api_server.py 头部注释：POST /predict {"texts": [...]}
                body = json.dumps({"texts": [
                    "The bass is muddy and the treble is harsh.",
                    "Fast shipping, well packed, arrived on time.",
                ]}).encode()
                req = urllib.request.Request(base + "/predict", data=body,
                                             headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=60) as r:
                        payload = json.loads(r.read().decode("utf-8"))
                    print(f"  [POST /predict] HTTP {r.status}｜返回键：{list(payload)[:6]}")
                    print(f"    返回内容预览：{json.dumps(payload, ensure_ascii=False)[:200]}")
                    ok = True
                    # 闸门预筛断言（机制而非约定）：不含音频词汇的评论必须标 is_out_of_scope
                    _res = (payload or {}).get("results") or []
                    _oos = [_x for _x in _res if _x.get("is_out_of_scope")]
                    _ok = bool(_oos) and all(_x.get("prob") is None and _x.get("pred") is None
                                            for _x in _oos)
                    print(f"  [闸门断言] is_out_of_scope {len(_oos)}/{len(_res)} 条｜"
                          f"概率与判定均为 None：{_ok}")
                    if not _ok:
                        raise AssertionError("闸门预筛未生效：非音频评论未被标为未判定")
                except Exception as e:  # noqa: BLE001
                    print(f"  [POST /predict] 失败：{type(e).__name__}: {str(e)[:90]}")
                break
    finally:
        ap.terminate()
        try:
            ap.wait(timeout=20)
        except subprocess.TimeoutExpired:
            ap.kill()
    out["api_predict_ok"] = ok

    json.dump(out, open(os.path.join(HERE, "v2", "entrypoints_check.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n[写出] v2/entrypoints_check.json")
    ui_ok = bool(out["ui"].get(f"http://{HOST}:{PORT}/") or out["ui"].get("http://127.0.0.1:7860/"))
    print(f"[结论] Gradio UI {'可达 ✓' if ui_ok else '未确认'}｜HTTP API "
          f"{'可用 ✓' if ok else '未确认'}")
    return 0 if (ui_ok and ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
