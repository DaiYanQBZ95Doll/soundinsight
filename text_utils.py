# -*- coding: utf-8 -*-
# text_utils.py —— 文本层共享工具（唯一实现处，供 predict_core / Demo / 在线版共用）
#
# E7 语种过滤（**真实边界，2026-10-01 实测更正**）：判据是「非拉丁字母占比 > 30% 或全无拉丁字母」。
#   ✔ 被拒绝：中文／日文／韩文／西里尔／希腊／阿拉伯／希伯来等**非拉丁字母文本**；
#   ✘ **不被拒绝**：德文／法文／西班牙文／印尼文等**拉丁字母语言**——它们会照常进入判定。
#     即本模块检测的是「非拉丁字母」，**不是**「非英文」；后者需真正的语种识别（未实现，见附录 B 第 6 条）。
# 由调用方显式跳过而非静默判为正常（静默漏报风险修复）。
import re

NON_LATIN_RE = re.compile(
    r"[\u00c0-\u024f\u0370-\u03ff\u0400-\u04ff\u0590-\u05ff"
    r"\u0600-\u06ff\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
LATIN_RE = re.compile(r"[A-Za-z]")


def is_unsupported(text: str) -> bool:
    """**非拉丁字母文本**判定：全无拉丁字母，或非拉丁字母占比 > 30%。

    注意：拉丁字母语言（德/法/西等）**不会**被判为 True——本函数不是语种识别器。
    """
    t = text.strip()
    if not t:
        return True
    if LATIN_RE.search(t) is None:
        return True
    letters = sum(ch.isalpha() for ch in t)
    if letters == 0:
        return False
    return len(NON_LATIN_RE.findall(t)) / letters > 0.3
