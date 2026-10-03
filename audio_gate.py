# -*- coding: utf-8 -*-
"""音频词汇闸门——**唯一实现**（R32）。标注管线与**产品推理**共用同一份定义。

`RX`：原始闸门（23 个一阶音频词），复赛/决赛标注使用的版本（世代钉死：`v2/split_manifest.json`）。
`RX_EXPANDED`：**候选扩词表**（S6 独立检验的对象）——在原始基础上加入降噪/漏音/失真类表述。
`EXPANDED_EXTRA`：仅列出**新增**的词，便于独立检验与报告。

⚠️ 纪律（S6 预注册）：`RX_EXPANDED` 一经冻结（`docs/s6_preregistration.md` 记哈希与时间戳），
**定稿前不得查看其匹配结果**；每改一次词表，旧验证作废、须用新样本重验。
"""
from __future__ import annotations

import re

KW = ["sound", "audio", "bass", "treble", "clarity", "muffled", "distortion", "static",
      "hiss", "crisp", "muddy", "volume", "pitch", "frequency", "crackling", "popping",
      "sibilance", "tinny", "boomy", "hollow", "scratchy", "buzzing", "rattling"]
RX = re.compile(r"\b(?:" + "|".join(map(re.escape, KW)) + r")\b", re.I)

# S6 新增词（降噪 / 隔音 / 漏音 / 听感类）
EXPANDED_EXTRA = ["noise cancel", "noise cancelling", "noise canceling", "noise cancellation",
                  "noise isolat", "anc", "active noise", "passive noise",
                  "leakage", "leaking", "leaks", "sound leak", "bleed",
                  "soundstage", "sound stage", "imaging", "echo", "echoes",
                  "whistling", "humming", "hum", "clicking", "thumping", "vibration"]
RX_EXPANDED = re.compile(r"\b(?:" + "|".join(map(re.escape, KW + EXPANDED_EXTRA)) + r")\b", re.I)


def gate(text: str) -> bool:
    """原始闸门是否命中（产品预筛与标注口径一致）。"""
    return bool(RX.search(text or ""))


def gate_expanded(text: str) -> bool:
    """扩词表是否命中（S6 检验对象）。"""
    return bool(RX_EXPANDED.search(text or ""))


def is_newly_covered(text: str) -> bool:
    """仅被扩词表覆盖、原始闸门未覆盖——S6 的抽样框定义。"""
    return gate_expanded(text) and not gate(text)
