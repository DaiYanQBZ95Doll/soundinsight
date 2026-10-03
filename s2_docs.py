# -*- coding: utf-8 -*-
"""S3/S4 + 落盘文档：split_manifest.md、s2c_true_holdout.md（含分层）、
extrapolation_register.md、review_coverage_table.md，以及"禁报数字"机械门。

设计要点：
  · split_manifest：全量 SHA256（禁用前缀，附碰撞实证）＋行数＋正例数＋天花板声明；
    v1 已钉；v2 标「候选输入（待佐证）」；v3-lite 待登记（含标签来源声明）。
  · 外推登记表：**取消"标注未传导"后门**——不能传导就只写"输入 CI＋仅方向性"，不写点估计。
  · 机械门 check_retracted_numbers.py：**禁报数字一旦出现在对外材料即 FAIL**；
    并校验登记表自身（有点估计却无区间 → FAIL）。
"""
from __future__ import annotations

import ast
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
man = json.load(open(os.path.join(HERE, "v2", "split_manifest.json"), encoding="utf-8"))
mem = json.load(open(os.path.join(HERE, "v2", "s2_membership.json"), encoding="utf-8"))
v1 = man["v1 训练输入"]
v1h = man["v1 真留出侧"]
v2i = man["v2 候选训练输入"]
v2t = man["v2 冻结测试集"]
v2u = man["v2 调参侧"]


def row(tag, d, status):
    return (f"| {tag} | `{d['file']}` | `{d['sha256']}` | {d['rows']:,} | {d['positives']} | "
            f"{status} |")


SPLIT_MD = f"""# 世代钉死登记（split manifest，R34）

> **规则**：每一代模型的训练输入与留出/测试集，必须在训练前登记**全量 SHA256**（64 位）＋行数＋正例数；
> 划分**只允许从登记版本复现**；已登记输入视为**冻结**，就地改写标签＝**开启新一代**。
> **前缀哈希不得用于世代判定**——实测：`labeled_llm.csv` 与 `labeled_llm_before_mid_remove.csv`
> 前 1MB 哈希**相同**（`8eef1c7e39e2`），全量哈希**不同**（`{v2i['sha256'][:16]}` vs
> `{man['另一世代(中间态)']['sha256'][:16]}`）。

## 一、登记表

| 世代 | 文件 | 全量 SHA256 | 行数 | 正例 | 状态 |
|---|---|---|---|---|---|
{row("**v1 训练输入**", v1, "**已钉死**（日志四数全中）")}
{row("**v1 真留出侧**", v1h, "**已钉死**（与复现 val 重合 19,281/19,282）")}
{row("v2 训练输入（候选）", v2i, "**候选输入（待佐证）**——须训练日志样本数或决策方确认后方可升级")}
{row("**v2 冻结测试集**", v2t, "已钉死（`v2_artifacts.json` 已登记）")}
{row("v2 调参侧", v2u, "已钉死（`v2_artifacts.json` 已登记）")}
{row("v3-lite 训练输入", v2i, "**待登记**：同一世代文件、训练侧标签经口径纠正（428 正例）；标签来源＝**分类器筛的耳机家族，非人工**")}

其它世代（**未绑定任何模型**，仅存档）：
`labeled_llm_before_mid_remove.csv`（{man['另一世代(中间态)']['positives']} 正例，`{man['另一世代(中间态)']['sha256'][:16]}`）、
`labeled_llm_before_mid_demote.csv`（{man['另一世代(中间态2)']['positives']} 正例，`{man['另一世代(中间态2)']['sha256'][:16]}`）。

## 二、复现证据（v1）

- 复现命令：`before_treble` + `train_test_split(test_size=0.2, random_state=42, stratify=标签)`；
- 日志 `exp06_最终二分类模型/train_final.log`：rows 100000｜positives 1257 → train 80000(pos 1006)｜val 20000(pos 251)；
- **复现值与日志四数全中 ✓** → v1 世代确定性可复现。

## 三、已披露的精度事实（不藏）

1. **`val_v2.csv` 与复现 val 的重合 = 19,281/19,282**（raw 与 normalized 两口径**同为** 19,281）；
   未命中的唯一文本是**字面量 `'nan'`**（4 行同文本）——**无实质差异**；
2. **`val_v2.csv` 内部重复**：20,000 行／唯一 {v1h['unique_norm']:,} → **多余行 718（3.6%）**；
   落在重复组内的行 **935（4.7%）**（两种口径都列出，避免又出现"成对数字被拆开"）；
   **重复行中正例 0** → 无正例泄漏；
3. **层面限定**：以上仅为「**精确匹配层**」结论。**模糊层（跨 ASIN 近重复）**因 10/8 紧迫列为
   **探索性项**，不得与精确层混写；"零泄漏"必须带层限定词。

## 四、天花板声明（必须与任何引用同屏出现）

**连 v2 的训练侧也只能判到「按当前文件不在 `val_v3_test`/`val_v3_tune` 内」**——
语料文件在训练时的哈希**未登记**，"确实喂进了训练"这一层对两代模型**均不可达**。
因此：凡引用某代的"训练侧/留出侧"，必须注明世代哈希；未登记世代的划分一律标「**不可复现**」。
"""
open(os.path.join(HERE, "docs", "split_manifest.md"), "w", encoding="utf-8",
     newline="\n").write(SPLIT_MD)
SPLIT_MD += """
## 五、地基刻度（**必须与任何"人工真值"引用同屏**）

本 manifest 的一切判定，其**真值来源是决策方人工判定**，而那层真值自身的一致性为：
**一致率 83.6%／κ 0.329**（口径 A，排除「无法判断」）或 **82.0%／κ 0.288**（口径 B，记为负）；
**S2 层 κ 为负**。按项目分级仅属「**一般**」。

**含义**：κ 0.33 的人工真值**远强于** κ 0.845 的 LLM 自一致假象（后者是"一起错"），
但**不是铁**——凡引用"人工真值/真实场景"，须带上这个刻度，否则三个月后无人记得 0.33。
"""
print("  [写出] docs/split_manifest.md")

# ---------------- S2c 文档（含分层与真实场景子集） ----------------
c = mem["s2c"]
per = c["per_stratum"]
rw = c.get("realworld_subset", {})
lines = ["# S2c：v1 真留出侧（`val_v2.csv`）上的人工真值口径", "",
         f"> 世代：`{v1['file']}`（`{v1['sha256'][:16]}…`）＋真留出侧 `{v1h['file']}`"
         f"（`{v1h['sha256'][:16]}…`）｜**内容哈希**判定（非 row_index）", "",
         f"**落入条目 {c['n_total']}｜可比对 {c['n_comparable']}｜正例 {c['n_positives']}｜"
         f"「无法判断」{c['n_unclear']}**", "",
         "分层构成：" + "｜".join(f"{k} {v}" for k, v in sorted(c["by_stratum"].items())), "",
         "## 一、混合口径（**不得单独引用**）", "",
         "| 模型 | 自带阈值 | 命中 | 命中率 | 95% CI |",
         "|---|---|---|---|---|"]
for name, r in c["models"].items():
    lines.append(f"| {name} | {r['thr_own']} | **{r['hits_own_thr']}/{r['positives']}** | "
                 f"{r['hit_rate_own_thr']:.3f} | {r['hit_rate_ci'][0]}–{r['hit_rate_ci'][1]} |")
lines += ["", "**CI 大幅重叠 → 按 R7 不可主张 v1/v2 优劣。**", "",
          "## 二、分层（**必须同屏**：混合口径的命中几乎全部来自同源层）"]
hdr = ["| 层 | n | 正例 | v1 命中 | v1 告警 | v2 命中 | v2 告警 | 性质 |",
       "|---|---|---|---|---|---|---|---|"]
for st, label in (("S1", "S1 闸门外随机"), ("S2", "S2 四五星池"), ("S3", "S3 已标注集"),
                  ("S4", "S4 闸门外追加"), ("S5", "S5 干净探针")):
    a = per.get("v1（出厂）", {}).get(st, {})
    b = per.get("v2（候选）", {}).get(st, {})
    if not a:
        continue
    nat = {"S1": "**真实场景**", "S2": "候选池", "S3": "**同源（循环）**",
           "S4": "**真实场景**", "S5": "**真实场景**"}[st]
    hdr.append(f"| {label} | {a['n']} | {a['positives']} | {a['hits']} | {a['alerts']} | "
               f"{b.get('hits', '—')} | {b.get('alerts', '—')} | {nat} |")
lines = lines[:-1] + hdr + ["", "## 三、真实场景子集（S1+S4+S5，**唯一可称真实场景者**）", "",
                            "| 模型 | n | 正例 | 命中 | 命中率 | 95% CI |",
                            "|---|---|---|---|---|---|"]
for name, r in rw.items():
    lines.append(f"| {name} | {r['n']} | {r['positives']} | **{r['hits']}** | "
                 f"{r['hit_rate']:.3f} | {r['hit_rate_ci'][0]}–{r['hit_rate_ci'][1]} |")
lines += ["", "## 四、判读限制（预注册，不得违反）", "",
          "- n=109／正例 8，**未达可断言样本量**：**仅报命中计数与区间，不做方向性归因**；",
          "- **不得**写作「v1 真实场景 F1 ≈ X」或类似表述；",
          "- 混合口径的数字**必须与分层表同屏**引用，否则读者会把 S3（同源）的命中读成真实能力；",
          "- 归档位置：**附录探索性数字**——不进正文、不进摘要、不进状态卡。"]
open(os.path.join(HERE, "docs", "s2c_true_holdout.md"), "w", encoding="utf-8",
     newline="\n").write("\n".join(lines) + "\n")
print("  [写出] docs/s2c_true_holdout.md（含分层与真实场景子集）")
