# -*- coding: utf-8 -*-
"""历史清除：从全部提交中移除误入的凭证文件与模型权重（一次性）。

背景（2026-09-30）：执行方用 `git add -A` 扫入了两个本不该入库的对象：
  1. `docs/百炼Token Plan 信件原文.txt`（含真实 Token Plan API Key）——**已推到两远端**；
  2. `v2/model_maxlen256/`（含 267MB `model.safetensors`）——仅本地提交，未推送成功。
处理：先取消跟踪 + 加 .gitignore（已做），再用 `git filter-branch` 从**全部历史**中删除，
      然后强推两远端并清理本地对象。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GIT = r"C:\Program Files\Git\cmd\git.exe"
PATHS = ["docs/*Token Plan*", "v2/model_maxlen256", "v2/model_maxlen128"]


def run(args, **kw):
    r = subprocess.run([GIT] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=os.getcwd(), **kw)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


print("== 1) 提交当前的取消跟踪（先让工作树干净）==")
rc, out = run(["commit", "-m",
               "安全修复：取消跟踪误入的凭据文件与模型权重，并加 .gitignore 规则\n\n"
               "- docs/百炼Token Plan 信件原文.txt（含真实 API Key）→ 移出仓库（保留在工作区根目录，供收尾存证使用）\n"
               "- v2/model_maxlen256/（267MB 权重）→ 不入库，改为按 SHA256 登记（v2/README.md 的 weight_availability 策略）\n"
               "- .gitignore 追加：v2/model_*/、*.safetensors、*Token Plan*、*信件原文*、*.env、*.key、*.pem\n"
               "- 后续将以 filter-branch 从历史中彻底删除这两者，并强推两远端"])
print(out.strip()[-400:])

print("\n== 2) filter-branch 从全部历史删除 ==")
flt = "git rm -r --cached --ignore-unmatch " + " ".join(f"'{p}'" for p in PATHS)
env = dict(os.environ, FILTER_BRANCH_SQUELCH_WARNING="1")
r = subprocess.run([GIT, "filter-branch", "-f", "--index-filter", flt,
                    "--prune-empty", "--", "--all"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=os.getcwd(), env=env)
print(((r.stdout or "") + (r.stderr or "")).strip()[-800:])

print("\n== 3) 清理本地对象与引用 ==")
for args in (["update-ref", "-d", "refs/original/refs/heads/main"],
             ["reflog", "expire", "--expire=now", "--all"],
             ["gc", "--prune=now", "--quiet"]):
    rc, out = run(args)
    print(f"  git {' '.join(args)} → rc={rc} {out.strip()[:120]}")

print("\n== 4) 校验：历史中是否还能找到这两者 ==")
rc, out = run(["log", "--all", "--oneline", "--", "docs/*Token Plan*",
               "v2/model_maxlen256", "v2/model_maxlen128"])
print("  路径命中：", out.strip() or "（无，已清除）")
rc, out = run(["rev-list", "--objects", "--all"])
leak = [l for l in out.splitlines() if "safetensors" in l or "Token Plan" in l]
print("  对象命中：", leak[:3] or "（无，已清除）")
rc, out = run(["count-objects", "-vH"])
print("  仓库体积：", [l for l in out.splitlines() if l.startswith("size-pack")])
