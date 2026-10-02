# -*- coding: utf-8 -*-
"""生成 `docs/PAUSE_SNAPSHOT.md`（停工/恢复快照）——**每次刷新都反映当前状态**，避免漂移。

红队 SPIKE-3/4：手写快照会随提交漂移（曾记 HEAD 落后 5 个提交、工作区状态已不成立），
且静默跳过已废止的 D-Q6。改为生成式：状态由 git/文件实时算，队列逐项列出含废止状态。
用法：python make_pause_snapshot.py
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GIT = r"C:\Program Files\Git\cmd\git.exe"
FINALS = "更新世界的锋芒_SoundInsight_决赛入围定稿作品.zip"
RECAP = "更新世界的锋芒_SoundInsight_复赛作品.zip"


def sh(*a):
    return subprocess.run([GIT, *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=HERE).stdout.strip()


audit = open(os.path.join(HERE, "number_audit.md"), encoding="utf-8", errors="replace").read()
head = sh("rev-parse", "--short", "HEAD")
commits = sh("rev-list", "--count", "HEAD")
pending = sh("rev-list", "--count", "gitcode/main..HEAD")
dirty = len(sh("status", "--porcelain").splitlines())
lock_commits = sh("rev-list", "--count", "--since=2026-09-30 16:33", "HEAD")
fsize = os.path.getsize(os.path.join(HERE, FINALS))
with zipfile.ZipFile(os.path.join(HERE, FINALS)) as z:
    n_entries = len(z.namelist())
rsha = hashlib.sha256(open(os.path.join(HERE, RECAP), "rb").read()).hexdigest()[:16]
# 推送记录（每日一次，见执行纪律 R29）
try:
    _pl = json.load(open(os.path.join(HERE, "v2", "push_log.json"), encoding="utf-8"))
    _ls = _pl.get("last_success") or {}
    last_push = "｜".join(f"{k} {v.get('at','—')}" for k, v in _ls.items()) or "—（尚无记录）"
except (OSError, ValueError):
    last_push = "—（无 push_log.json）"
queue = [
    ("**R-1**", "**提供 Token Plan key**（我即跑跨模型判定 300 条，约 $0.01）", "**待决策方**"),
    ("**R-2**", "**确认 3-a 是否即刻执行**（五类归因只改表述，20 分钟、零风险）", "**待决策方一句话**"),
    ("R-3", "防护 P1（样例报告回归）／P3（回调级测试）／P2（最小公共模块抽取）", "已批准，执行方续做"),
    ("R-4", "人工金标 300 条（判别由决策方本人；`gold_set_helper.py` 已备）", "待决策方 1.5–3 h"),
    ("D-Q2", "treble 评测分辨率修复（测试集该类仅 10 条正例）", "待决策方"),
    ("D-Q3", "V1.6 更正提案落地（W11 加注／outside_gate_fp 加前提／附录 B 标 LLM 口径）", "待决策方"),
    ("D-Q4", "视频是否重录", "待决策方"),
    ("D-Q5", "M1 主文档人工复核", "待决策方"),
    ("D-Q6", "N 线外部顾问复核", "**已废止**"),
    ("D-Q7", "路演 PPT（若进 6 强；须用 `docs/ppt_claims_erratum.md` 的更正表述）", "待决策方"),
    ("—", "正式提交（10/8）", "人侧动作"),
]
rows = "\n".join(f"| {i} | {t} | {s} |" for i, t, s in queue)
snap = f"""# 停工快照（生成式，勿手改）

> **生成时刻**：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> **用途**：停工期结束后照本文件无损恢复；亦用于确认停工期间无漂移。
> **本文件由 `python make_pause_snapshot.py` 生成**（红队 SPIKE-3：手写版曾落后 5 个提交）。

## 一、冻结状态（实时）

| 项 | 值 |
|---|---|
| 本地 HEAD | `{head}`（累计 {commits} 个提交；范围冻结后 {lock_commits} 个） |
| 远端同步 | GitCode / GitHub｜**待推送 {pending}**（推送**每天一次**，见 R29） |
| 上次成功推送 | {last_push} |
| 工作区 | {"**干净**" if dirty == 0 else f"有 {dirty} 项未提交改动"} |
| 决赛包 | {n_entries} 条目｜体积 {fsize:,} B（**随重建变化，以 `hashes.txt` 决赛段为准**） |
| 复赛包（红线 9） | sha256 `{rsha}…`（冻结值 `e6cae286515ef1d2`） |
| 审计 | FAIL {audit.count('[FAIL]')}／PASS {audit.count('[PASS]')}／SKIP {audit.count('[SKIP]')} |
| 清单版本 | v1.5 |

## 二、恢复命令（三步，约 7 分钟）

```powershell
cd <repo-root>（本机为 C:/deepseek-harness-master/soundinsight）
git pull                      # 换机器时
python run_all_checks.py      # 13 步门槛链；全绿即与停工前一致
python make_reviewer_brief.py # 刷新给外部的状态卡（含本快照）
```

## 三、停工期间不该发生的事（防漂移）

1. 不要手工编辑清单、`build_*.py`、`check_doc_numbers.py`（互相咬合）；
2. 不要改 `v2/threshold.json`、`v2/model_maxlen256/`、`val_v3_test.csv`（冻结口径）；
3. 不要手工重打包——只走 `python build_finals_package.py`（含红线 9 核对）；
4. 新数字必须当场配机械检查或标"未校准"。

## 四、未决事项（逐项列出，含已废止项）

| ID | 事项 | 状态 |
|---|---|---|
{rows}

> 队列全文：`docs/decision_queue.md`｜进展全文：`docs/progress_report_current.md`
> 给外部审阅者：`docs/REVIEWER_BRIEF.md`

## 五、对外数字（照抄，勿重算）

> **口径限定（必读）**：以下 `val_v3_test` 指标测的是「**关键词可达 × 已复核星级**」子集内的表现（附录 B 第 8 条：该测试集 128 条正例 100% 含一阶关键词；闸门外 86.9% 语料在构造上不可能成为正例）。
> 故这些数字**不代表全语料表现**；引用时必须连本限定一起引用。

- 主指标（`val_v3_test`）：F1@调优(0.6) **0.7220**｜F1@0.5 **0.7206**｜PR-AUC **0.7811**
- **两代不可比、且不主张 v2 优于 v1**：同基准 v1 **0.7759**（CI 0.721–0.826）vs v2 **0.7220**（0.655–0.786）
- 归因：宏 F1 **0.8273**（逐类阈值）／统一 0.5 档 **0.7180**；高音 **0.5333**／**0.0000**
- CV：无偏 **0.6584±0.0378（5.7%）**
- 覆盖（**LLM 口径，未经人工校准**）：成对 **2,461（52.0%）／2,826（45.3%）**
- 三项未达标：长文本约束式分档 **68.3%<70%**、CV 波动 **5.7%>5%**、闸门第 (3) 条部分未达
"""
open(os.path.join(HERE, "docs", "PAUSE_SNAPSHOT.md"), "w", encoding="utf-8",
     newline="\n").write(snap)
print(f"  [生成] docs/PAUSE_SNAPSHOT.md｜HEAD {head}｜待推送 {pending}｜"
      f"工作区 {'干净' if dirty == 0 else str(dirty) + ' 项改动'}")
