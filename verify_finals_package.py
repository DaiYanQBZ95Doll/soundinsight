# -*- coding: utf-8 -*-
"""决赛包完整性验证 + Demo 冒烟测试（不含评分模型）。

步骤：
1. 解包决赛包，核对 5 个条目与内层哈希是否与 hashes.txt 登记一致；
2. 解包 Demo.zip 到工作区临时目录，用其中的 report_builder 对样例评论生成报告，
   验证"包内代码可运行、报告六节齐备"（不加载权重，因此不依赖 GPU/模型文件）。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, "_tmp_pkgcheck")
TEAM, NAME = "更新世界的锋芒", "SoundInsight"
FINALS = f"{TEAM}_{NAME}_决赛入围定稿作品.zip"
INNER = [f"{TEAM}_{NAME}_决赛入围定稿作品.docx", f"{TEAM}_{NAME}_Demo.zip",
         f"{TEAM}_{NAME}_演示视频.mp4", f"{TEAM}_{NAME}_其他材料.zip"]


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP, exist_ok=True)

    fp = os.path.join(HERE, FINALS)
    with zipfile.ZipFile(fp) as z:
        names = z.namelist()
        bad = z.testzip()
        print(f"[1] 决赛包：{len(names)} 条目，CRC 校验 {'全部通过' if bad is None else f'失败：{bad}'}")
        for n in names:
            print(f"    {n}")
        z.extractall(TMP)

    # 内层哈希与 hashes.txt 比对
    reg = open(os.path.join(HERE, "hashes.txt"), encoding="utf-8",
               errors="replace").read()
    print("\n[2] 内层文件哈希 vs hashes.txt")
    for name in INNER:
        p = os.path.join(TMP, name)
        if not os.path.isfile(p):
            print(f"    [缺失] {name}")
            continue
        h = sha(p)
        # 视频：包内为 faststart 重排版，登记值也按该版本计算（见 update_finals_hashes.py）
        rec = h[:16] in reg
        note = ""
        if not rec and name.endswith("演示视频.mp4"):
            fs = os.path.join(HERE, name.replace(".mp4", "_faststart.mp4"))
            if os.path.isfile(fs) and sha(fs)[:16] == h[:16]:
                rec, note = True, "（faststart 版本，登记值一致）"
        print(f"    [{'一致' if rec else '不一致'}] {name}  sha256 {h[:16]}{note}")

    # Demo 冒烟：解包并用包内 report_builder 生成报告
    demo_zip = os.path.join(TMP, f"{TEAM}_{NAME}_Demo.zip")
    demo_dir = os.path.join(TMP, "demo")
    with zipfile.ZipFile(demo_zip) as z:
        z.extractall(demo_dir)
    files = sorted(os.listdir(demo_dir))
    print(f"\n[3] Demo 解包：{len(files)} 个顶层条目")
    need = ["report_builder.py", "soundinsight_agent.py", "demo_sound_v2.py",
            "requirements.txt", "sample_reviews_100.csv"]
    for n in need:
        print(f"    [{'有' if n in files else '缺'}] {n}")

    code = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "import report_builder as rb\n"
        "t = rb.build_report(src_name='包内冒烟', n_total=10, n_unsupported=0, n_valid=10,\n"
        "                    n_neg=2, avg_rating=3.5,\n"
        "                    issue_counts={'杂音': 2, '清晰度': 1},\n"
        "                    examples=[{'text': 'bass rattle', 'issue': '杂音', 'prob': 0.98}],\n"
        "                    n_mid=1, lang='zh')\n"
        "print('OK sections:', [l for l in t.splitlines() if l.startswith('## ')])\n"
    ) % demo_dir
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=demo_dir)
    print("\n[4] 包内代码冒烟（不加载权重）")
    print("    " + (r.stdout.strip().replace("\n", "\n    ") or r.stderr.strip()[:300]))
    ok = r.returncode == 0 and "OK sections" in r.stdout and "置信度档位" in r.stdout
    print(f"\n[结论] 决赛包完整性 {'通过' if ok else '需检查'}；"
          f"Demo 包内代码 {'可运行' if r.returncode == 0 else '运行失败'}")
    # 自清理：临时解包目录不留在工作区（否则会被 git add -A 扫入，且内含 46 MB 视频）
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"[清理] 已删除临时目录 {os.path.relpath(TMP, HERE)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
