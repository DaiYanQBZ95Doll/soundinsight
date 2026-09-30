# -*- coding: utf-8 -*-
"""一键刷新两份样例报告并**自动补回口径说明**（幂等）。

为什么需要：`soundinsight_agent.py` 重生成样例时会**覆盖**手工添加的说明行；
每次单独重生成都会丢掉说明（本轮已发生两次）。本脚本把两步固化：
   ① 用产品当前代码重生成中文/英文样例；
   ② 若样例缺少口径说明，则补回。
用法：python refresh_samples.py
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
NOTE_ZH = ("> **样例说明**：本样例由**产品默认模型（v1 冻结权重）**生成，因此报告内指标为 v1 口径"
           "（验证集 F1 0.687、阈值 0.9744）；决赛主文档中的 v2 指标（`val_v3_test` 上 "
           "F1@调优(0.6) = 0.7220）来自 **v2 候选模型**，两者样本集不同、**不可直比**。"
           "模型调用边界见 README「模型调用与边界」段。\n\n")
NOTE_EN = ("> **Sample note**: this sample was produced by the **shipped default model (frozen v1 weights)**, "
           "so the metrics shown are v1-generation (validation F1 0.687, threshold 0.9744). The v2 metrics in "
           "the finals main document (F1@tuned(0.6) = 0.7220 on `val_v3_test`) come from the **v2 candidate "
           "model**; the two use different sample sets and are **not directly comparable**.\n\n")


def regenerate(lang: str) -> None:
    cmd = [sys.executable, "soundinsight_agent.py", "--csv", "sample_reviews_100.csv"]
    if lang == "en":
        cmd += ["--lang", "en"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=HERE)
    print(f"  [重生成 {lang}] 退出码 {p.returncode}")


def add_note(path: str, note: str, key: str) -> None:
    if not os.path.isfile(path):
        print(f"  [跳过] {path} 不存在")
        return
    t = open(path, encoding="utf-8").read()
    if key in t:
        print(f"  [跳过] {path} 已含说明")
        return
    lines = t.splitlines(keepends=True)
    open(path, "w", encoding="utf-8", newline="\n").write(
        lines[0] + "\n" + note + "".join(lines[1:]))
    print(f"  [补注] {path}（现 {len(open(path, encoding='utf-8').read())} 字符）")


if __name__ == "__main__":
    regenerate("zh")
    regenerate("en")
    add_note(os.path.join(HERE, "insight_report_v2.md"), NOTE_ZH, "样例说明")
    add_note(os.path.join(HERE, "insight_report_v2_en.md"), NOTE_EN, "Sample note")
    # 校验两份样例均为七节且无标签污染
    for f in ("insight_report_v2.md", "insight_report_v2_en.md"):
        t = open(os.path.join(HERE, f), encoding="utf-8").read()
        secs = sum(1 for l in t.splitlines() if l.startswith("## "))
        print(f"  [校验] {f}：{secs} 节｜标签污染 {'有' if '[v1]' in t else '无'}")
