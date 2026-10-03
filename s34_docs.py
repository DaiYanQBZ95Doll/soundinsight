# -*- coding: utf-8 -*-
"""S3 + S4：外推登记表、复核覆盖表，以及「禁报数字」机械门。

S3 规则（红队定稿）：
  · 任一输入带抽样不确定性 ⇒ **必须传导区间**；
  · 不能传导 ⇒ **不写点估计**，只写「输入量 CI ＋ 结论强度：仅方向性」；
  · "标注未传导后点估计继续流通"这条后门**取消**。
机械门：禁报数字出现在对外材料即 FAIL；登记表自身「有点估计却无区间」也 FAIL。
"""
from __future__ import annotations

import ast
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

REG = """# 外推登记表（extrapolation register，R5 扩展）

> **规则**：任一输入带抽样不确定性 ⇒ **必须传导区间**；不能传导 ⇒ **不写点估计**，
> 只写「输入量 CI ＋ 结论强度：**仅方向性**」。
> 字段：id｜estimand（一句话）｜输入（含 CI）｜运算｜点估计｜传导后区间｜预注册编号｜
> 分析脚本哈希｜**结论强度上限**｜状态。

| id | estimand | 输入（含 CI） | 运算 | 点估计 | 传导后区间 | 预注册 | 脚本 | 结论强度上限 | 状态 |
|---|---|---|---|---|---|---|---|---|---|
| X-01 | 全语料真阳总数 | 闸门内 1,280（**精确计数**）＋闸门外 87,071×1.02%（CI 0.35–2.96%） | 加／乘 | ~~2,168~~ | 未传导 | — | `v2_coverage_math.py` | **仅方向性：闸门外真阳占比与闸门内同量级** | **撤回点估计** |
| X-02 | 模型对全部真阳的检出比例 | X-01 ＋ 闸门内召回 0.695（LLM 标签口径） | 加权比 | ~~45%~~ | 未传导 | — | 同上 | **仅方向性：检出明显低于分布内口径** | **撤回** |
| X-03 | 结构性漏检占比 | X-01 拆解 | 比 | ~~37%~~ | 未传导 | — | 同上 | **仅方向性** | **撤回** |
| X-04 | 扩词表可回收真阳数 | 814×37.5%（n=8，CI 8.1–68.4%） | 乘 | ~~305~~ | 66–557 | 待 S6 预注册 | `v2_vocab_gap.py` | **不可用于决策**（样本外＋同批拟合） | **撤回，待 S6 独立检验** |
| X-05 | 闸门外召回上界 | 告警率 0.105%（分母为构造混合池）÷ 真值率 1.02%（CI 0.35–2.96%） | 比 | ~~7–10%~~ | 按 CI 直算 3.5%–30%（**但不同总体，算式本身不成立**） | — | `v2_coverage_math.py` | **仅尺度论证：两者相差约一个数量级、各有 CI、不同总体** | **撤回** |
| X-06 | 闸门外补标预算 | 30,000 条（**设计选择**）× $0.138/千条（**实测**） | 乘 | $4.14 | 无需（输入为精确计数与实测单价，非抽样估计） | — | `v2/b_measure_results.json` | **量级可用**，但**条数选择依据须写明** | 降级：须随附条数依据 |
| X-07 | v1 留出侧真实场景 F1 | 94 条（**v2 划分**） | 比 | ~~0.381~~ | — | — | `realworld_eval_split.py` | **口径错误：非 v1 真留出侧** | **撤回** |
| X-08 | v2 同口径 F1 | 同上 | 比 | ~~0.471~~ | — | — | 同上 | 同上 | **撤回** |
| X-09 | 词表命中已知漏检 | 3 条拟合样本 | — | ~~3/3~~ | — | — | `v2_vocab_gap.py` | **同义反复，零信息量** | **撤回** |
| X-10 | 干净池告警率 | 15/14,299（**精确计数**） | 比 | 0.105% | Wilson 95% CI **0.064%–0.173%** | — | `make_clean_alerts_sheet.py` | **测量本身成立**；引用须**拆三成分**（留出侧／闸门外／未判过） | **保留（限测量）** |
| X-11 | LLM 复核单价 | 1.4096 USD ÷ 10.228 千条 | 比 | $0.1378/千条 | 无需（输入为精确计数） | — | `v2/b_measure_results.json` | **可用** | 保留 |
| X-12 | v1 世代划分可复现 | 日志四数 vs 复现值 | 对账 | 四数全中 | 无需（对账结论，非估计） | — | `s2_generation_audit.py` | **可断言「确定性可复现」** | 保留 |
| X-16 | P(真阳｜扩词表命中)（S6 独立检验，**预注册**） | 抽样框 861 条，随机 98 条人工盲判（词表先冻结 `81df7375…`） | 比 | **9/98 = 9.2%** | Wilson 95% CI **4.9%–16.5%**（CP 4.3%–16.7%） | S6 预注册（n=100，实际 98，**偏离 2% 已披露**） | `score_vocab_test.py` | **可断言：扩词表命中者约 9% 为真阳；此前 37.5% 属事后拟合，放大近 4 倍** | 保留（新测量） |
| X-17 | 扩词表可回收正例 | X-16 × 抽样框 861 | 乘 | **≈78 条** | **41–140 条**（由 X-16 的 CI 传导） | 同上 | `score_vocab_test.py` | **量级不足以把闸门外召回拉到可用**；不得据此主张召回提升 | 保留 |
| X-18 | 三模型同池干净触发对比 | 干净池 14,299 条（**与 v1 的 15 条同池**） | 比 | v1 15／v3-lite-A 1／v3-lite-B 3 条 | Wilson（n 太小，不报） | — | `fair_pool_compare.py` | **可断言：标签侧两种修法都未提升闸门外触发（反而更保守）** | 保留（新测量） |
| X-13 | 告警精确率（干净池） | 告警臂 15 条（**全部触发条目**，非抽样） | 比 | 3/15 = 20.0% | Wilson 95% CI 7.0%–45.2%（口径 B，`?` 记负）；口径 A（排除 6 条 `?`）3/9 = 33.3%（CI 12.1%–64.6%） | — | `score_clean_alerts.py` | **可断言：产品报警时约 1/3（最好）至 1/5（含 `?` 记负）为真** | 保留（新测量） |
| X-14 | 干净基线率（闸门外真阳率） | 背景臂 100 条（随机）＋先前 S1/S4/S5 294 条 | 比 | 3/394 = 0.76% | Wilson 95% CI 0.26%–2.21% | — | `score_clean_alerts.py` | 可用；**须与"背景臂 0/100"同屏** | 保留 |
| X-15 | 闸门外召回（干净池） | 分子 3（告警中真阳）；分母 = 池 14,299 × 基线率 X-14 | 比 | **2.8%** | 由 X-14 的 CI 两端传导：**0.9%–8.1%** | — | `score_clean_alerts.py` | **可断言：召回为个位数百分比量级**；不得写作"上界" | 保留（新测量） |

## 判读限制

- **X-01～X-05、X-07～X-09 的点估计一律不得出现在对外材料**（含 docx、附录、N 线、路演稿）；
- 引用 X-10 必须与「分层三成分」同屏；引用 X-12 必须与「标签仍为 LLM 口径」同屏；
- 新增任何"乘除外推"必须先在本表登记，再使用。
"""
open(os.path.join(HERE, "docs", "extrapolation_register.md"), "w", encoding="utf-8",
     newline="\n").write(REG)
print("  [写出] docs/extrapolation_register.md")

COV = """# 复核覆盖表（review coverage）

> **目的**：区分「**已送复核**」与「**已复核**」。凡未复核者，一律维持「单方、未过红队」标注。

| 结论／数字 | 提出方 | 复核方 | 复核结论 | 当前状态 |
|---|---|---|---|---|
| 80.4% 人工样本落在 v2 训练侧 | DSH | Kimi、Qwen | 数值成立（402/500）；但**对 v1 的适用性不成立**（v1 世代不同） | ③ 标注；仅限 **v2 世代**；v2 训练输入登记后可升级 |
| 干净池 14,299／15 条／0.105% | DSH | Kimi、Qwen | 测量成立；**分母为构造混合池**，须拆三成分 | 保留（限测量） |
| 留出侧 v1 0.381 / v2 0.471 | DSH | Qwen（⑤⑥） | **口径错误**（按 v2 划分判 v1）＋按 R7 不成立 | **撤回** |
| 2,168 / 45% / 37% | DSH | Qwen | 点估计外推、未传导；分母混总体 | **撤回** |
| 305 条可回收 | DSH | Kimi、Qwen | 同批拟合＋n=8 未传导 | **撤回**，待 S6 独立检验 |
| $4.2 / 4 小时 | DSH | Kimi、Qwen | 单价成立；**条数依据未写明** | 降级（须随附依据） |
| 召回上界 7–10% | DSH | Kimi、Qwen | 分母不同总体＋"上界"算法错误 | **撤回** |
| 词表 3/3 命中 | DSH | Kimi、Qwen | **同义反复**（hit_pos ≡ all_gate_out_pos） | **撤回** |
| 自攻 #4「闸门外从未 LLM 复核」 | DSH | Kimi、Qwen | **部分推翻**：300 条探针已复核（判正 6／in_scope 4／人工确认 3） | 改述为「仅在 300 条探针上验证过」 |
| 6 vs 4（LLM 判正数） | Qwen 提出 | DSH | 已闭合：判正 6、其中 in_scope 4 | 两数须同时入档 |
| 74 vs 112（v1 真留出侧条目） | Qwen 自纠 | DSH | 采 112／可比对 109／正例 8 | 已更新 |
| 前缀哈希 vs 全量哈希 | Qwen | DSH | 实测前缀碰撞（`8eef1c7e39e2`）→ **全量 SHA256** | 已写入 R34 与 manifest |
| `val_v2` 那 1 行差异 | Kimi | DSH | 定位为字面量 `'nan'`（4 行）；raw 与 normalized 均 19,281 | 已披露 |
| `val_v2` 重复行口径 | Kimi | DSH | 多余行 718（3.6%）／落入重复组 935（4.7%）／其中正例 0 | 已披露（两口径并列） |
| v3-lite 掉分归因 | DSH | **未复核** | — | **单方、未过红队** |
| S2c 命中计数（6/8、5/8 及分层） | DSH | **未复核** | — | **单方、未过红队**；附录探索性数字 |
| S6 独立检验 P(真阳｜扩词表命中) = **9.0%**（n=100，预注册完成） | DSH | **未复核** | — | **单方、未过红队**；偏离预注册 2% 已披露 |
| 扩词表可回收 ≈ **78 条**（区间 41–140） | DSH | **未复核** | — | 单方、未过红队 |
| Demo 冷启动路径实测（下载 530MB→加载→出报告） | DSH | **未复核** | — | 单方；详见 `docs/coldstart_test.md` |
| R34 条文与机械门 | Kimi/Qwen 稿 | DSH 合并 | 待最终确认 | 执行中 |
"""
open(os.path.join(HERE, "docs", "review_coverage_table.md"), "w", encoding="utf-8",
     newline="\n").write(COV)
print("  [写出] docs/review_coverage_table.md")

# ---------------- 机械门 ----------------
CHECK = '''# -*- coding: utf-8 -*-
"""机械门：禁报数字不得出现在对外材料（R5 扩展 + 红队裁定）。

规则：
  · 下列"撤回"数字出现在对外材料即 FAIL（除非该行同时含撤回/作废/禁报等字样）；
  · docs/extrapolation_register.md 自身：状态非撤回且填了点估计却无区间的行 → FAIL。

用法：python check_retracted_numbers.py   （0=通过，1=违规）
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = ["build_finals_content.py", "build_finals_appendix.py",
           "docs/N1_narrative_mainline.md", "docs/N2_narrative_final.md",
           "docs/N5_qna_factbase.md", "docs/N6_review_risk_list.md",
           "docs/roadshow_slides_corrections.md", "README.md"]
# 撤回数字（上下文锚定，避免误报）
PATTERNS = [r"0\\.381", r"0\\.471", r"2,?168", r"305\\s*条", r"\\$4\\.2", r"4\\.2\\s*美元",
            r"7[–\\-]10\\s*%", r"检出\\s*45\\s*%", r"45\\s*%.{0,6}检出",
            r"结构性漏检\\s*37", r"37\\s*%.{0,6}结构性", r"3/3\\s*命中", r"命中\\s*3/3",
            r"留出侧\\s*74\\s*条", r"召回上界\\s*7"]
EXEMPT = ("撤回", "作废", "禁报", "不得", "已废", "不再是")


def main() -> int:
    bad = []
    for rel in TARGETS:
        p = os.path.join(HERE, rel)
        if not os.path.isfile(p):
            continue
        for i, ln in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
            if any(e in ln for e in EXEMPT):
                continue
            for pat in PATTERNS:
                if re.search(pat, ln):
                    bad.append(f"{rel}:{i} 命中禁报数字 /{pat}/：{ln.strip()[:80]}")
    # 登记表自洽
    reg = os.path.join(HERE, "docs", "extrapolation_register.md")
    if os.path.isfile(reg):
        for i, ln in enumerate(open(reg, encoding="utf-8", errors="replace"), 1):
            if not ln.startswith("| X-"):
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) < 10:
                continue
            point, interval, status = cells[4], cells[5], cells[9]
            if point and point not in ("—", "-") and (not interval or interval in ("—", "-")) \\
                    and "撤回" not in status and "方向" not in status:
                bad.append(f"extrapolation_register.md:{i} 有点估计却无区间：{cells[0]}")
    print("## 禁报数字机械门（R5 扩展）")
    if bad:
        for b in bad:
            print(f"- [FAIL] {b}")
    else:
        print(f"- [PASS] 未发现禁报数字（扫描 {len(TARGETS)} 个对外材料）"
              f"；登记表自洽性通过")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
open(os.path.join(HERE, "check_retracted_numbers.py"), "w", encoding="utf-8",
     newline="\n").write(CHECK)
ast.parse(CHECK)
print("  [写出] check_retracted_numbers.py")

# 入链
P = os.path.join(HERE, "run_all_checks.py")
s = open(P, encoding="utf-8").read()
if "check_retracted_numbers" not in s:
    anchor = '    ("对外称谓一致性（正文 vs 附录）", ["check_scope_wording.py"]),'
    s = s.replace(anchor, '    ("禁报数字机械门（R5 扩展）", ["check_retracted_numbers.py"]),\n'
                          + anchor, 1)
    try:
        ast.parse(s)
        open(P, "w", encoding="utf-8", newline="\n").write(s)
        print("  [改] 门槛链新增禁报数字门（现 24 步）")
    except SyntaxError as e:
        print(f"  [失败] 未写盘：{e}")
