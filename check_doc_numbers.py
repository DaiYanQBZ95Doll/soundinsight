# -*- coding: utf-8 -*-
# 本脚本用于文档数字一致性审计：扫描指定文档，逐项核对红线数字，
# 检测口径违规，输出 number_audit.md。
import hashlib
import os
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
    (r"83\.7", "教师一致性出现在正文（仅允许方法说明/附录）"),
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
]

# 阈值档表：一行内命中两个及以上档的值时，该行必须为每一档写出标签
THRESHOLD_TIERS = {
    "调优(0.9744)": {"labels": ("0.9744", "0.97", "调优"),
                     "values": ("0.6871", "0.687", "66.3", "71.3")},
    "0.5": {"labels": ("0.5", "0.50"), "values": ("0.6241", "47.9", "89.6")},
}

# 代际：v1 = 复赛已提交口径；v2 = 决赛口径（落地后把新指标填进 tokens，检查自动生效）
GEN_TAGS = ("[v1]", "[v2]")
GEN_TOKENS = {
    "v1": ["0.6871", "0.9744", "0.6234", "0.7191", "0.6241", "0.000932"],
    "v2": [],  # 待填：v2 的 F1 / 阈值 / CV 等
}
CURRENT_GEN = os.environ.get("DSH_DOC_GEN", "v1")
GEN_FILES = PAIR_FILES + ["docs/project_full_record.md", "PROGRESS_SYNC.md"]
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
    当前 v2 尚未落地，GEN_TOKENS["v2"] 为空 → 本检查只覆盖 v1（机制就绪，v2 数字一产生
    就自动生效）。当前代由环境变量 DSH_DOC_GEN 指定（默认 v1）。
    """
    out.append(f"## 代际检查（当前代：{CURRENT_GEN}）")
    v2_tokens = GEN_TOKENS.get("v2") or []
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


def main() -> None:
    out = ["# 文档数字一致性审计", ""]
    for grp in GROUPS:
        for fname in grp["files"]:
            audit_file(fname, grp["required"], grp["forbidden"],
                       grp["check_1288"], out)
    check_template_conformance(out)
    check_threshold_pairing(out)
    check_generation_mixing(out)
    check_frozen_package(out)
    check_finals_template(out)
    check_v2_artifacts(out)
    text = "\n".join(out)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"保存 -> {OUT_MD}")
    print(text)


if __name__ == "__main__":
    main()
