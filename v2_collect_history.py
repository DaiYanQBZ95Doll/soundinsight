# -*- coding: utf-8 -*-
"""为《三阶段差异文档》采集史实：初赛/复赛/决赛的交付物、数据、模型、指标、材料。"""
import json
import os
import re
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GIT = r"C:\Program Files\Git\cmd\git.exe"


def sh(*a):
    return subprocess.run([GIT, *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=".").stdout.strip()


print("=== ① 仓库时间线（首末提交）===")
print("  最早：" + sh("log", "--reverse", "--format=%ad|%h|%s", "--date=format:%m-%d %H:%M", "-1")
      .splitlines()[0][:100])
print("  最新：" + sh("log", "--format=%ad|%h|%s", "--date=format:%m-%d %H:%M", "-1")[:100])
print("  总提交：" + sh("rev-list", "--count", "HEAD"))
print("\n  各阶段提交分布：")
for pat, label in ((r"初赛|创意方案|competition_v2", "初赛相关"),
                   (r"复赛|competition_v3|competition_v4|复赛作品", "复赛相关"),
                   (r"决赛|frozen_execution|v2_|W\d+ 线|M\d", "决赛相关")):
    n = len(sh("log", "--format=%s", "--all").splitlines())
    hits = [l for l in sh("log", "--format=%s").splitlines() if re.search(pat, l)]
    print(f"    {label}: {len(hits)} 条提交信息命中（总 {n}）")

print("\n=== ② 三个阶段的提交物 ===")
for f in ("更新世界的锋芒_SoundInsight_复赛作品.zip",
          "更新世界的锋芒_SoundInsight_决赛入围定稿作品.zip"):
    if os.path.isfile(f):
        with zipfile.ZipFile(f) as z:
            info = [(i.filename, i.file_size) for i in z.infolist()]
        print(f"  {f}（{os.path.getsize(f):,} B, {len(info)} 条目）")
        for n, s in info:
            print(f"     {n}  {s:,} B")

print("\n=== ③ 数据与标签演进 ===")
for f in ("local_data.csv", "labeled_llm.csv", "review_meta_v2.csv", "val_v2.csv",
          "val_v3_tune.csv", "val_v3_test.csv"):
    if os.path.isfile(f):
        n = sum(1 for _ in open(f, encoding="utf-8", errors="replace")) - 1
        print(f"  {f}: {n:,} 行｜{os.path.getsize(f):,} B")

print("\n=== ④ 关键指标（两代）===")
rs = open("results_summary.md", encoding="utf-8", errors="replace").read()
for ln in rs.splitlines():
    if re.search(r"0\.6871|0\.6241|0\.7220|0\.7206|0\.7811|0\.8273|0\.5333|0\.6481", ln):
        print("  " + ln.strip()[:150])

print("\n=== ⑤ 初赛/复赛材料文件 ===")
for pat in ("competition_v2", "competition_v3", "competition_v4", "创意方案"):
    hits = [f for f in os.listdir(".") if pat in f]
    if hits:
        print(f"  {pat}: {hits}")
    d = [x for x in os.listdir(".") if os.path.isdir(x) and pat in x]
    if d:
        print(f"  {pat}（目录）: {d} → {os.listdir(d[0])[:6]}")

print("\n=== ⑥ 决赛新增的机械验证资产 ===")
tools = sorted(t for t in os.listdir(".") if t.endswith(".py") and
               re.match(r"(check_|verify_|scan_|precommit|safe_commit|run_all|make_gold|"
                        r"score_gold|review_pool|refresh_)", t))
print(f"  共 {len(tools)} 个：{tools}")
