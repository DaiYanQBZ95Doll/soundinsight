# -*- coding: utf-8 -*-
"""刷新 `docs/REVIEWER_BRIEF.md` 的状态卡（§2），并输出不可变 SHA 链接表。

只改 STATE-CARD 标记之间的内容，正文不动——避免"文档与仓库状态漂移"（红队第四轮的教训）。

用法：python make_reviewer_brief.py [--links]
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "docs", "REVIEWER_BRIEF.md")
GIT = r"C:\Program Files\Git\cmd\git.exe"
FINALS = "更新世界的锋芒_SoundInsight_决赛入围定稿作品.zip"
RECAP = "更新世界的锋芒_SoundInsight_复赛作品.zip"
BEGIN, END = "<!-- STATE-CARD:BEGIN -->", "<!-- STATE-CARD:END -->"
KEY_FILES = [
    "docs/REVIEWER_BRIEF.md", "results_summary.md", "docs/three_stage_comparison.md",
    "docs/progress_report_current.md", "docs/scoped_findings.md", "docs/b_measure_results.md",
    "docs/decision_queue.md", "docs/human_gold_set_protocol.md",
    "docs/frozen_execution_checklist.md", "docs/v2_gate_verdict.md",
    "docs/PAUSE_SNAPSHOT.md", "PROGRESS_SYNC.md", "hashes.txt",
]


def sh(*a):
    return subprocess.run([GIT, *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=HERE).stdout.strip()


def main() -> int:
    sha = sh("rev-parse", "HEAD")
    short = sha[:7]
    pending = sh("rev-list", "--count", "gitcode/main..HEAD")
    dirty = len(sh("status", "--porcelain").splitlines())
    commits = sh("rev-list", "--count", "HEAD")
    audit = open(os.path.join(HERE, "number_audit.md"), encoding="utf-8",
                 errors="replace").read()
    stamp = [l for l in audit.splitlines() if "运行时刻" in l]
    hyg = open(os.path.join(HERE, "docs", "repo_hygiene_scan.md"), encoding="utf-8",
               errors="replace").read()
    hyg_line = next((l.strip() for l in hyg.splitlines() if "密钥" in l and "[PASS]" in l),
                    "（未找到卫生结论行）")
    fsize = os.path.getsize(os.path.join(HERE, FINALS)) if os.path.isfile(FINALS) else 0
    with zipfile.ZipFile(os.path.join(HERE, FINALS)) as z:
        n_entries = len(z.namelist())
    rsha = hashlib.sha256(open(os.path.join(HERE, RECAP), "rb").read()).hexdigest()[:16] \
        if os.path.isfile(RECAP) else "（缺失）"
    self_test = subprocess.run([sys.executable, "test_audit_checks.py"], capture_output=True,
                               text=True, encoding="utf-8", errors="replace",
                               cwd=HERE).stdout.strip().splitlines()
    self_line = self_test[-1] if self_test else "（自测未运行）"

    card = f"""| 项 | 值 |
|---|---|
| 生成时刻 | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| 本地 HEAD | `{short}`（{commits} 个提交；工作区{"干净" if dirty == 0 else f"有 {dirty} 项改动"}；待推送 {pending}） |
| 清单版本 | **v1.5**（`docs/checklist_version.json`） |
| 数字审计 | FAIL {audit.count('[FAIL]')}／PASS {audit.count('[PASS]')}／SKIP {audit.count('[SKIP]')}（{stamp[0][2:30] if stamp else '无时刻'}） |
| 负向自测 | {self_line} |
| 卫生扫描 | {hyg_line[2:90]} |
| 决赛包 | {n_entries} 条目｜体积 {fsize:,} B（**随重建变化，以 `hashes.txt` 决赛段为准**） |
| 复赛包（红线 9） | sha256 `{rsha}…`（应与冻结值 `e6cae286515ef1d2` 一致） |
| 一键复跑 | `python run_all_checks.py`（13 步门槛链，约 6 分钟） |

**直读链接（GitCode raw 需鉴权返回 403，故统一用 GitHub）**：

```
# ① 始终指向最新 main（拿去就能用）
https://raw.githubusercontent.com/DaiYanQBZ95Doll/soundinsight/main/docs/REVIEWER_BRIEF.md

# ② 钉死版本（把 <SHA> 换成任意提交号，用于"我审的是哪一版"）
https://raw.githubusercontent.com/DaiYanQBZ95Doll/soundinsight/<SHA>/docs/REVIEWER_BRIEF.md
```

> **注意**：本卡生成于提交 `{short}` **之前**（本文件自身的提交），因此 `{sha}` 形态的链接
> 要在该提交推送后才生效；**要立刻可用，请用上面的 ①**。
> 其他关键文件的 SHA 链接：`python make_reviewer_brief.py --links`
"""
    t = open(P, encoding="utf-8").read()
    i, j = t.find(BEGIN), t.find(END)
    assert i > 0 and j > i, "未找到 STATE-CARD 标记"
    t = t[:i + len(BEGIN)] + "\n" + card + t[j:]
    open(P, "w", encoding="utf-8", newline="\n").write(t)
    print(f"  [刷新] {os.path.relpath(P, HERE)} 状态卡｜HEAD {short}｜"
          f"审计 FAIL {audit.count('[FAIL]')}｜包 {n_entries} 条目 / {fsize:,} B")

    if "--links" in sys.argv:
        print("\n=== 关键文件不可变链接 ===")
        for f in KEY_FILES:
            if os.path.isfile(os.path.join(HERE, f)):
                print(f"  https://raw.githubusercontent.com/DaiYanQBZ95Doll/soundinsight/"
                      f"{sha}/{f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
