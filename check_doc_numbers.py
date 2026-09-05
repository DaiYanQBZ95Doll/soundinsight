# -*- coding: utf-8 -*-
# 本脚本用于文档数字一致性审计：扫描指定文档，逐项核对红线数字，
# 检测口径违规，输出 number_audit.md。
import os
import re
import sys

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
    (r"47\.9", ["47.9", "0.479"], "精确率"),
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

GROUPS = [
    {"files": ["competition_v3.txt", "competition_v4.md", "README.md",
               "QWEN_HANDOFF.md", "ppt_text_dump.md"],
     "required": CORE_REQUIRED, "forbidden": CORE_FORBIDDEN, "check_1288": True},
    {"files": ["llm_baseline.md"],
     "required": LLM_REQUIRED, "forbidden": [], "check_1288": False},
    {"files": ["qna_preparation.md"],
     "required": QNA_REQUIRED, "forbidden": QNA_FORBIDDEN, "check_1288": False},
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


def main() -> None:
    out = ["# 文档数字一致性审计", ""]
    for grp in GROUPS:
        for fname in grp["files"]:
            audit_file(fname, grp["required"], grp["forbidden"],
                       grp["check_1288"], out)
    text = "\n".join(out)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"保存 -> {OUT_MD}")
    print(text)


if __name__ == "__main__":
    main()
