# -*- coding: utf-8 -*-
"""M3 执行方侧部署复测 + M8-a 提交规则核对（能自己做的部分先做掉）。

M3：冷启动/TTFB、应用直链响应、Gradio 前端可达性（三次测量取中位数）
M8-a：从仓库已记录的官方页面抓取提交规则（格式/大小/次数/截止），并与我们的包核对
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (SoundInsight precheck)"}
TARGETS = [
    ("ModelScope 空间页", "https://modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight"),
    ("应用直链", "https://daiyanqbz95doll-soundinsight.ms.show"),
]


def timed(url: str, timeout: int = 30) -> dict:
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(200_000)
        return {"status": r.status, "sec": round(time.time() - t0, 2),
                "bytes": len(body), "ok": True}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "sec": round(time.time() - t0, 2), "ok": False,
                "err": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"status": None, "sec": round(time.time() - t0, 2), "ok": False,
                "err": f"{type(e).__name__}: {str(e)[:60]}"}


print("=== M3：部署可达性与冷启动（各测 3 次）===")
m3 = {}
for name, url in TARGETS:
    runs = [timed(url) for _ in range(3)]
    secs = [r["sec"] for r in runs if r["status"]]
    m3[name] = {"url": url, "runs": runs,
                "median_sec": round(statistics.median(secs), 2) if secs else None,
                "status": runs[-1]["status"]}
    print(f"  {name}: 状态 {runs[-1]['status']}｜耗时 "
          f"{[r['sec'] for r in runs]} → 中位数 {m3[name]['median_sec']}s")

print("\n=== M8-a：官方提交规则（从页面抓取）===")
PAGES = [
    ("决赛入围名单公示", "https://builderx.csdn.net/activity-site/ceshi1/bansaimingdan"),
]
rules = {}
for label, url in PAGES:
    r = timed(url, timeout=30)
    if r.get("ok"):
        req = urllib.request.Request(url, headers=UA)
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        # 抽取含关键词的文本片段
        txt = re.sub(r"<[^>]+>", " ", html)
        txt = re.sub(r"\s+", " ", txt)
        hits = []
        for kw in ("MB", "大小", "格式", "zip", "提交次数", "截止", "10 月", "10月"):
            for m in re.finditer(re.escape(kw), txt):
                seg = txt[max(0, m.start() - 60):m.start() + 80].strip()
                if seg not in hits:
                    hits.append(seg)
        rules[label] = hits[:6]
        print(f"  [{label}] 抓取成功（{len(html):,} 字节）")
        for h in hits[:6]:
            print(f"     … {h[:150]}")
    else:
        print(f"  [{label}] 抓取失败：{r.get('err')}")

print("\n=== 我们的包 vs 已知约束 ===")
import zipfile
z = os.path.join(HERE, "更新世界的锋芒_SoundInsight_决赛入围定稿作品.zip")
size = os.path.getsize(z)
with zipfile.ZipFile(z) as zf:
    names = zf.namelist()
    bad = zf.testzip()
print(f"  包大小 {size:,} B（{size/1024/1024:.1f} MB）｜条目 {len(names)}｜CRC 校验 "
      f"{'通过' if bad is None else '失败：' + str(bad)}")
print(f"  条目：{names}")
print(f"  命名含队伍名/方案名/阶段："
      f"{all(k in z for k in ('更新世界的锋芒', 'SoundInsight', '决赛'))}")
json.dump({"m3": m3, "rules": rules}, open(os.path.join(HERE, "v2", "m3_m8a_precheck.json"),
                                           "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("  [写出] v2/m3_m8a_precheck.json")
