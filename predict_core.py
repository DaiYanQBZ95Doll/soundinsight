# -*- coding: utf-8 -*-
# predict_core.py — SoundInsight 共享推理核心（soundinsight_agent / api_server /
# benchmark 共用同一套加载与推理路径，保证口径一致）。
#
# E7 非英文显式拒绝：评论中非拉丁字母占比 > 30% 或全无拉丁字母时，
# 返回 is_unsupported=True 且不给出音质判定（静默漏报风险修复）。
import json
import os
import re
import sys

import numpy as np
import torch
from transformers import (DistilBertForSequenceClassification,
                          DistilBertTokenizer)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
    CFG = json.load(f)
BIN_MODEL = os.path.join(HERE, CFG["bin_model_dir"])
ML_MODEL = os.path.join(HERE, CFG["multi_label_dir"])
THR_FILE = os.path.join(HERE, CFG["threshold_file"])
ISSUE_FILE = os.path.join(HERE, CFG["issue_labels_file"])
BATCH = int(CFG["batch_size"])
MAX_LEN = int(CFG["max_len"])

# 非拉丁书写系统字符（西里尔/希腊/中日韩/阿拉伯/希伯来等）
NON_LATIN_RE = re.compile(
    r"[\u00c0-\u024f\u0370-\u03ff\u0400-\u04ff\u0590-\u05ff"
    r"\u0600-\u06ff\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
LATIN_RE = re.compile(r"[A-Za-z]")

_state = None


def is_unsupported(text: str) -> bool:
    """非英文评论显式拒绝：全无拉丁字母，或非拉丁字母占比 > 30%。"""
    t = text.strip()
    if not t:
        return True
    if LATIN_RE.search(t) is None:
        return True
    letters = sum(ch.isalpha() for ch in t)
    if letters == 0:
        return False
    return len(NON_LATIN_RE.findall(t)) / letters > 0.3


def load(device: str = None):
    """加载模型（进程内缓存）。device: 'cuda'|'cpu'|None(自动)。"""
    global _state
    if _state is not None and (device is None or _state["device_name"] == device):
        return _state
    dev = (device if device in ("cuda", "cpu")
           else ("cuda" if torch.cuda.is_available() else "cpu"))
    tok = DistilBertTokenizer.from_pretrained(BIN_MODEL)
    bin_model = DistilBertForSequenceClassification.from_pretrained(
        BIN_MODEL).to(dev)
    bin_model.eval()
    with open(THR_FILE, encoding="utf-8") as f:
        thr = float(json.load(f)["threshold"])
    ml_model = DistilBertForSequenceClassification.from_pretrained(
        ML_MODEL).to(dev)
    ml_model.eval()
    with open(ISSUE_FILE, encoding="utf-8") as f:
        issue_info = json.load(f)
    _state = {"device": torch.device(dev), "device_name": dev,
              "tok": tok, "bin": bin_model, "thr": thr,
              "ml": ml_model, "issues": issue_info}
    return _state


def _bin_probs(model, tok, texts, device):
    probs = []
    with torch.no_grad():
        for b in range(0, len(texts), BATCH):
            enc = tok(texts[b:b + BATCH], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            probs.append(torch.softmax(model(**enc).logits, -1)
                         [:, 1].cpu().numpy())
    return np.concatenate(probs)


def _ml_sigmoid(model, tok, texts, device):
    out = []
    with torch.no_grad():
        for b in range(0, len(texts), BATCH):
            enc = tok(texts[b:b + BATCH], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            out.append(torch.sigmoid(model(**enc).logits).cpu().numpy())
    return np.vstack(out)


def predict_batch(texts, device: str = None):
    """批量推理。返回与输入等长的结果列表，每项为 dict：
    {text, is_unsupported, prob, pred, issues, issue_probs}
    不支持/空文本：prob=None, pred=None, issues=[]。"""
    st = load(device)
    texts = [str(t) for t in texts]
    flags = [is_unsupported(t) for t in texts]
    supported = [t for t, f in zip(texts, flags) if not f]
    probs_map, ml_map = {}, {}
    if supported:
        p = _bin_probs(st["bin"], st["tok"], supported, st["device"])
        probs_map = {t: float(v) for t, v in zip(supported, p)}
        pos_texts = [t for t, v in zip(supported, p) if v >= st["thr"]]
        if pos_texts:
            ml = _ml_sigmoid(st["ml"], st["tok"], pos_texts, st["device"])
            names = st["issues"]["names"]
            ml_map = {t: {"issues": [names[k] for k in range(len(names))
                                     if ml[i, k] >= 0.5],
                          "issue_probs": {names[k]: float(ml[i, k])
                                          for k in range(len(names))}}
                      for i, t in enumerate(pos_texts)}
    results = []
    for t, f in zip(texts, flags):
        if f:
            results.append({"text": t, "is_unsupported": True, "prob": None,
                            "pred": None, "issues": [], "issue_probs": {}})
            continue
        prob = probs_map[t]
        pred = int(prob >= st["thr"])
        if pred:
            issues = ml_map.get(t, {}).get("issues", [])
            issue_probs = ml_map.get(t, {}).get("issue_probs", {})
        else:
            issues, issue_probs = [], {}
        results.append({"text": t, "is_unsupported": False, "prob": prob,
                        "pred": pred, "issues": issues,
                        "issue_probs": issue_probs})
    return results


def predict_single(text, device: str = None):
    """单条推理，返回一个结果 dict。"""
    return predict_batch([text], device)[0]
