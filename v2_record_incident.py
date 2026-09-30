# -*- coding: utf-8 -*-
"""登记安全事件与 E7 守卫（一次性，修正引号问题）。"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

P = "docs/frozen_execution_checklist.md"
s = open(P, encoding="utf-8").read()

anchor = "| **E6** ✅ 2026-09-30 | **术语与自述换代** |"
row = ("| **E7** ✅ 2026-09-30（**事故后新增**） | **提交前守卫** | `precommit_guard.py`：对暂存区检查"
       "① 凭据模式（sk- 系列／云 AccessKey／私钥头／硬编码密钥赋值）、② 敏感文件名"
       "（`*Token Plan*`／`*信件*`／`.env`／`.key`／`.pem`／`credential`）、③ **新入库**文件 >5 MB；"
       "命中即退出码 1 阻止提交。**起因**：执行方用 `git add -A` 误入库真实 Token Plan 密钥与 267 MB 权重。"
       "用法：每次 `git add` 后、`commit` 前运行 | 执行方 | — |\n")
if "| **E7**" not in s and anchor in s:
    i = s.find(anchor)
    j = s.find("\n", i) + 1
    s = s[:j] + row + s[j:]
    print("  [增] E7 提交前守卫")

marker = "### A-尽力（超时即弃"
incident = (
    "> **🔴 安全事件记录（2026-09-30，已处置）**\n"
    "> 执行方以 `git add -A` 一次扫入两个不该入库的对象并推到远端：\n"
    "> ① `docs/百炼Token Plan 信件原文.txt` —— 含**真实 Token Plan API Key**；\n"
    "> ② `v2/model_maxlen256/model.safetensors` —— **267 MB** 权重。\n"
    "> **处置**：文件移出仓库（信件保留在工作区根目录，供收尾存证）+ `.gitignore` 加规则；"
    "`git filter-branch` 两轮（index-filter 删文件、tree-filter 掩码旧报告内逐字打印的密钥）；"
    "删除 `refs/original/*` 与陈旧远端跟踪引用后 `gc --prune=now`；强推两远端。\n"
    "> **验证**：密钥 0（历史 0）；全历史提交 grep `sk-` 系列密钥命中 **0**；267 MB 对象消失"
    "（pack 406 MB → 171 MB）。\n"
    "> **遗留动作（不可省）**：**该密钥必须视为已泄露并轮换**——它曾在 GitCode/GitHub 历史中存在。\n"
    "> **防复发**：新增 **E7**（`precommit_guard.py`），并把「扫描报告须掩码打印密钥」写入扫描器"
    "（`mask_secret`），避免卫生报告自身成为泄露源。\n\n")
if "🔴 安全事件记录" not in s and marker in s:
    s = s.replace(marker, incident + marker, 1)
    print("  [增] 安全事件记录")
open(P, "w", encoding="utf-8").write(s)

Q = "PROGRESS_SYNC.md"
t = open(Q, encoding="utf-8").read()
add = """## 🔴 安全事件与 W1 结论（2026-09-30 深夜）

- **安全事件（已处置，遗留轮换动作）**：执行方用 `git add -A` 误入库 ① 含**真实 Token Plan 密钥**的信件原文、② **267 MB** 模型权重，并推到远端。处置：移出仓库 + `.gitignore` + `filter-branch`（删文件 + 掩码旧报告中逐字打印的密钥）+ 清 `refs/original/*` 与陈旧远端跟踪引用 + `gc --prune=now` + 强推。**验证：密钥 0（历史 0）、全历史 grep 命中 0、267 MB 对象消失（pack 406→171 MB）**。**需决策方执行：轮换该密钥**（曾在远端历史中存在，一律视为已泄露）。防复发：新增 `precommit_guard.py`（E7）与扫描器掩码。
- **W1 对等对比（无泄漏留出集 val_v3_test，n=10,000／正例 128）**：

| 变体 | 整体 F1@0.5 | ≤64 token 桶 | 65–128 桶 | **>128 token 桶（截断桶）** |
|---|---|---|---|---|
| `max_len=128` | 0.7077（P 69.7／R 71.9） | 0.7523／R 83.7% | 0.7792／R 78.9% | **0.5676／R 51.2%** |
| `max_len=256` | **0.7206**（P 74.8／R 69.5） | 0.7664／R 83.7% | 0.7826／R 71.1% | **0.5915／R 51.2%** |

  - **结论**：放宽到 256 只带来整体 +0.013，**截断桶召回完全未变（51.2%，TP21/FN20 两者一致）**；原因是长文本不止 256：实测 **129–256 占 11.7%、257–512 占 5.5%、>512 占 2.1%**，超长部分中 **39.3% 超过 256 token**（P95=333、P99=694、最长 3,509）。
  - **下一步**：W1 走**变体 B（512）**或**变体 C/D（切窗/分段聚合推理）**；截断桶召回验收线 ≥70% 目前**未达**。
- **D7 与守卫**：`check_doc_numbers.py` 的 D7 检查首次运行抓出 2 处（均已修）；`precommit_guard.py` 自检即抓出卫生报告中的密钥泄露点，随后扫描器加掩码。

"""
if "🔴 安全事件与 W1 结论" not in t:
    i = t.find("## 待办（触发式，未触发前不执行）")
    t = t[:i] + add + t[i:]
    open(Q, "w", encoding="utf-8").write(t)
    print("  [增] PROGRESS_SYNC 事故与 W1 结论")
print("完成")
