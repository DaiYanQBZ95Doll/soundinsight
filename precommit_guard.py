# -*- coding: utf-8 -*-
"""提交前守卫（E7）：拦住"不该入库的东西"和"过大的文件"。

## 为什么需要（事故记录，2026-09-30）

执行方用 `git add -A` 一次扫入了两个本不该入库的对象，并已推到远端：

  1. `docs/百炼Token Plan 信件原文.txt` —— 含**真实 Token Plan API Key**（红线：凭证绝不入库）；
  2. `v2/model_maxlen256/model.safetensors` —— **267 MB** 权重（约定：权重按 SHA256 登记，不入库）。

两者都已用 `git filter-branch` 从历史清除并强推，但**凭据必须视为已泄露并轮换**。
根因是"人工记得检查"不可靠，故把检查机械化：本守卫在 `git add` 之后、`commit` 之前运行，
对**暂存区**做三类检查，任一命中即退出码 1 并列出处置建议。

## 用法

    python precommit_guard.py            # 检查暂存区（推荐：每次 commit 前）
    python precommit_guard.py --all      # 检查工作区全部未忽略文件（更严）

## 检查项

  A. 凭据模式：`sk-` 系列密钥、`AKIA`/`LTAI` 云密钥、私钥头、`api_key=…` 赋值；
  B. 敏感文件名：`*Token Plan*`、`*信件*`、`*.env`、`*.key`、`*.pem`、`*credential*`；
  C. 体积：单个暂存文件 > 5 MB（权重/大 CSV 应走登记而非入库）。

> 守卫只做"拦截并要求人工判断"，不自动修改任何文件；确需入库时按提示改走
> `v2/README.md` 的 `weight_availability` 登记或 `docs/legacy_materials_notice.md` 的凭据规则。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAX_MB = 5.0
SECRET_PATTERNS = (
    (re.compile(r"sk-[A-Za-z0-9._\-]{24,}"), "sk- 系列 API 密钥"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS Access Key"),
    (re.compile(r"\bLTAI[0-9A-Za-z]{12,}\b"), "阿里云 AccessKey"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "私钥文件内容"),
    (re.compile(r"(?i)\b(?:api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{16,}"),
     "疑似硬编码密钥赋值"),
)
# 说明：`credential|secret` 只对数据/配置类扩展名生效——仓库里有**关于**凭据的 .md 文档
# （如 docs/llm_credential_status.md），那类文档必须允许入库。
BAD_NAME = re.compile(
    r"(?i)(token plan|信件|记得删|提醒|便签|"
    r"(?:credential|secret)[^/]*\.(?:json|ya?ml|txt|ini|cfg|env|key|pem)$|"
    r"\.env$|\.key$|\.pem$)")
SKIP_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".docx", ".pptx",
            ".mp4", ".zip", ".safetensors", ".bin", ".pt", ".onnx")


def git(*args: str) -> str:
    r = subprocess.run([r"C:\Program Files\Git\cmd\git.exe", *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=os.path.dirname(os.path.abspath(__file__)))
    return (r.stdout or "") + (r.stderr or "")


def targets(scan_all: bool) -> list[str]:
    if scan_all:
        out = git("-c", "core.quotepath=false", "ls-files", "--cached", "--others",
                  "--exclude-standard")
    else:
        out = git("-c", "core.quotepath=false", "diff", "--cached", "--name-only",
                  "--diff-filter=ACM")
    return [l.strip().strip('"') for l in out.splitlines() if l.strip()]


def tracked_in_head() -> set[str]:
    """已在 HEAD 中的文件：体积检查只针对"新入库"的文件（既有数据文件属历史既成事实）。"""
    out = git("-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", "HEAD")
    return {l.strip().strip('"') for l in out.splitlines() if l.strip()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="检查全部未忽略文件（更严）")
    args = ap.parse_args()

    files = targets(args.all)
    if not files:
        print("[守卫] 暂存区为空，无待检查文件")
        return 0
    already = tracked_in_head()

    problems: list[str] = []
    for f in files:
        if BAD_NAME.search(os.path.basename(f)):
            problems.append(f"A/B 敏感文件名：{f}")
        if not os.path.isfile(f):
            continue
        size_mb = os.path.getsize(f) / 1024 / 1024
        # 体积只拦"新入库"（既有跟踪文件不重复报警），阈值 5 MB
        if size_mb > MAX_MB and f not in already:
            problems.append(f"C 体积过大（新入库）：{f}（{size_mb:.1f} MB > {MAX_MB} MB）")
        if f.lower().endswith(SKIP_EXT) or size_mb > 20:
            continue
        try:
            text = open(f, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for pat, what in SECRET_PATTERNS:
            if pat.search(text):
                problems.append(f"A 疑似凭据（{what}）：{f}")
                break

    print(f"[守卫] 检查 {len(files)} 个文件"
          f"（{'全量未忽略' if args.all else '暂存区'}）")
    if not problems:
        print("[守卫] PASS：未发现凭据、敏感文件名或超大文件")
        return 0
    print(f"[守卫] FAIL：{len(problems)} 处需人工判断 —— 已阻止提交")
    for p in problems:
        print(f"    - {p}")
    print("\n处置建议：")
    print("  · 凭据类：从工作树移出仓库（凭证绝不入库），并**轮换该凭证**；"
          "如已提交，需 filter-branch 清史 + 强推")
    print("  · 权重类：不入库，改为按 SHA256 登记（见 v2/README.md 的 weight_availability）")
    print("  · 确需入库的超大文件：先与决策方确认，并更新上限")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
