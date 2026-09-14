# -*- coding: utf-8 -*-
# _which_zip.py —— 确认待提交的 zip 归属与内容（临时）
import hashlib
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PROJ = r"C:\deepseek-harness-master\soundinsight"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


print("=== 1) 全盘搜索同名/近名 zip（排除已确认的项目目录）===")
roots = [r"C:\deepseek-harness-master", r"C:\Users\19355\Desktop",
         r"C:\Users\19355\Downloads", r"C:\Users\19355\Documents",
         r"C:\Users\19355", r"F:\\"]
found = []
for root in roots:
    if not os.path.isdir(root):
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in {"node_modules", ".git", "AppData", "$RECYCLE.BIN",
                                    "System Volume Information", "Windows"}]
        for fn in filenames:
            if "复赛作品" in fn and fn.lower().endswith(".zip"):
                p = os.path.join(dirpath, fn)
                try:
                    st = os.stat(p)
                    found.append((p, st.st_size, st.st_mtime))
                except OSError:
                    pass
for p, size, mtime in sorted(found):
    tag = "  ← 项目目录内的提交包" if os.path.dirname(p) == PROJ else ""
    print(f"{size:>12,} B  {__import__('time').strftime('%Y-%m-%d %H:%M', __import__('time').localtime(mtime))}"
          f"  sha256:{sha(p)[:16]}  {p}{tag}")

print("\n=== 2) 项目目录里的四项提交物 ===")
for fn in sorted(os.listdir(PROJ)):
    if fn.startswith("更新世界的锋芒_SoundInsight") and \
       fn.lower().endswith((".zip", ".pdf", ".docx", ".mp4")):
        p = os.path.join(PROJ, fn)
        print(f"{os.path.getsize(p):>12,} B  sha256:{sha(p)[:16]}  {fn}")

print("\n=== 3) 包内 PDF 的标题页文本（确认是这个项目/团队）===")
Z = os.path.join(PROJ, "更新世界的锋芒_SoundInsight_复赛作品.zip")
with zipfile.ZipFile(Z) as z:
    pdf = z.read("更新世界的锋芒_SoundInsight_复赛作品.pdf")
tmp = os.path.join(PROJ, "_title_probe.pdf")
open(tmp, "wb").write(pdf)
try:
    import pypdf
    t = (pypdf.PdfReader(tmp).pages[0].extract_text() or "")
    print(" ".join(t.split())[:400])
finally:
    os.remove(tmp)

print("\n=== 4) 包内 Demo.zip 与视频是否为本项目产物 ===")
with zipfile.ZipFile(Z) as z:
    demo = z.read("更新世界的锋芒_SoundInsight_Demo.zip")
dtmp = os.path.join(PROJ, "_demo_probe.zip")
open(dtmp, "wb").write(demo)
with zipfile.ZipFile(dtmp) as dz:
    names = dz.namelist()
print("Demo 文件数:", len(names))
print("含本项目核心文件:",
      all(any(n.endswith(x) for n in names)
          for x in ("demo_sound_v2.py", "soundinsight_agent.py", "report_builder.py")))
os.remove(dtmp)
