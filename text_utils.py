# -*- coding: utf-8 -*-
# text_utils.py —— 文本层共享工具（唯一实现处，供 predict_core / Demo / 在线版共用）
#
# E7 非英文显式拒绝：评论中非拉丁字母占比 > 30% 或全无拉丁字母时，
# 视为不支持语种，由调用方显式跳过而非静默判为正常（静默漏报风险修复）。
import re

NON_LATIN_RE = re.compile(
    r"[\u00c0-\u024f\u0370-\u03ff\u0400-\u04ff\u0590-\u05ff"
    r"\u0600-\u06ff\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
LATIN_RE = re.compile(r"[A-Za-z]")


def is_unsupported(text: str) -> bool:
    """非英文评论判定：全无拉丁字母，或非拉丁字母占比 > 30%。"""
    t = text.strip()
    if not t:
        return True
    if LATIN_RE.search(t) is None:
        return True
    letters = sum(ch.isalpha() for ch in t)
    if letters == 0:
        return False
    return len(NON_LATIN_RE.findall(t)) / letters > 0.3
