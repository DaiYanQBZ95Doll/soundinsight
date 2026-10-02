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
# 席位可用性（任一方短时不可用时登记；见执行纪律 R30）
try:
    _av = json.load(open(os.path.join(HERE, "docs", "bus", "availability.json"),
                         encoding="utf-8")).get("parties", {})
    avail_line = "｜".join(
        f"{k}:" + ("可用" if v.get("status") == "available" else
                   ("**不可用**" if v.get("status") == "unavailable" else "未明"))
        + (f"（至 {v['until']}）" if v.get("until") else "") for k, v in _av.items())
except (OSError, ValueError):
    avail_line = "—（无 availability.json）"
try:
    _pl = json.load(open(os.path.join(HERE, "v2", "push_log.json"), encoding="utf-8"))
    _ls = _pl.get("last_success") or {}
    last_push = "｜".join(f"{k} {v.get('at','—')}" for k, v in _ls.items()) or "—（尚无记录）"
except (OSError, ValueError):
    last_push = "—（无 push_log.json）"
queue = [
    ("**N-1**", "**V1.6 提案（现 4 项）是否批准落地**——原 2 项 + S2 结论降级 + κ 并列呈现", "**待决策方一句话**"),
    ("**N-2**", "**是否立项 v3 重训**（范围内、无闸门偏置标签；唯一能真正解决「分布外有效性」的路径，2–4 天）", "**待决策方**"),
    ("**N-3**", "**网络恢复后推送**：`python push_daily.py`（本地领先若干提交；「当日必推」会自动识别红队可见文件）", "执行方，等网络"),
    ("N-4", "红队 round-02 回复（`docs/bus/round-02/dsh.md` 的 `DSH2-R1/R2`：请 Kimi 复核事实更正、两方复核称谓检查覆盖）", "待 Kimi/Qwen"),
    ("N-5", "对外材料收尾：评审导读一页纸 / 路演稿（`docs/roadshow_slides_corrections.md` 已备更正文本）", "执行方 1–2 h"),
    ("D-Q2", "treble 评测分辨率修复（测试集该类仅 10 条正例）", "待决策方"),
    ("D-Q4", "视频是否重录（现为 v1 口径）", "待决策方"),
    ("D-Q5", "M1 主文档人工复核", "待决策方"),
    ("D-Q6", "N 线外部顾问复核", "**已废止**"),
    ("D-Q7", "路演 PPT（若进 6 强；须用更正表述并精简到 8–12 页）", "待决策方"),
    ("**已闭合**", "Token Plan key（T2 跨模型已跑：95.3%／κ 0.845）｜人工金标 500 条（含 S4/S5）｜"
     "P9 防护｜称谓一致性检查｜R32 机制化｜S5 可见性说明", "—"),
    ("—", "**正式提交（10/8 截止）**", "**人侧动作**"),
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
| 席位可用性 | {avail_line} |
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
- ⚠️ **真实场景性能（人工真值，2026-10-02 新测）**：混合样本 F1 **0.427**、精确率 **0.320**、PR-AUC **0.396**；**闸门外自然混合层召回首测 0.000**（3 条真阳一条未中）——主指标描述**分布内**表现，产品实际价值应表述为「对关键词可达评论做优先级排序」
- **两代不可比、且不主张 v2 优于 v1**：同基准 v1 **0.7759**（CI 0.721–0.826）vs v2 **0.7220**（0.655–0.786）
- 归因：宏 F1 **0.8273**（逐类阈值）／统一 0.5 档 **0.7180**；高音 **0.5333**／**0.0000**
- CV：无偏 **0.6584±0.0378（5.7%）**
- 跨模型校验（qwen3.7-plus 对同 300 条第二判定）：一致率 **95.3%**、κ **0.845**——**不等于正确**：同一批上 LLM 正例对人工精确率仅 **30.2%**（两家族共同偏离人工口径）
- 口径：已标注正例中**耳机家族约 41.4%**；真实耳机音质差评估计 **约 380–400 条**；限定耳机口径 F1@0.5 **0.6966**（**低于**全集，故不主张"收紧口径可提分"）
- 覆盖：**LLM 口径** 成对 2,461（52.0%）／2,826（45.3%）；**人工佐证口径**（n=294 人工判定）点估计 58.5%／51.5%，**95% 区间 33.0%–79.9%**（原报值落在区间内）
- 三项未达标：长文本约束式分档 **68.3%<70%**、CV 波动 **5.7%>5%**、闸门第 (3) 条部分未达
"""
open(os.path.join(HERE, "docs", "PAUSE_SNAPSHOT.md"), "w", encoding="utf-8",
     newline="\n").write(snap)
print(f"  [生成] docs/PAUSE_SNAPSHOT.md｜HEAD {head}｜待推送 {pending}｜"
      f"工作区 {'干净' if dirty == 0 else str(dirty) + ' 项改动'}")
