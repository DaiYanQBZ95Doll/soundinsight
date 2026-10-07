# -*- coding: utf-8 -*-
"""世代一致性校验（入链，位置在「构建决赛包」之前）。

病根（round-03 审查，实证盲区）：判别器世代曾在**25 步全绿**时提交，而
`build_finals_content.py` 对该世代命中 0 处——全链没有任何一步校验
「材料描述的模型 == 出厂权重」。本步骤补上这一环。

设计（按审查意见加固）：
  · **世代标识从 `config.json` 读**（`generation_label`），不硬编码——否则下次换型又漏；
  · 三件事各查一遍：
    ① 权重自洽：`model_hashes.json` 登记的哈希 == 实际 `sound_model/model.safetensors`；
    ② config 自述：`config.model_note` 含世代标识；
    ③ 材料同步：面向评委/卖家的材料必须出现**当前**世代标识（缺即 FAIL）。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
# 必须出现当前世代标识的材料（面向评委或卖家）
# 构建输入：真正进入 docx／包的源（门 ④ 只对这些要求提交后再打包）
BUILD_INPUTS = ["build_finals_content.py", "build_finals_appendix.py",
                "build_finals_docx2.py", "build_finals_package.py",
                "make_current_output.py", "report_builder.py",
                "predict_core.py", "soundinsight_agent.py", "audio_gate.py",
                "types_helper.py", "config.json", "README.md", "MODEL_CARD.md",
                "sample_reviews_100.csv", "model_hashes.json"]

MATERIALS = ["build_finals_content.py", "build_finals_appendix.py", "report_builder.py",
             "MODEL_CARD.md", "docs/SUBMISSION_CHECKLIST.md", "docs/split_manifest.md",
             # round-04 Qwen 盲读发现 README 仍写「默认模型＝v1」→ 纳入机械门
             "README.md", "deployment/README.md", "当前输出版本（对照视频）.html"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
    label = cfg.get("generation_label") or ""
    gen = cfg.get("generation") or ""
    bad = []
    if not label:
        bad.append("config.generation_label 缺失（本步骤无法判定世代，属配置错误）")
    if not gen:
        bad.append("config.generation 缺失")

    # ① 权重自洽
    rel = f"{cfg.get('bin_model_dir', 'sound_model')}/model.safetensors"
    want = (json.load(open(os.path.join(HERE, "model_hashes.json"), encoding="utf-8"))
            .get(rel) if os.path.isfile(os.path.join(HERE, "model_hashes.json")) else None)
    actual = sha(os.path.join(HERE, rel)) if os.path.isfile(os.path.join(HERE, rel)) else None
    if not want or not actual:
        bad.append(f"权重或登记缺失：{rel}（登记 {bool(want)}／存在 {bool(actual)}）")
    elif want != actual:
        bad.append(f"权重与登记不符：期望 {want[:16]}… 实际 {actual[:16]}…")

    # ② config 自述
    if label and label not in (cfg.get("model_note") or ""):
        bad.append(f"config.model_note 未出现世代标识「{label}」")

    # ③ 材料同步
    miss = []
    for f in MATERIALS:
        p = os.path.join(HERE, f)
        if not os.path.isfile(p):
            miss.append(f"{f}（文件缺失）")
            continue
        if label not in open(p, encoding="utf-8", errors="replace").read():
            miss.append(f)
    if miss:
        bad.append(f"以下材料未出现当前世代标识「{label}」：{'、'.join(miss)}")


    # ④ 源-产物一致性（R4-6）：生成器/材料源若有未提交改动，产物可能"新于源"
    import subprocess as _sp
    _gens = BUILD_INPUTS
    try:
        _st = _sp.run(["git", "status", "--porcelain", "--", *_gens],
                      cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                      errors="replace").stdout.strip()
    except Exception:  # noqa: BLE001
        _st = ""
    if _st:
        _dirty = [ln[2:].strip() for ln in _st.splitlines() if len(ln) > 3]
        bad.append("**产物可能新于源**：以下生成器/材料源有未提交改动 → "
                   "请先提交再打包（否则重建会静默回退）：" + "、".join(_dirty))
    print("## 世代一致性")
    print(f"- 当前世代：`{gen}`／标识「{label}」｜权重 {rel}")
    if want and actual and want == actual:
        print(f"- 权重哈希自洽 ✓（{actual[:16]}…）")
    if not bad:
        print(f"- 材料同步 ✓（{len(MATERIALS)} 份材料均含世代标识）")
    for b in bad:
        print(f"- [FAIL] {b}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
