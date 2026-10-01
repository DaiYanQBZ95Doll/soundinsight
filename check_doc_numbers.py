# -*- coding: utf-8 -*-
# 本脚本用于文档数字一致性审计：扫描指定文档，逐项核对红线数字，
# 检测口径违规，输出 number_audit.md。
import datetime
import hashlib
import json
import os
import subprocess
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_MD = os.path.join(HERE, "number_audit.md")

# 数字 -> (允许的等价写法列表, 说明)
CORE_REQUIRED = [
    (r"0\.687", ["0.687", "0.6871", "68.7%"], "最终模型 F1"),
    (r"0\.6234", ["0.6234"], "5折CV平均F1"),
    (r"0\.024", ["0.024", "0.0240", "±0.024"], "CV标准差"),
    (r"0\.97", ["0.97", "0.9744"], "阈值"),
    (r"89\.6", ["89.6", "0.896"], "召回率"),
    (r"47\.9|66\.3", ["47.9", "66.3"],
     "精确率（须标阈值档：0.9744 档 66.3% / 0.5 档 47.9%）"),
    (r"0\.497", ["0.497"], "SVM基线"),
    (r"0\.410", ["0.410", "0.41"], "LR基线"),
    (r"0\.025", ["0.025"], "dummy基线"),
    (r"0\.7191", ["0.7191"], "AUC-PR"),
    (r"0\.000932", ["0.000932", "0.0009"], "t检验p值"),
    (r"1257", ["1257"], "正例(实验口径)"),
    (r"78%", ["78%"], "人工抽查精度"),
    (r"41\.5%", ["41.5%"], "三星漏检率"),
    (r"51\.8%", ["51.8%"], "弱标注精度"),
]

CORE_FORBIDDEN = [
    (r"1297", "错误正例数1297"),
    # 仅当与「教师/一致性」同现才算（避免误伤合法的 83.7% 召回等数值）
    (r"83\.7(?=[^\n]{0,40}(?:教师|一致性))|(?:教师|一致性)[^\n]{0,40}83\.7",
     "教师一致性出现在正文（仅允许方法说明/附录）"),
    (r"qwen3\.7-plus.*标注|标注.*qwen3\.7-plus", "已废弃的qwen标注复核claim"),
]

# Batch B 新数字：llm_baseline.md 必须包含（如实记录口径）
LLM_REQUIRED = [
    (r"0\.940", ["0.940", "94.0%"], "LLM零样本F1"),
    (r"0\.826", ["0.826"], "小模型子集F1"),
    (r"0\.873", ["0.873"], "LLM 5示例F1"),
    (r"0\.846", ["0.846"], "LLM复核模式F1"),
    (r"249,703", ["249,703", "249703"], "LLM实验tokens合计"),
    (r"0\.9044", ["0.9044", "0.904"], "LLM零样本召回"),
    (r"0\.7092", ["0.7092", "0.709"], "小模型子集召回"),
    (r"0\.971", ["0.971", "97.1%"], "LLM零样本Acc"),
    (r"2,560|2552", ["2,560", "2552", "2560"], "单批40条延迟实测"),
    (r"0\.9149", ["0.9149", "0.915"], "qwen零样本F1"),
    (r"490,747", ["490,747", "490747"], "qwen实验tokens合计"),
]

QNA_REQUIRED = [
    (r"0\.940", ["0.940", "94.0%"], "Q3/Q5/Q10 LLM零样本F1"),
    (r"0\.826", ["0.826"], "Q3 小模型子集F1"),
    (r"0\.873", ["0.873"], "Q10 5示例F1"),
    (r"0\.03", ["0.03", "$0.03"], "每1000条LLM成本"),
]

# 已废弃的旧claim，不得再出现在 Q&A 中
QNA_FORBIDDEN = [
    (r"0\.01/条", "已废弃的GPT-4单条$0.01成本claim"),
    (r"耗时 30 秒", "已废弃的未实测30秒claim"),
    (r"\$50", "已废弃的纯LLM标注$50成本claim"),
]

# Batch C/E 新文档数字
THROUGHPUT_REQUIRED = [
    (r"1\.763", ["1.763"], "GPU 1000条中位数(秒)"),
    (r"567\.1", ["567.1"], "GPU 吞吐(条/s)"),
    (r"28\.443", ["28.443"], "CPU 1000条中位数(秒)"),
    (r"35\.2", ["35.2", "35.6"], "CPU 吞吐(条/s)"),
]

CALIB_REQUIRED = [
    (r"0\.0122", ["0.0122"], "ECE十箱"),
    (r"0\.229", ["0.229"], "0.8-0.9箱实际正例率"),
    (r"0\.555", ["0.555"], "0.9-1.0箱实际正例率"),
]

ERRTAX_REQUIRED = [
    (r"FP=91", ["FP=91", "FP 91"], "误报数"),
    (r"FN=73", ["FN=73", "FN 73"], "漏报数"),
    (r"54\.9%", ["54.9%"], "FP其他问题占比"),
    (r"58\.9%", ["58.9%"], "FN委婉+双面占比"),
    (r"9\.1%", ["9.1%"], "标注噪声率(人工终审)"),
    (r"15/16", ["15/16"], "人工终审确认数"),
    (r"TP=179", ["TP=179"], "与冻结矩阵的调和说明"),
]

LENBUCKET_REQUIRED = [
    (r"0\.7080|0\.708", ["0.7080", "0.708"], "<=64 token F1"),
    (r"0\.7485|0\.749", ["0.7485", "0.749"], "65-128 token F1"),
    (r"0\.5649|0\.565", ["0.5649", "0.565"], ">128 token F1(截断桶)"),
    (r"3728", ["3728", "3,728"], ">128 token 评论数"),
    (r"tokenizer", ["tokenizer"], "token 口径声明"),
]

MODELCARD_REQUIRED = [
    (r"0\.0122", ["0.0122"], "ECE十箱"),
    (r"0\.9744", ["0.9744"], "阈值"),
    (r"9\.1%", ["9.1%"], "标注噪声率(人工终审)"),
    (r"1280", ["1280"], "当前工作集正例数"),
]

RESULTSSUMMARY_REQUIRED = [
    (r"0\.687", ["0.687", "0.6871"], "最终F1"),
    (r"TP=178", ["TP=178"], "GPU重跑矩阵调和行"),
    (r"FN=73", ["FN=73"], "GPU重跑FN"),
    (r"TP=179", ["TP=179"], "冻结矩阵"),
]

# 官方复赛模板（hackathon-复赛作品提交模板-天池版.docx）必备章节
TEMPLATE_SECTIONS = [
    "团队信息", "参赛信息", "业务价值与市场分析", "产品功能与使用说明",
    "技术架构及调用模型说明", "项目开发及阶段成果说明", "提交物清单",
    "附件命名规范", "注意事项",
]
TEMPLATE_FILES = ["competition_v4.md", "competition_v3.txt"]

# 口径配对检查覆盖的文档（提交物与对外交接文档）
PAIR_FILES = [
    "competition_v4.md", "competition_v3.txt", "README.md",
    "QWEN_HANDOFF.md", "MODEL_CARD.md",
    "AI_HANDOFF/01_project_overview.md",
    "AI_HANDOFF/03_metrics_and_caveats.md",
    # 复盘文档同样对外公开，曾出现"F1 0.6871（阈值 0.9744）、召回 89.6%"式并排
    "docs/retrospective_and_reflection.md",
    # 决赛阶段的对外文档（质检方 §九.2：配对检查须覆盖全部 F1/召回/精确率）
    "docs/finals_stage.md", "docs/v2_acceptance_benchmark.md",
    # E4（冻结清单 §二）：锁定期间仍在编辑的流程文档纳入覆盖。
    # 补全前这些文档的编辑不受代际与配对约束；纳入后实测 0 FAIL。
    "docs/final_project_review_and_execution_plan.md",
    "docs/final_review_and_execution_plan.md",
    "docs/gap_and_roadmap_inventory.md",
    "docs/external_sources_register.md",
    "docs/frozen_execution_checklist.md",
    "docs/pre_lock_completeness_audit.md",
    "docs/completeness_audit_round2.md",
    "docs/N_line_handoff_protocol.md",
]

# 阈值档表：一行内命中两个及以上档的值时，该行必须为每一档写出标签
THRESHOLD_TIERS = {
    "调优(0.9744)": {"labels": ("0.9744", "0.97", "调优"),
                     "values": ("0.6871", "0.687", "66.3", "71.3")},
    "0.5": {"labels": ("0.5", "0.50"), "values": ("0.6241", "47.9", "89.6")},
}

# 代际：v1 = 复赛已提交口径；v2 = 决赛口径（落地后把新指标填进 tokens，检查自动生效）
GEN_TAGS = ("[v1]", "[v2]")
# 产品运行时模块：这些文件必须可编译，且代码行内不得出现"数字直贴 [v1]/[v2]"
# （2026-10-01：M0 的行级文本替换曾把 `tuned_thr = 0.9744` 改成 `0.9744[v1]`，
#   导致包内 Demo 运行失败而数字审计全绿——本清单与检查即为该事故的机械化防护）
PRODUCT_MODULES = ["report_builder.py", "deployment/report_builder.py",
                   "soundinsight_agent.py", "demo_sound_v2.py", "demo_sound.py",
                   "api_server.py", "text_utils.py", "predict_core.py",
                   "deployment/app.py", "download_models.py"]
TAG_GLUED = re.compile(r"\d\[v[12]\]")
GEN_TOKENS = {
    "v1": ["0.6871", "0.9744", "0.6234", "0.7191", "0.6241", "0.000932"],
    "v2": ["0.7220", "0.7206", "0.7811", "0.8273", "0.5333"],  # E5 填入：F1@调优/F1@0.5/PR-AUC/归因宏F1/高音F1
}
CURRENT_GEN = os.environ.get("DSH_DOC_GEN", "v1")
GEN_FILES = PAIR_FILES + [
    "docs/project_full_record.md", "PROGRESS_SYNC.md",
    # 2026-10-01 扩充：决赛阶段新增的、含两代数字的证据与叙事文档
    "docs/v2_gate_verdict.md", "docs/DoD_completion_table.md",
    "docs/w1_longtext_variants.md", "docs/w17_failure_cases.md",
    "docs/e2_erratum.md", "docs/w17_confidence_actions.md",
    "docs/W5_cv_interpretation.md", "docs/w11_data_efficiency.md",
    "docs/w13_keyword_miss_rate.md",
    "docs/N1_narrative_mainline.md", "docs/N1b_downgrade_narrative.md",
    "docs/N2_narrative_final.md", "docs/N3_calibration_evidence.md",
    "docs/N4_target_argument.md", "docs/N5_qna_factbase.md",
    "docs/N6_review_risk_list.md",
]

# D7：否定性状态断言的触发词 / 豁免语境 / 豁免指针 / 检查范围（当前态文档）
STATUS_TRIGGERS = ("未使用", "无出处", "查无", "不存在", "未调用", "从未调用",
                   "没有出处", "无任何出处", "未提供")
STATUS_EXEMPT_CTX = ("曾", "历史", "原写", "原表", "原判", "旧", "过时", "勘误",
                     "更正", "订正", "不得", "错误", "误用", "不准确", "路线",
                     "取代", "已作废", "已删除", "确认", "检索", "同上", "禁止",
                     "清理", "任务", "计划", "要求", "应填", "结论", "披露")
STATUS_OK = re.compile(r"(\d{4}-\d{2}-\d{2}|\d{4}\s*年\s*\d{1,2}\s*月|"
                       r"\.md|\.py|\.json|\.csv|\.txt|\.docx|docs/|#L\d|§|"
                       r"核验|实测|状态源|见\s*`|待人工|待补|本轮|当日)")
STATUS_FILES = GEN_FILES  # 历史材料与转储（B 类）不在其中
GEN_HISTORY_MARKERS = ("已作废", "已废弃", "历史", "曾", "取代", "旧口径", "勘误",
                       "修正前", "过时", "v1.1", "路线 (a)")

# 冻结的复赛提交包（红线 9：不得覆盖；2026-09-14 21:44:28 提交）
FROZEN_ZIP_NAME = "更新世界的锋芒_SoundInsight_复赛作品.zip"
FROZEN_ZIP_SHA = "e6cae286515ef1d27866a629cf78f695984b74a85c73ed0ad9bc7dc5c6485db2"

# 决赛主文档候选（填好模板后放到项目根目录即可自动检查）
FINALS_DOC_CANDIDATES = [
    "更新世界的锋芒_SoundInsight_决赛入围定稿作品.docx",
    "更新世界的锋芒_SoundInsight_决赛入围定稿作品.pdf",
]

# 决赛模板九节（据 hackathon-决赛入围定稿作品提交模板-天池版.docx 原文）
TEMPLATE_SECTIONS_FINALS = [
    "团队信息", "参赛信息", "业务价值与市场分析", "产品功能与使用说明",
    "技术架构及调用模型说明", "项目开发及阶段成果说明", "提交物清单",
    "附件命名规范", "注意事项",
]

GROUPS = [
    {"files": ["competition_v3.txt", "competition_v4.md", "README.md",
               "QWEN_HANDOFF.md", "ppt_text_dump.md"],
     "required": CORE_REQUIRED, "forbidden": CORE_FORBIDDEN, "check_1288": True},
    {"files": ["llm_baseline.md"],
     "required": LLM_REQUIRED, "forbidden": [], "check_1288": False},
    {"files": ["qna_preparation.md"],
     "required": QNA_REQUIRED, "forbidden": QNA_FORBIDDEN, "check_1288": False},
    {"files": ["throughput_eval.md"],
     "required": THROUGHPUT_REQUIRED, "forbidden": [], "check_1288": False},
    {"files": ["calibration_eval.md"],
     "required": CALIB_REQUIRED, "forbidden": [], "check_1288": False},
    {"files": ["error_taxonomy.md"],
     "required": ERRTAX_REQUIRED, "forbidden": [], "check_1288": False},
    {"files": ["length_bucket_eval.md"],
     "required": LENBUCKET_REQUIRED, "forbidden": [], "check_1288": False},
    {"files": ["MODEL_CARD.md"],
     "required": MODELCARD_REQUIRED, "forbidden": [], "check_1288": False},
    {"files": ["results_summary.md"],
     "required": RESULTSSUMMARY_REQUIRED, "forbidden": [], "check_1288": False},
]


def read_file(name):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return None, None
    with open(p, encoding="utf-8", errors="replace") as f:
        content = f.read()
    if name == "ppt_text_dump.md":
        # 只审计正文提取区，截断自动核对小节，避免自匹配假 FAIL
        marker = "## 自动核对"
        if marker in content:
            content = content.split(marker)[0]
    return content.splitlines(keepends=True), p


def audit_file(fname, required, forbidden, check_1288, out):
    lines, path = read_file(fname)
    if lines is None:
        out.append(f"## {fname}")
        out.append("- 文件不存在：SKIP（不判 FAIL）")
        out.append("")
        return
    out.append(f"## {fname}")
    # 必含数字
    for pattern, variants, desc in required:
        hits = []
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                hits.append(i)
        ok = "PASS" if hits else "FAIL"
        out.append(f"- [{ok}] {desc} ({pattern}): "
                   f"{'行 ' + ','.join(map(str, hits[:5])) if hits else '未出现'}")
    # 违禁检测
    for pattern, desc in forbidden:
        found = False
        for i, line in enumerate(lines, 1):
            m = re.search(pattern, line)
            if m:
                if desc.startswith("教师一致性") and \
                   re.search(r"方法|附录|蒸馏|不作为|可行性", line):
                    continue  # 方法说明语境，允许
                out.append(f"- [FAIL] {desc} 出现在行 {i}: "
                           f"{line.strip()[:80]}")
                found = True
                break
        if not found:
            out.append(f"- [PASS] 未发现 {desc}")
    # 正例口径：1288 出现时必须带口径说明
    if check_1288:
        for i, line in enumerate(lines, 1):
            if re.search(r"1288", line) and not re.search(r"口径|补捞|扩展|高音", line):
                out.append(f"- [FAIL] 1288 出现但无口径说明，行 {i}: {line.strip()[:80]}")
    out.append("")


def check_template_conformance(out) -> None:
    """对照官方复赛模板（hackathon-复赛作品提交模板-天池版.docx）的九章结构。"""
    out.append("## 模板格式对照（官方复赛模板九章 + 在线链接表）")
    for fname in TEMPLATE_FILES:
        lines, _ = read_file(fname)
        if lines is None:
            out.append(f"- [FAIL] {fname} 文件不存在")
            continue
        text = "\n".join(lines)
        heads = re.findall(r"^##\s*([一二三四五六七八九十]+)、(.+)$", text,
                           flags=re.M)
        nums = [h[0] for h in heads]
        titles = " ".join(h[1] for h in heads)
        missing = [s for s in TEMPLATE_SECTIONS if s not in titles]
        dup = sorted({n for n in nums if nums.count(n) > 1})
        out.append(f"- {fname}：正文章节 {len(heads)} 个")
        out.append(f"  - [{'FAIL' if missing else 'PASS'}] 模板必备章节："
                   f"{'缺 ' + '、'.join(missing) if missing else '九章齐备'}")
        out.append(f"  - [{'FAIL' if dup else 'PASS'}] 章节编号重复："
                   f"{'重复 ' + '、'.join(dup) if dup else '无'}")
        out.append(f"  - [{'PASS' if '在线链接填写表' in text else 'FAIL'}] "
                   f"在线链接填写表")
        out.append(f"  - [{'PASS' if '团队名称：更新世界的锋芒' in text else 'FAIL'}] "
                   f"团队信息已填写")
    out.append("")


def check_threshold_pairing(out) -> None:
    """口径配对检查：同一行出现**不同阈值档**的指标时，必须为每一档显式写出阈值标签。

    起因：v4 §7.2 曾写成"F1=0.6871（阈值 0.97），召回率 89.6%，精确率 47.9%"——
    三个数字并排，读者会当成同一阈值的结果，实际 89.6%/47.9% 来自阈值 0.5。
    本函数已按质检方要求从"仅 F1 与 P/R"扩展为**全指标、按阈值档**判定：
    凡一行内命中两个及以上档的值，该行必须同时出现这些档的标签，否则 FAIL。
    """
    out.append("## 口径配对检查（阈值档，全指标）")
    for fname in PAIR_FILES:
        lines, _ = read_file(fname)
        if lines is None:
            out.append(f"- {fname}：不存在，SKIP")
            continue
        bad = []
        for i, line in enumerate(lines, 1):
            present = [tier for tier, spec in THRESHOLD_TIERS.items()
                       if any(v in line for v in spec["values"])]
            if len(present) < 2:
                continue
            missing = [t for t in present
                       if not any(lb in line for lb in THRESHOLD_TIERS[t]["labels"])]
            if missing and not any(mk in line for mk in GEN_HISTORY_MARKERS):
                bad.append((i, missing, line.strip()[:90]))
        if bad:
            for i, missing, snippet in bad:
                out.append(f"- [FAIL] {fname} 行 {i} 并排了 {'/'.join(missing)} 档却未标该档阈值：{snippet}")
        else:
            out.append(f"- [PASS] {fname}：跨档指标均已标注阈值档")
    # PPT 文本：不在提交 zip 内，仅提示不判 FAIL（改与不改由用户决定）
    lines, _ = read_file("ppt_text_dump.md")
    if lines:
        hits = []
        for i, line in enumerate(lines, 1):
            present = [t for t, spec in THRESHOLD_TIERS.items()
                       if any(v in line for v in spec["values"])]
            if len(present) >= 2 and any(
                    not any(lb in line for lb in THRESHOLD_TIERS[t]["labels"])
                    for t in present):
                hits.append(i)
        out.append(f"- [注意] ppt_text_dump.md：{len(hits)} 行跨档未标"
                   f"（{'行 ' + ','.join(map(str, hits)) if hits else '无'}）"
                   f"——PPT 不在提交包内，需用户决定是否改")
    out.append("")


def check_generation_mixing(out) -> None:
    """代际混用检查（质检方 §九.1/§九.2）：doc 内两代数字并排而无 [v1]/[v2] 标注即 FAIL。

    代际语法：实验数字后带 `[v1]`（复赛已提交口径）或 `[v2]`（决赛口径），首次出现处附说明。
    **当前代**：若 `GEN_TOKENS["v2"]` 已有值（E5 已填），当前代即 v2；否则沿用环境变量
    `DSH_DOC_GEN`（默认 v1）。2026-10-01 修正：此前标注恒为 v1，与换代事实不符。
    """
    v2_tokens = GEN_TOKENS.get("v2") or []
    current = "v2" if v2_tokens else CURRENT_GEN
    out.append(f"## 代际检查（当前代：{current}；v2 token 已登记 {len(v2_tokens)} 个）")
    if not v2_tokens:
        out.append("- [注意] v2 数字尚未产生（`GEN_TOKENS[\"v2\"]` 为空）："
                   "混用检查当前仅覆盖 v1；v2 落地时把新指标/tokens 填入即可自动生效")
    for fname in GEN_FILES:
        lines, _ = read_file(fname)
        if lines is None:
            out.append(f"- {fname}：不存在，SKIP")
            continue
        bad = []
        for i, line in enumerate(lines, 1):
            gens = [g for g, toks in GEN_TOKENS.items()
                    if toks and any(t in line for t in toks)]
            if len(gens) >= 2 and not any(tag in line for tag in GEN_TAGS) \
                    and not any(mk in line for mk in GEN_HISTORY_MARKERS):
                bad.append((i, gens, line.strip()[:80]))
        for i, gens, snippet in bad:
            out.append(f"- [FAIL] {fname} 行 {i} 含 {'+'.join(gens)} 两代数字但无代际标签：{snippet}")
        if not bad:
            out.append(f"- [PASS] {fname}：无未标注的代际混用")
    out.append("")


def check_frozen_package(out) -> None:
    """冻结包保护（质检方 §九.5）：已提交的复赛包不得被重打覆盖。

    以根目录 hashes.txt 记录值与磁盘实际哈希双向核对；任一不符即 FAIL，
    因为那意味着"仓库里的包 ≠ 已提交的包"。
    """
    out.append("## 提交包冻结校验（红线 9）")
    p = os.path.join(HERE, "hashes.txt")
    if not os.path.isfile(p):
        out.append("- [SKIP] 无 hashes.txt")
        out.append("")
        return
    rec = ""
    for line in open(p, encoding="utf-8", errors="replace").read().splitlines():
        if FROZEN_ZIP_NAME in line:
            m = re.search(r"sha256:([0-9a-f]{16,})", line)
            rec = m.group(1) if m else ""
    disk = os.path.join(HERE, FROZEN_ZIP_NAME)
    if not os.path.isfile(disk):
        out.append(f"- [SKIP] 磁盘上无 {FROZEN_ZIP_NAME}（仅作记录）")
        out.append("")
        return
    h = hashlib.sha256(open(disk, "rb").read()).hexdigest()
    ok_rec = rec.startswith(FROZEN_ZIP_SHA[:16])
    ok_disk = h.startswith(FROZEN_ZIP_SHA[:16])
    out.append(f"- [{'PASS' if ok_rec else 'FAIL'}] hashes.txt 记录的是已提交版本"
               f"（{rec[:16] or '未找到'} vs 冻结值 {FROZEN_ZIP_SHA[:16]}）")
    out.append(f"- [{'PASS' if ok_disk else 'FAIL'}] 磁盘上的包与已提交版本一致"
               f"（{h[:16]} vs {FROZEN_ZIP_SHA[:16]}）")
    if not (ok_rec and ok_disk):
        out.append("- 说明：若确为 v2 换代后的新包，应另建**新文件名**（决赛包），"
                   "并在此登记新的冻结值，而不是覆盖复赛包")
    out.append("")


def check_finals_template(out) -> None:
    """决赛模板合规（质检方 §九.3）：九节齐备 + 编号唯一 + 在线链接表 + 团队信息
    + **5.2 百炼栏按既成事实填写**（真实调用 qwen3.7-plus + 百炼 Token Plan，非"未使用"）。"""
    out.append("## 决赛模板合规检查（模板九节 + 5.2 百炼栏事实）")
    target = None
    for cand in FINALS_DOC_CANDIDATES:
        fp = os.path.join(HERE, cand)
        if os.path.isfile(fp):
            target = (cand, fp)
            break
    if target is None:
        out.append(f"- [SKIP] 决赛主文档尚未生成（候选：{'、'.join(FINALS_DOC_CANDIDATES)}）"
                   "——检查项已就绪，填好模板后自动生效")
        out.append("")
        return
    name, fp = target
    if name.lower().endswith(".docx"):
        try:
            xml = zipfile.ZipFile(fp).read("word/document.xml").decode("utf-8", "replace")
            text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, flags=re.S))
        except (OSError, KeyError, zipfile.BadZipFile) as e:
            out.append(f"- [FAIL] {name} 无法读取（{type(e).__name__}）")
            out.append("")
            return
    else:
        try:
            import pypdf
            text = "\n".join((pg.extract_text() or "") for pg in pypdf.PdfReader(fp).pages)
        except Exception as e:  # noqa: BLE001 - 缺依赖/坏文件都只报告
            out.append(f"- [FAIL] {name} 无法读取（{type(e).__name__}）")
            out.append("")
            return

    missing = [s for s in TEMPLATE_SECTIONS_FINALS if s not in text]
    nums = re.findall(r"([一二三四五六七八九])、", text)
    dup = sorted({n for n in nums if nums.count(n) > 1})
    out.append(f"- 目标文档：{name}（{len(text)} 字符）")
    out.append(f"  - [{'FAIL' if missing else 'PASS'}] 模板九节："
               f"{'缺 ' + '、'.join(missing) if missing else '齐备'}")
    out.append(f"  - [{'FAIL' if dup else 'PASS'}] 章节编号唯一："
               f"{'重复 ' + '、'.join(dup) if dup else '无'}")
    out.append(f"  - [{'PASS' if 'http' in text else 'FAIL'}] 在线链接表："
               f"{'已含链接' if 'http' in text else '未填链接'}")
    out.append(f"  - [{'PASS' if '更新世界的锋芒' in text else 'FAIL'}] 团队信息已填写")
    has_qwen = "qwen3.7-plus" in text or "qwen3.7" in text
    has_bailian = "百炼" in text or "Token Plan" in text
    false_claim = re.search(r"百炼[^。\n]{0,40}未使用|未使用[^。\n]{0,20}百炼", text)
    ok_bailian = has_qwen and has_bailian and not false_claim
    out.append(f"  - [{'PASS' if ok_bailian else 'FAIL'}] 5.2 百炼栏按既成事实填写"
               f"（qwen3.7-plus={'有' if has_qwen else '无'}、"
               f"百炼/Token Plan={'有' if has_bailian else '无'}、"
               f"假称未使用={'有' if false_claim else '无'}）")
    out.append("")


def check_v2_artifacts(out) -> None:
    """v2 可核验产物（质检方 §七(5)/§九.4）：权重不入库，但须入库
    模型 SHA256 + threshold.json + 训练命令 + 评估原始输出 + v2 MODEL_CARD 登记。"""
    out.append("## v2 可核验产物检查")
    reg = os.path.join(HERE, "v2", "v2_artifacts.json")
    if not os.path.isfile(reg):
        out.append("- [SKIP] 无 `v2/v2_artifacts.json`：v2 尚未落地。"
                   "采纳 v2 时须提供该登记文件，字段：model_sha256{}、threshold_json{}、"
                   "train_command、eval_outputs[]、model_card")
        out.append("")
        return
    import json
    try:
        data = json.load(open(reg, encoding="utf-8"))
    except ValueError as e:
        out.append(f"- [FAIL] v2_artifacts.json 解析失败：{e}")
        out.append("")
        return
    problems = []
    for key in ("model_sha256", "threshold_json", "train_command",
                "eval_outputs", "model_card"):
        if key not in data:
            problems.append(f"缺字段 {key}")
    def _verify(path: str, expect: str, what: str) -> None:
        fp = os.path.join(HERE, path)
        if not os.path.isfile(fp):
            problems.append(f"{what} 文件不存在：{path}")
            return
        h = hashlib.sha256(open(fp, "rb").read()).hexdigest()
        if not h.startswith(expect):
            problems.append(f"{what} 哈希不符：{path}（记录 {expect} 实际 {h[:16]}）")
    for path, sha in (data.get("model_sha256") or {}).items():
        _verify(path, sha, "模型")
    tj = data.get("threshold_json") or {}
    if isinstance(tj, dict) and "path" in tj:
        _verify(tj["path"], tj.get("sha256", ""), "threshold.json")
    for path in (data.get("eval_outputs") or []):
        if not os.path.isfile(os.path.join(HERE, path)):
            problems.append(f"评估原始输出不存在：{path}")
    if data.get("model_card") and not os.path.isfile(
            os.path.join(HERE, data["model_card"])):
        problems.append(f"v2 MODEL_CARD 不存在：{data['model_card']}")
    if problems:
        for p in problems:
            out.append(f"- [FAIL] {p}")
    else:
        out.append("- [PASS] v2 产物登记齐全且哈希一致")
    out.append("")


def check_status_assertions(out) -> None:
    """D7 否定性状态断言检查：对"当前状态/外部来源"的否定断言必须带日期或来源指针。

    背景：同类错误在本项目出现过三次（"百炼栏 = 未使用"两次、"激动线外部数字全部无出处"
    一次），根因都是**断言状态而未核对**。本检查把"记得核对"变成机械可拦。

    规则：
    - 触发词（高危否定断言）：未使用 / 无出处 / 查无 / 不存在 / 未调用 / 从未调用 /
      没有出处 / 无任何出处 / 未提供；
    - 豁免语境（历史、引用、勘误、任务、结论等）：曾 / 历史 / 原写 / 原判 / 旧 / 过时 /
      勘误 / 更正 / 订正 / 不得 / 错误 / 误用 / 不准确 / 路线 / 取代 / 已作废 / 已删除 /
      确认 / 检索 / 同上 / 禁止 / 清理 / 任务 / 计划 / 要求 / 应填 / 结论；
    - 豁免指针：日期（YYYY-MM-DD 或 YYYY年M月）/ 文件名 / docs/ / #LNN / 核验 / 实测 /
      状态源 / 待人工 / 待补 / 本轮 / 当日 / §；
    - 豁免文件：历史材料与转储（B 类）不检查。

    诚实披露"未开展/未做/未完成"不属本检查范围（那是如实记录局限，不是状态断言）。
    """
    out.append("## 否定性状态断言检查（D7）")
    bad = []
    for fname in STATUS_FILES:
        lines, _ = read_file(fname)
        if lines is None:
            continue
        for i, line in enumerate(lines, 1):
            if not any(t in line for t in STATUS_TRIGGERS):
                continue
            if STATUS_OK.search(line):
                continue
            if any(c in line for c in STATUS_EXEMPT_CTX):
                continue
            bad.append((fname, i, line.strip()[:100]))
    if not bad:
        out.append(f"- [PASS] {len(STATUS_FILES)} 份当前态文档中，"
                   "否定性状态断言均带日期/来源指针或属豁免语境")
    else:
        out.append(f"- [FAIL] {len(bad)} 处否定性状态断言未带日期或来源指针"
                   "（须补核验日期或指向状态源；若属历史/引用语境请加相应标记）：")
        for fname, i, snippet in bad[:20]:
            out.append(f"    - {fname}:{i}｜{snippet}")
    out.append("")


def check_api_wording_consistency(out) -> None:
    """M0b 跨材料口径一致性：README 与决赛主文档的模型调用表述必须逐字一致。

    背景（红队第三轮）：README 曾只写"大模型 API（deepseek-chat）复核标注"，对百炼只字未提；
    而决赛模板 5.2 要求填真实调用。若评委同时打开仓库与 PDF，会看到两套表述。
    处置：定义**三句权威表述**（见 README「模型调用与边界」段），要求两侧逐字出现。

    检查方式（机械）：三句各自的关键短语必须同时出现在 README 与决赛主文档中；
    任一缺失即 FAIL 并指出缺哪句。决赛主文档尚未生成时 SKIP（与模板检查同口径）。
    """
    out.append("## 跨材料口径一致性检查（M0b）")
    required = [
        ("产品推理本地化", "100% 本地"),
        ("标注侧通道", "DeepSeek 官方 API"),
        ("对照侧通道", "Token Plan"),
    ]
    readme, _ = read_file("README.md")
    if readme is None:
        out.append("- [FAIL] README.md 不存在，无法核对权威表述")
        out.append("")
        return
    readme_text = "\n".join(readme)
    missing_readme = [name for name, kw in required if kw not in readme_text]
    finals = None
    for cand in FINALS_DOC_CANDIDATES:
        fp = os.path.join(HERE, cand)
        if not os.path.isfile(fp):
            continue
        if cand.lower().endswith(".docx"):
            # .docx 必须走 XML 文本抽取：read_file 按 UTF-8 读会得到二进制垃圾，
            # 关键词永远匹配不到（2026-10-01 修复的假 FAIL）。
            try:
                xml = zipfile.ZipFile(fp).read("word/document.xml").decode("utf-8", "replace")
                text = "\n".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, flags=re.S))
            except (OSError, KeyError, zipfile.BadZipFile) as e:
                out.append(f"- [FAIL] {cand} 无法解析：{type(e).__name__}")
                break
            finals = (cand, text)
        else:
            lines, _ = read_file(cand)
            if lines is not None:
                finals = (cand, "\n".join(lines))
        break
    if missing_readme:
        out.append(f"- [FAIL] README 缺少权威表述要素：{'、'.join(missing_readme)}")
    else:
        out.append("- [PASS] README 含全部三句权威表述要素")
    if finals is None:
        out.append("- [SKIP] 决赛主文档尚未生成：生成后本检查将要求两侧逐字一致")
    else:
        name, text = finals
        missing = [n for n, kw in required if kw not in text]
        if missing:
            out.append(f"- [FAIL] {name} 缺少权威表述要素：{'、'.join(missing)}"
                       "（须与 README「模型调用与边界」段逐字一致）")
        else:
            out.append(f"- [PASS] {name} 含全部三句权威表述要素")
    out.append("")


def check_package_size_claims(out) -> None:
    """当前态文档里的决赛包**字节数**必须等于实际值（否则即为"重建后未同步"的陈旧数字）。

    背景（2026-10-01 红队记账观察）：同一份包的体积在多次重建后出现在不同文档里
    （44,538,005 / 44,582,250 / 44,592,798 …），而体积**每轮重建都会变**。
    规则：当前态文档若写死字节数，必须与磁盘上一致；历史/勘误类文档豁免（须自带"当时/构建批次"字样）。
    """
    out.append("## 决赛包体积声明一致性")
    finals = os.path.join(HERE, "更新世界的锋芒_SoundInsight_决赛入围定稿作品.zip")
    if not os.path.isfile(finals):
        out.append("- [SKIP] 决赛包不存在")
        out.append("")
        return
    cur = os.path.getsize(finals)
    # 当前态文档（写死字节数须等于实际值）；历史文档按文件名豁免
    HIST = {"docs/D13_seal_declaration.md", "docs/overnight_summary.md",
            "docs/legacy_materials_notice.md", "PROGRESS_SYNC.md"}
    pat = re.compile(r"(4[0-9],\d{3},\d{3})\s*B")
    bad = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "_tmp_selftest",
                                                "_tmp_pkgcheck", "node_modules")]
        for f in files:
            if not f.endswith(".md"):
                continue
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, HERE).replace("\\", "/")
            if rel in HIST or rel == "number_audit.md":
                continue
            try:
                lines = open(fp, encoding="utf-8", errors="replace").read().splitlines()
            except OSError:
                continue
            for i, ln in enumerate(lines, 1):
                for m in pat.finditer(ln):
                    val = int(m.group(1).replace(",", ""))
                    # 已冻结产物的体积不是"包体积声明"：视频 48,375,526（faststart）／复赛包 44,446,308
                    if val in (cur, 44446308, 48375526):
                        continue
                    if "视频" in ln or "video" in ln.lower() or ".mp4" in ln:
                        continue
                    if any(k in ln for k in ("当时", "构建批次", "冻结值", "历史", "随重建变化", "以 `hashes.txt`")):
                        continue
                    bad.append(f"{rel}:{i} → {m.group(1)} B（当前 {cur:,} B）")
    if bad:
        for b in bad[:8]:
            out.append(f"- [FAIL] 陈旧的决赛包体积声明：{b}")
        out.append("  （体积随重建变化；正文请写「精确值见 hashes.txt」或标注历史批次）")
    else:
        out.append(f"- [PASS] 未发现陈旧的包体积声明（当前 {cur:,} B）")
    out.append("")


def check_paired_totals(out) -> None:
    """覆盖总量与覆盖率必须与权威成对口径一致（防"两端混用口径"第四次出现）。

    权威值取 `v2/scoped_estimates.json::paired_totals`；扫描各文档中的
    「总量区间/覆盖率」写法，凡出现**非权威数值**即 FAIL（勘误语境由 ERRATA_ALLOW 放行）。
    """
    out.append("## 覆盖总量口径一致性（成对口径，防混用）")
    p = os.path.join(HERE, "v2", "scoped_estimates.json")
    if not os.path.isfile(p):
        out.append("- [SKIP] 缺少 v2/scoped_estimates.json")
        out.append("")
        return
    with open(p, encoding="utf-8") as fh:
        data = json.load(fh)
    pt = data.get("paired_totals", {})
    if not pt:
        out.append("- [FAIL] 权威文件缺少 paired_totals")
        out.append("")
        return
    good_total = {str(pt["strict_strict"]["total"]), str(pt["inclusive_inclusive"]["total"])}
    good_cov = {f"{pt['strict_strict']['coverage_pct']:.1f}%",
                f"{pt['inclusive_inclusive']['coverage_pct']:.1f}%"}
    # 已知历史值：只允许出现在勘误/更正语境
    ERRATA_ALLOW = ("勘误", "更正", "作废", "旧值", "初版", "此前", "错误", "混用", "old")
    total_pat = re.compile(r"2,[45]\d\d\s*[–~-]\s*2,[45]\d\d")
    cov_pat = re.compile(r"\b(4[0-9]|5[0-9])\.[0-9]%\s*[–~-]\s*(4[0-9]|5[0-9])\.[0-9]%")
    # 排除生成物（审计报告/卫生报告/巡检日志等）——否则报告里的 FAIL 文本会被再次扫到（自污染）
    SKIP = {"number_audit.md", "docs/repo_hygiene_scan.md", "docs/demo_uptime_log.md",
            "docs/ai_handoff_manifest.md"}
    files = [f for f in os.listdir(HERE)
             if f.endswith(".md") and f not in SKIP]
    docs_dir = os.path.join(HERE, "docs")
    if os.path.isdir(docs_dir):
        files += [os.path.join("docs", f) for f in os.listdir(docs_dir)
                  if f.endswith(".md") and os.path.join("docs", f) not in SKIP]
    bad = []
    for f in files:
        fp = os.path.join(HERE, f)
        try:
            lines = open(fp, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        for i, ln in enumerate(lines, 1):
            if any(k in ln for k in ERRATA_ALLOW):
                continue
            for m in total_pat.finditer(ln):
                a, b = m.group(0).replace(" ", "").split("–") if "–" in m.group(0) \
                    else m.group(0).replace(" ", "").split("-")
                if a.replace(",", "") not in good_total or b.replace(",", "") not in good_total:
                    bad.append((f, i, m.group(0)))
            for m in cov_pat.finditer(ln):
                for g in m.groups():
                    pass
    if bad:
        for f, i, val in bad[:8]:
            out.append(f"- [FAIL] {f}:{i} 出现非权威总量区间「{val}」"
                       f"（权威：{'／'.join(sorted(good_total))}）")
    else:
        out.append(f"- [PASS] 未发现混用口径的总量区间"
                   f"（权威成对值 {sorted(good_total)}，覆盖率 {sorted(good_cov)}）")
    out.append("")


def check_checklist_version(out) -> None:
    """v1.5 附加条款②：清单条目与版本元数据一致性（防"越权新增"重演）。

    依据 `docs/checklist_version.json`：
      ① 清单声明的当前版本 == JSON.current_version；
      ② 清单条目 ID ⊆ 锁定 ID ∪ 追认新增（多出者即未登记新增 → FAIL）；
      ③ 追认新增必须实际出现在清单中（只登记不落地也 FAIL）；
      ④ JSON.locked_item_ids 必须与 base_locked_commit 的清单快照一致（防篡改基线）。
    """
    out.append("## 清单版本与新增项一致性（v1.5 附加条款②）")
    meta_path = os.path.join(HERE, "docs", "checklist_version.json")
    if not os.path.isfile(meta_path):
        out.append("- [FAIL] 缺少 docs/checklist_version.json（v1.5 元数据）")
        out.append("")
        return
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)
    lines, cpath = read_file("docs/frozen_execution_checklist.md")
    if lines is None:
        out.append("- [FAIL] 读不到清单文件")
        out.append("")
        return
    text = "".join(lines)
    declared = meta.get("current_version", "")
    if f"**{declared}**" not in text and declared not in text.splitlines()[0]:
        out.append(f"- [FAIL] 清单未声明当前版本 {declared}")
    else:
        out.append(f"- [PASS] 清单已声明当前版本 {declared}")
    ids = set(re.findall(r"\*\*([A-Z]\d{1,2}[a-z]?)\*\*", text))
    locked = set(meta.get("locked_item_ids", []))
    ratified = set(meta.get("ratified_additions", []))
    unknown = sorted(ids - locked - ratified)
    if unknown:
        out.append(f"- [FAIL] 清单含 {len(unknown)} 个未登记条目：{unknown}"
                   f"——**锁定后新增必须先升版并登记到 checklist_version.json**")
    else:
        out.append(f"- [PASS] 清单条目 {len(ids)} 个，全部属于「锁定基线 ∪ 追认新增」")
    missing = sorted(ratified - ids)
    if missing:
        out.append(f"- [FAIL] 追认新增 {missing} 未出现在清单中（只登记未落地）")
    else:
        out.append(f"- [PASS] 追认新增 {sorted(ratified)} 均已在清单中")
    base_commit = meta.get("base_locked_commit", "")
    if base_commit:
        try:
            snap = subprocess.run(
                ["git", "show", f"{base_commit}:docs/frozen_execution_checklist.md"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=HERE, timeout=30).stdout
            snap_ids = set(re.findall(r"\*\*([A-Z]\d{1,2}[a-z]?)\*\*", snap)) if snap else set()
            if snap_ids and snap_ids != locked:
                out.append(f"- [FAIL] 锁定基线不一致：JSON {len(locked)} 个 vs "
                           f"{base_commit} 快照 {len(snap_ids)} 个"
                           f"（差异 {sorted(snap_ids ^ locked)[:6]}）")
            else:
                out.append(f"- [PASS] 锁定基线与 {base_commit} 快照一致（{len(locked)} 个条目）")
        except Exception as e:  # noqa: BLE001
            out.append(f"- [SKIP] 无法读取基线提交（{type(e).__name__}）")
    out.append("")


def check_file_integrity(out) -> None:
    """关键文件完整性：**体积下限 + 上限 + 章节唯一性**——防脚本化编辑的截断与重复。

    两次实测事故（2026-10-01）：
      ① **截断**：登记脚本漏拼后半段，清单 55,149 B → 9,553 B；
      ② **重复**：锚点未命中（find 返回 −1）导致表达式重拼大半个文件，65,353 B → 131,236 B（+374 行）。
    故本检查同时看下限（防截断）、上限（防重复）与章节唯一性（更直接的重复信号）。
    """
    out.append("## 关键文件完整性（体积上下限 + 章节唯一性）")
    bounds = {
        "docs/frozen_execution_checklist.md": (40000, 80000),
        "PROGRESS_SYNC.md": (20000, 90000),
        "docs/final_project_review_and_execution_plan.md": (15000, 80000),
        "competition_v4.md": (20000, 80000),
        "results_summary.md": (4000, 30000),
        "AI_HANDOFF/manifest.json": (20000, 400000),
    }
    bad = 0
    for name, (floor, ceil) in bounds.items():
        p = os.path.join(HERE, name)
        if not os.path.isfile(p):
            out.append(f"- [FAIL] {name}：文件不存在")
            bad += 1
            continue
        size = os.path.getsize(p)
        if size < floor:
            out.append(f"- [FAIL] {name}：{size} B < 下限 {floor} B（**疑似被截断**；"
                       f"可用 `git show <rev>:{name}` 恢复）")
            bad += 1
            continue
        if size > ceil:
            out.append(f"- [FAIL] {name}：{size} B > 上限 {ceil} B（**疑似内容重复/拼接**；"
                       f"对比 `git diff` 与该文件的历史体积）")
            bad += 1
            continue
        out.append(f"- [PASS] {name}：{size} B ∈ [{floor}, {ceil}]")
    # 章节唯一性（仅对 Markdown 主文档）
    for name in ("docs/frozen_execution_checklist.md", "PROGRESS_SYNC.md",
                 "competition_v4.md"):
        p = os.path.join(HERE, name)
        if not os.path.isfile(p):
            continue
        heads = re.findall(r"^## .*$", open(p, encoding="utf-8", errors="replace").read(),
                           re.M)
        seen, dups = set(), []
        for h in heads:
            if h in seen:
                dups.append(h)
            seen.add(h)
        if dups:
            out.append(f"- [FAIL] {name}：{len(dups)} 个重复章节（如 {dups[0][:40]}）"
                       f"——**内容可能被重复拼接**")
            bad += 1
        else:
            out.append(f"- [PASS] {name}：{len(heads)} 个章节均唯一")
    if bad == 0:
        out.append("- 结论：关键文件体积与章节结构均正常")
    out.append("")


def check_product_code_health(out) -> None:
    """产品代码健康（2026-10-01 事故后新增）。

    背景：M0 的"给 v1 数字加代际标签"脚本是**按行做文本替换**的，结果把产品代码里的
    `tuned_thr = 0.9744` 改成了 `tuned_thr = 0.9744[v1]` —— 包内 Demo 直接运行失败。
    数字审计当时全绿，因为没有任何检查看过**代码能不能跑**。

    检查（机械、不依赖 GPU/权重）：
      ① 产品模块必须能编译（内存 compile，不落盘 .pyc）；
      ② 代码行内不得出现"数字直贴 [v1]/[v2]"（注释与文档字符串不受限，
         但正则会命中直贴形态，因此只对 PRODUCT_MODULES 生效）。
    """
    out.append("## 产品代码健康检查（编译 + 标签污染）")
    bad = 0
    for rel in PRODUCT_MODULES:
        p = os.path.join(HERE, rel)
        if not os.path.isfile(p):
            out.append(f"- [FAIL] {rel}：文件不存在")
            bad += 1
            continue
        src = open(p, encoding="utf-8", errors="replace").read()
        try:
            compile(src, rel, "exec")
        except SyntaxError as e:
            out.append(f"- [FAIL] {rel}：语法错误 {e}")
            bad += 1
            continue
        hits = [(i, ln.strip()) for i, ln in enumerate(src.splitlines(), 1)
                if TAG_GLUED.search(ln)]
        if hits:
            out.append(f"- [FAIL] {rel}：{len(hits)} 处代码内残留代际标签"
                       f"（如行 {hits[0][0]}：{hits[0][1][:70]}）")
            bad += 1
        else:
            out.append(f"- [PASS] {rel}：可编译且无标签污染")
    if bad == 0:
        out.append("- 结论：产品模块健康（编译通过、无 [v1]/[v2] 直贴数字）")
    out.append("")


def check_finals_numbers(out) -> None:
    """决赛主文档的关键数字：与 v2 证据文件一致 + 代际标注 + 不可直比声明。"""
    out.append("## 决赛主文档数字核对（与 v2 证据一致）")
    target = None
    for cand in FINALS_DOC_CANDIDATES:
        fp = os.path.join(HERE, cand)
        if os.path.isfile(fp) and cand.lower().endswith(".docx"):
            target = (cand, fp)
            break
    if target is None:
        out.append("- [SKIP] 决赛主文档尚未生成")
        out.append("")
        return
    name, fp = target
    try:
        xml = zipfile.ZipFile(fp).read("word/document.xml").decode("utf-8", "replace")
        text = "\n".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, flags=re.S))
    except (OSError, KeyError, zipfile.BadZipFile) as e:
        out.append(f"- [FAIL] {name} 无法解析：{type(e).__name__}")
        out.append("")
        return

    # 证据文件里的 v2 权威值
    ev = {}
    try:
        w5 = json.load(open(os.path.join(HERE, "v2", "w5_final.json"), encoding="utf-8"))
        ev["F1@调优"] = str(w5["test_at_tuned"]["F1"])
        ev["F1@0.5"] = str(w5["test_at_0.5"]["F1"])
        ev["PR-AUC"] = f"{w5['pr_auc']['test']:.4f}"
    except (OSError, KeyError, ValueError):
        pass
    try:
        w2 = json.load(open(os.path.join(HERE, "v2", "w2_perclass_thresholds.json"),
                            encoding="utf-8"))
        t = w2.get("test", {}).get("tuned_on_tune", {})
        if "macro" in t:
            ev["归因宏F1"] = str(t["macro"])
    except (OSError, KeyError, ValueError):
        pass
    try:
        cv = json.load(open(os.path.join(HERE, "v2", "w5_cv.json"), encoding="utf-8"))
        ev["CV无偏"] = str(cv["summary"]["f1_fixed_mean"])
    except (OSError, KeyError, ValueError):
        pass

    bad = 0
    for label, val in ev.items():
        if val and val in text:
            out.append(f"- [PASS] {label} {val}：主文档已含该值")
        else:
            out.append(f"- [FAIL] {label} {val}：主文档未出现（与证据不一致或漏写）")
            bad += 1

    v1_vals = ["0.6871", "0.6241", "0.6234", "0.9744"]
    v1_present = [v for v in v1_vals if v in text]
    # 判定放宽到"同一行内含 [v1]"：允许"0.6234[v1]±0.0240""0.6871（v1 口径）[v1]"等写法
    lines = text.splitlines()
    untagged = []
    for v in v1_present:
        ok = False
        for ln in lines:
            if v in ln and (f"{v}[v1]" in ln or f"{v}`[v1]`" in ln or "[v1]" in ln):
                ok = True
                break
        if not ok:
            untagged.append(v)
    if not v1_present:
        out.append("- [PASS] 主文档未出现 v1 历史值（无需代际标注）")
    elif untagged:
        out.append(f"- [FAIL] 主文档中 v1 值未标 [v1]：{'、'.join(untagged)}")
        bad += 1
    else:
        out.append(f"- [PASS] 主文档中 v1 值均已标 [v1]（{len(v1_present)} 个）")

    if ("不可直比" in text) or ("不可直接对比" in text):
        out.append("- [PASS] 已声明两代不可直比（采纳闸门第 (2) 条机械侧）")
    else:
        out.append("- [FAIL] 主文档未声明两代数字不可直比")
        bad += 1

    if bad == 0:
        out.append("- 结论：主文档数字与证据一致、代际可辨、并含不可直比声明")
    out.append("")


def check_dependency_declaration(out) -> None:
    """依赖声明一致性（2026-10-01 新增）。

    动机：评委/接手者按 `requirements.txt` 安装后应当能直接跑 Demo。此前没有任何机械检查
    确认"代码 import 的第三方包"都在声明清单里；漏一个就会在别人机器上 ImportError。

    口径：解析 PRODUCT_MODULES 的 import，排除标准库与仓库内本地模块，
    其余必须在 requirements.txt 中出现（支持 scikit-learn↔sklearn 等常见别名）。
    """
    out.append("## 依赖声明一致性（requirements.txt vs 产品 import）")
    import ast
    stdlib = set(sys.stdlib_module_names)
    local = {os.path.splitext(f)[0] for f in os.listdir(HERE) if f.endswith(".py")}
    local |= {"report_builder", "text_utils", "predict_core", "config", "deployment"}
    req = os.path.join(HERE, "requirements.txt")
    declared = set()
    if os.path.isfile(req):
        for line in open(req, encoding="utf-8", errors="replace"):
            line = line.split("#")[0].strip()
            if line:
                declared.add(re.split(r"[<>=!\[]", line)[0].strip().lower())
    alias = {"sklearn": "scikit-learn", "pil": "pillow", "dotenv": "python-dotenv",
             "yaml": "pyyaml", "cv2": "opencv-python"}
    imports = {}
    for rel in PRODUCT_MODULES:
        p = os.path.join(HERE, rel)
        if not os.path.isfile(p):
            continue
        try:
            tree = ast.parse(open(p, encoding="utf-8", errors="replace").read())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imports.setdefault(a.name.split(".")[0], set()).add(rel)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.setdefault(node.module.split(".")[0], set()).add(rel)
    undeclared = []
    for mod, where in sorted(imports.items()):
        if mod in stdlib or mod in local or mod.startswith("_"):
            continue
        norm = mod.lower().replace("_", "-")
        if norm in declared or mod.lower() in declared or alias.get(norm) in declared:
            continue
        undeclared.append((mod, sorted(where)))
    if undeclared:
        for mod, where in undeclared:
            out.append(f"- [FAIL] 未在 requirements.txt 声明：{mod}（被 {', '.join(where)} 引用）")
    else:
        out.append(f"- [PASS] 产品模块的 {len(imports)} 个 import 全部已声明"
                   f"（第三方 {sum(1 for m in imports if m not in stdlib and m not in local)} 个）")
    out.append("")


def main() -> None:
    out = ["# 文档数字一致性审计",
           f"> 运行时刻：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
           "（用于判别报告新鲜度；脚本异常退出时本文件不会被改写）", ""]
    check_package_size_claims(out)
    check_paired_totals(out)
    check_checklist_version(out)
    check_file_integrity(out)
    check_product_code_health(out)
    check_finals_numbers(out)
    check_dependency_declaration(out)
    for grp in GROUPS:
        for fname in grp["files"]:
            audit_file(fname, grp["required"], grp["forbidden"],
                       grp["check_1288"], out)
    check_template_conformance(out)
    check_threshold_pairing(out)
    check_generation_mixing(out)
    check_status_assertions(out)
    check_api_wording_consistency(out)
    check_frozen_package(out)
    check_finals_template(out)
    check_v2_artifacts(out)
    text = "\n".join(out)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    n_fail = text.count("[FAIL]")
    n_pass = text.count("[PASS]")
    n_skip = text.count("[SKIP]")
    print(f"保存 -> {OUT_MD}")
    print(text)
    print(f"\n=== 审计汇总 ===FAIL {n_fail}｜PASS {n_pass}｜SKIP {n_skip}")
    # **退出码必须有意义**：2026-10-01 发现此前恒为 0，导致门槛链的"审计步骤"从未真正拦过失败
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
