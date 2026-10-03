# -*- coding: utf-8 -*-
"""Demo **冷启动**端到端实测（P0④）：模拟评委拿到提交包后的**首次**运行。

与 `verify_demo_end_to_end.py` 的区别：那个把真实权重**复制**进去（跳过下载），
本脚本**不复制**，真跑 `download_models.py` 下 530MB → 加载 → 出报告——这正是评委的路径。

步骤：① 从决赛包解出 Demo.zip 到 `_coldstart_test/`；② 真跑 download_models.py（计时）；
③ 跑产品（Agent CLI）出报告并核对节数与未判定计数；④ 记录失败点；⑤ 清理权重（不留在工作区）。

产物：`v2/coldstart_report.json`、`docs/coldstart_test.md`
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_coldstart_test")
FINALS = os.path.join(HERE, "更新世界的锋芒_SoundInsight_决赛入围定稿作品.zip")


def run(cmd, cwd, timeout, label):
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return {"label": label, "rc": r.returncode, "sec": round(time.time() - t0, 1),
                "tail": out[-800:], "ok": r.returncode == 0}
    except subprocess.TimeoutExpired:
        return {"label": label, "rc": None, "sec": round(time.time() - t0, 1),
                "tail": f"超时（>{timeout}s）", "ok": False}


report = {"steps": []}
if os.path.isdir(WORK):
    shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK, exist_ok=True)

# ① 解包（决赛包 → 内层 Demo.zip → 工作目录）
inner = None
with zipfile.ZipFile(FINALS) as z:
    for n in z.namelist():
        if n.lower().endswith("demo.zip"):
            inner = n
            open(os.path.join(WORK, "_demo.zip"), "wb").write(z.read(n))
            break
if not inner:
    print("[失败] 决赛包内无 Demo.zip")
    sys.exit(1)
with zipfile.ZipFile(os.path.join(WORK, "_demo.zip")) as dz:
    dz.extractall(WORK)
os.remove(os.path.join(WORK, "_demo.zip"))
names = os.listdir(WORK)
has_weights = any(n.endswith((".safetensors", ".bin")) for n in names) or \
    os.path.isdir(os.path.join(WORK, "sound_model"))
print(f"① 解包完成：{len(names)} 项｜**自带权重：{has_weights}**（应为 False —— 冷启动）")
report["steps"].append({"label": "unpack", "ok": True, "files": len(names),
                        "ships_weights": has_weights})

# ② 真跑下载
print("② 下载权重（530MB，计时中…）")
r = run([sys.executable, "download_models.py"], WORK, 3600, "download_models")
report["steps"].append(r)
print(f"   rc={r['rc']}｜{r['sec']}s｜{'成功 ✓' if r['ok'] else '失败 ✗'}")
if not r["ok"]:
    print("   末尾输出：" + r["tail"][-400:])

# ③ 跑产品出报告（Agent CLI，走闸门预筛）
print("③ 跑产品（Agent CLI）")
r2 = run([sys.executable, "soundinsight_agent.py", "--csv", "sample_reviews_100.csv"],
         WORK, 1800, "agent_run")
report["steps"].append(r2)
print(f"   rc={r2['rc']}｜{r2['sec']}s｜{'成功 ✓' if r2['ok'] else '失败 ✗'}")
rep_md = os.path.join(WORK, "insight_report_v2.md")
sections = oos = None
if os.path.isfile(rep_md):
    t = open(rep_md, encoding="utf-8", errors="replace").read()
    sections = t.count("\n## ")
    import re
    m = re.search(r"未判定（不含音频词汇）：(\d+) 条", t)
    oos = int(m.group(1)) if m else None
report["report"] = {"sections": sections, "n_out_of_scope": oos}
print(f"   报告节数 {sections}｜未判定计数 {oos}")

# ④ 清理权重（避免 530MB 留在工作区）
freed = 0
for root, dirs, files in os.walk(WORK):
    for f in files:
        if f.endswith((".safetensors", ".bin", ".pt")):
            p = os.path.join(root, f)
            freed += os.path.getsize(p)
            os.remove(p)
report["freed_bytes"] = freed
print(f"④ 清理权重：释放 {freed/1e6:.0f} MB（工作目录保留其余文件以便复查）")

json.dump(report, open(os.path.join(HERE, "v2", "coldstart_report.json"), "w",
                       encoding="utf-8"), ensure_ascii=False, indent=2)
ok_all = all(s.get("ok") for s in report["steps"])
dl = report["steps"][1]
md = f"""# Demo 冷启动实测（P0④，评委首次运行路径）

> 与 `verify_demo_end_to_end.py` 的区别：那个把权重**复制**进去（跳过下载）；本测试**不复制**，
> 真跑 `download_models.py`。日期 2026-10-03。

| 步骤 | 结果 | 耗时 |
|---|---|---|
| ① 解包决赛包→Demo.zip | {'✓' if report['steps'][0]['ok'] else '✗'}（{report['steps'][0]['files']} 项，**自带权重 {report['steps'][0]['ships_weights']}**） | — |
| ② `download_models.py`（约 530MB） | {'**成功 ✓**' if dl['ok'] else '**失败 ✗**'} | {dl['sec']}s |
| ③ `soundinsight_agent.py --csv sample_reviews_100.csv` | {'**成功 ✓**' if report['steps'][2]['ok'] else '**失败 ✗**'} | {report['steps'][2]['sec']}s |

- 报告节数：**{sections}**｜未判定（不含音频词汇）计数：**{oos}**
- 总判定：**{'全通过 ✓' if ok_all else '存在失败 ✗'}**
- 下载后已清理权重（释放 {freed/1e6:.0f} MB），工作目录 `_coldstart_test/` 保留其余文件供复查。

## 结论

冷启动路径{'**已实测可用**——评委按 README 首次运行可在约 '
          f'{int((dl["sec"] + report["steps"][2]["sec"]) // 60)} 分钟内完成（含 530MB 下载）'
          if ok_all else '**存在失败点，需修**'}（详见 `v2/coldstart_report.json` 的逐步输出）。
"""
open(os.path.join(HERE, "docs", "coldstart_test.md"), "w", encoding="utf-8",
     newline="\n").write(md)
print(f"[写出] docs/coldstart_test.md、v2/coldstart_report.json｜总判定："
      f"{'全通过 ✓' if ok_all else '存在失败 ✗'}")
