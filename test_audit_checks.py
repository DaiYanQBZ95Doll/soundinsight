# -*- coding: utf-8 -*-
# test_audit_checks.py —— 审计检查项的负向测试（证明坏输入会被拒绝，而非只报 PASS）
#
# 运行：python test_audit_checks.py      （无需 pytest；pytest 也可收集 test_* 函数）
# 覆盖：口径配对（跨阈值档）、代际混用、提交包冻结、决赛模板 5.2 百炼栏事实、v2 产物登记。
import os
import sys
import shutil
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import check_doc_numbers as m  # noqa: E402


class local_tempdir:
    """工作区内临时目录：只 makedirs/rmtree，**不调用 chmod**（沙箱禁止 chmod，
    否则 tempfile.TemporaryDirectory 会抛 WinError 5）。"""

    def __init__(self):
        self.path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "_tmp_selftest", "run")

    def __enter__(self):
        shutil.rmtree(self.path, ignore_errors=True)
        os.makedirs(self.path, exist_ok=True)
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)
        return False

PASSED, FAILED = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append(name)
    print(f"  [{'OK  ' if cond else 'BAD '}] {name}{(' — ' + detail) if detail else ''}")


def run_with_lines(fn, lines, **patch):
    """用伪造文件内容调用某个检查函数，返回输出文本。"""
    old_read, old_pair = m.read_file, getattr(m, "PAIR_FILES", None)
    m.read_file = lambda name: (lines, "/fake/" + name)
    if old_pair is not None:
        m.PAIR_FILES = ["fake.md"]
    saved = {k: getattr(m, k) for k in patch}
    for k, v in patch.items():
        setattr(m, k, v)
    out = []
    try:
        fn(out)
    finally:
        m.read_file, m.PAIR_FILES = old_read, old_pair
        for k, v in saved.items():
            setattr(m, k, v)
    return "\n".join(out)


print("== 1. 口径配对检查（跨阈值档）==")
bad_line = "F1=0.6871（阈值 0.97），召回率 89.6%，精确率 47.9%"
txt = run_with_lines(m.check_threshold_pairing, [bad_line + "\n"])
check("并排两档且未标阈值 → FAIL", "[FAIL]" in txt, txt.splitlines()[-1][:80])

good_line = ("阈值 0.9744：F1 0.6871、精确率 66.3%、召回率 71.3%；"
             "阈值 0.5：F1 0.6241、精确率 47.9%、召回率 89.6%")
txt = run_with_lines(m.check_threshold_pairing, [good_line + "\n"])
check("两档齐标 → 不 FAIL", "[FAIL]" not in txt)

single = "阈值 0.9744 下的 F1 为 0.6871（同档精确率 66.3%）"
txt = run_with_lines(m.check_threshold_pairing, [single + "\n"])
check("单档 → 不 FAIL", "[FAIL]" not in txt)

print("\n== 2. 代际混用检查 ==")
saved_v2 = m.GEN_TOKENS["v2"]
m.GEN_TOKENS["v2"] = ["0.7412"]
try:
    mixed = "v1 为 0.6871，v2 为 0.7412\n"
    txt = run_with_lines(m.check_generation_mixing, [mixed])
    check("两代数字无标签 → FAIL", "[FAIL]" in txt)
    tagged = "v1 为 0.6871 [v1]，v2 为 0.7412 [v2]\n"
    txt = run_with_lines(m.check_generation_mixing, [tagged])
    check("带 [v1]/[v2] 标签 → 不 FAIL", "[FAIL]" not in txt)
finally:
    m.GEN_TOKENS["v2"] = saved_v2

print("\n== 3. 提交包冻结校验 ==")
with local_tempdir() as td:
    name = "包.zip"
    zp = os.path.join(td, name)
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("a.txt", "hello")
    import hashlib
    real = hashlib.sha256(open(zp, "rb").read()).hexdigest()
    old_here, old_name, old_sha = m.HERE, m.FROZEN_ZIP_NAME, m.FROZEN_ZIP_SHA
    m.HERE, m.FROZEN_ZIP_NAME = td, name
    with open(os.path.join(td, "hashes.txt"), "w", encoding="utf-8") as f:
        f.write(f"{os.path.getsize(zp)} B  sha256:{real}  {name}\n")
    m.FROZEN_ZIP_SHA = real  # 冻结值 = 该临时包的哈希（模拟"记录与磁盘都等于已提交版本"）
    out = []
    m.check_frozen_package(out)
    check("磁盘与记录均等于冻结值 → PASS", "[PASS]" in "\n".join(out)
          and "[FAIL]" not in "\n".join(out))
    m.FROZEN_ZIP_SHA = "0" * 64  # 模拟"包被重打、与已提交版本不一致"
    out = []
    m.check_frozen_package(out)
    check("包被覆盖（哈希与冻结值不符）→ FAIL", "[FAIL]" in "\n".join(out))
    m.HERE, m.FROZEN_ZIP_NAME, m.FROZEN_ZIP_SHA = old_here, old_name, old_sha

print("\n== 4. 决赛模板合规（5.2 百炼栏事实）==")


def make_docx(path: str, text: str) -> None:
    xml = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="x"><w:body>'
           + "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>"
                     for t in text.split("\n")) + "</w:body></w:document>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)


sections = "\n".join(f"{n}、{s}" for n, s in zip(
    "一二三四五六七八九", m.TEMPLATE_SECTIONS_FINALS))
with local_tempdir() as td:
    old_here, old_cands = m.HERE, m.FINALS_DOC_CANDIDATES
    m.HERE = td
    doc = "更新世界的锋芒_SoundInsight_决赛入围定稿作品.docx"
    m.FINALS_DOC_CANDIDATES = [doc]
    good = sections + "\n团队名称：更新世界的锋芒\nhttps://gitcode.com/x/y\n" \
        "qwen3.7-plus｜跨 LLM 对照（评审用途）｜阿里云百炼 Token Plan API\n"
    make_docx(os.path.join(td, doc), good)
    out = []
    m.check_finals_template(out)
    check("模板齐备 + 百炼填真实调用 → 不 FAIL", "[FAIL]" not in "\n".join(out))
    fake = sections + "\n团队名称：更新世界的锋芒\nhttps://gitcode.com/x/y\n" \
        "阿里云百炼：未使用\n"
    make_docx(os.path.join(td, doc), fake)
    out = []
    m.check_finals_template(out)
    check("模板里假称百炼未使用 → FAIL", "[FAIL]" in "\n".join(out))
    m.HERE, m.FINALS_DOC_CANDIDATES = old_here, old_cands

print("\n== 5. v2 可核验产物 ==")
with local_tempdir() as td:
    old_here = m.HERE
    m.HERE = td
    os.makedirs(os.path.join(td, "v2"))
    open(os.path.join(td, "v2", "model.bin"), "wb").write(b"weights")
    open(os.path.join(td, "v2", "threshold.json"), "w").write("{}")
    open(os.path.join(td, "v2", "eval.txt"), "w").write("out")
    open(os.path.join(td, "v2", "MODEL_CARD_v2.md"), "w").write("# v2")
    import json
    reg = os.path.join(td, "v2", "v2_artifacts.json")
    json.dump({"model_sha256": {"v2/model.bin": "deadbeef"},  # 故意写错
               "threshold_json": {"path": "v2/threshold.json", "sha256": ""},
               "train_command": "python train.py", "eval_outputs": ["v2/eval.txt"],
               "model_card": "v2/MODEL_CARD_v2.md"}, open(reg, "w"))
    out = []
    m.check_v2_artifacts(out)
    check("模型哈希不符 → FAIL", "[FAIL]" in "\n".join(out))
    json.dump({"model_sha256": {}, "threshold_json": {"path": "v2/threshold.json"},
               "train_command": "python train.py", "eval_outputs": ["v2/eval.txt"],
               "model_card": "v2/MODEL_CARD_v2.md"}, open(reg, "w"))
    out = []
    m.check_v2_artifacts(out)
    check("登记齐全 → PASS", "[PASS]" in "\n".join(out))
    m.HERE = old_here

print("\n== 6. 否定性状态断言检查（D7）==")
# 6a：高危否定断言且无日期/来源 → FAIL
txt = run_with_lines(m.check_status_assertions,
                     ["- 百炼模型未使用，因此 5.2 栏可留空\n"],
                     STATUS_FILES=["fake.md"])
check("否定断言无日期/来源 → FAIL", "[FAIL]" in txt, txt.splitlines()[-1][:70])
# 6b：同一断言带核验日期 → PASS
txt = run_with_lines(m.check_status_assertions,
                     ["- 百炼模型未使用（2026-09-30 实测，见 PROGRESS_SYNC.md）\n"],
                     STATUS_FILES=["fake.md"])
check("否定断言带日期/来源 → PASS", "[FAIL]" not in txt and "[PASS]" in txt)
# 6c：历史/勘误语境豁免 → PASS
txt = run_with_lines(m.check_status_assertions,
                     ["- 曾写\"百炼未使用\"，该表述属过时状态，已更正\n"],
                     STATUS_FILES=["fake.md"])
check("历史/勘误语境 → 豁免 PASS", "[FAIL]" not in txt)
# 6d：如实披露"未开展"不触发（不属状态断言范围）
txt = run_with_lines(m.check_status_assertions,
                     ["- 未开展用户验证（无渠道，详见 v4 §9.1）\n"],
                     STATUS_FILES=["fake.md"])
check("诚实披露未开展 → 不触发", "[FAIL]" not in txt)

print("\n== N. 清单版本一致性检查（v1.5 附加条款②）==")


def _fake_version_env(lines, meta):
    """把 m.HERE 指向带 docs/checklist_version.json 的临时目录，并伪造清单内容。"""
    import json as _json
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_selftest", "ver")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "docs"), exist_ok=True)
    with open(os.path.join(root, "docs", "checklist_version.json"), "w",
              encoding="utf-8") as fh:
        _json.dump(meta, fh, ensure_ascii=False)
    return root


def run_version_check(lines, meta):
    root = _fake_version_env(lines, meta)
    old_here, old_read = m.HERE, m.read_file
    m.HERE = root
    m.read_file = lambda name: (lines, os.path.join(root, name))
    out = []
    try:
        m.check_checklist_version(out)
    finally:
        m.HERE, m.read_file = old_here, old_read
        shutil.rmtree(root, ignore_errors=True)
    return "\n".join(out)


META = {"current_version": "v9.9", "locked_item_ids": ["A1"], "ratified_additions": ["B2"],
        "base_locked_commit": ""}

txt = run_version_check(["版本 **v9.9** 为基准\n", "| **A1** | x |\n", "| **C3** | 越权新增 |\n"], META)
check("未登记条目 → FAIL", "[FAIL]" in txt and "C3" in txt, txt.split("FAIL")[-1][:60])

txt = run_version_check(["版本 **v9.9** 为基准\n", "| **A1** | x |\n", "| **B2** | 追认新增 |\n"], META)
check("锁定∪追认 → 不 FAIL", "[FAIL]" not in txt)

txt = run_version_check(["版本 **v8.8** 为基准\n", "| **A1** | x |\n"], META)
check("版本未声明 → FAIL", "[FAIL]" in txt)

META2 = dict(META, ratified_additions=["B2", "C9"])
txt = run_version_check(["版本 **v9.9** 为基准\n", "| **A1** | x |\n"], META2)
check("追认新增未落地 → FAIL", "[FAIL]" in txt and "C9" in txt)

print(f"\n结果：{len(PASSED)} 项通过，{len(FAILED)} 项失败")
if FAILED:
    print("失败项：" + "、".join(FAILED))
sys.exit(1 if FAILED else 0)
