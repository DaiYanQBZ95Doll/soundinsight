# -*- coding: utf-8 -*-
"""功能级验证：真的加载模型并调用 single_predict，验证非英文被显式拒绝、英文正常判定。

这是"修好了"的实证，不是静态检查。约需 20–40 秒（加载两个模型）。
"""
from __future__ import annotations

import io
import os
import sys
import contextlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

print("加载 demo_sound_v2（会载入两个模型，请稍候）…")
# 注意：不能用重定向 stdout 的方式静音——模块内会调用 sys.stdout.reconfigure，
# 而 StringIO 没有该方法（首次尝试即因此失败）。直接导入并让加载日志正常输出。
import demo_sound_v2 as demo  # noqa: E402
print("  已加载；模块内 single_predict 可调用")

CASES = [
    # (标签, 文本, 期望是否被拒绝)
    # 判据是「非拉丁字母占比 > 30% 或全无拉丁字母」——**不是**语种识别，
    # 故德/法/西等拉丁字母语言按**已知未测**处理（不拒绝，且这一事实已在附录 B 第 6 条披露）
    ("中文（非拉丁字母 → 应拒绝）", "这款耳机音质很差，低音浑浊，高音刺耳。", True),
    ("日文（非拉丁字母 → 应拒绝）", "このイヤホンの音質は悪いです。", True),
    ("俄文（非拉丁字母 → 应拒绝）", "Звук очень плохой, бас грязный.", True),
    ("英文（应正常判定）", "The bass is muddy and the treble is harsh.", False),
    ("英文好评（应正常判定）", "Battery life is great and the sound is fine.", False),
    ("德文（拉丁字母 → **已知未拒绝**，属披露中的边界）",
     "Der Klang ist schlecht und der Bass ist zu schwach.", False),
]
print("\n=== single_predict 行为矩阵（按真实规则断言）===")
ok = True
for label, text, expect_reject in CASES:
    out = demo.single_predict(text)
    rejected = "不支持的语种" in out
    verdict = "OK  " if rejected == expect_reject else "BAD "
    if rejected != expect_reject:
        ok = False
    print(f"  [{verdict}] {label}")
    print(f"        → {out.strip().splitlines()[0][:88]}")

print(f"\n[结论] {'单条路径行为与文档一致 ✓（含已披露的拉丁语系盲区）' if ok else '**行为与文档不符，需检查**'}")
sys.exit(0 if ok else 1)
