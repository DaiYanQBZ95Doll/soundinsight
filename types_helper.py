# -*- coding: utf-8 -*-
"""类型/原因预测（本地模型，零 API）：给"非音质差评"打**反馈类型**，
并给"提到声音但说不清"的条目打**不可归因原因**。

模型缺失时返回 None，调用方跳过（优雅降级）。
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "v2", "model_types")
_cache = {}


def available() -> bool:
    return os.path.isdir(MODEL_DIR) and os.path.isfile(
        os.path.join(HERE, "v2", "types_model_manifest.json"))


def predict(texts, device: str = None):
    """→ [{"types": [...], "vague": "..."}]；模型缺失时返回 None。"""
    if not available():
        return None
    if not _cache:
        import torch
        from transformers import (DistilBertForSequenceClassification,
                                  DistilBertTokenizer)
        man = json.load(open(os.path.join(HERE, "v2", "types_model_manifest.json"),
                             encoding="utf-8"))
        dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
        _cache.update({"labels": man["labels"], "types": man["types"], "vague": man["vague"],
                       "tok": DistilBertTokenizer.from_pretrained(MODEL_DIR),
                       "model": DistilBertForSequenceClassification.from_pretrained(
                           MODEL_DIR).to(dev).eval(), "dev": dev})
    import torch
    out = []
    with torch.no_grad():
        for b in range(0, len(texts), 64):
            e = _cache["tok"](texts[b:b + 64], padding=True, truncation=True,
                              max_length=192, return_tensors="pt")
            e = {k: v.to(_cache["dev"]) for k, v in e.items()}
            p = torch.sigmoid(_cache["model"](**e).logits).cpu().numpy()
            for j in range(p.shape[0]):
                types = [_cache["labels"][k] for k in range(len(_cache["labels"]))
                         if p[j, k] >= 0.5 and _cache["labels"][k] in _cache["types"]]
                vcands = [(p[j, k], _cache["labels"][k]) for k in range(len(_cache["labels"]))
                          if _cache["labels"][k] in _cache["vague"]]
                vague = max(vcands)[1] if vcands else "NONE"
                out.append({"types": types, "vague": vague})
    return out


def type_counts(preds):
    """→ {类型: 计数}（多标签计数）。"""
    from collections import Counter
    c = Counter()
    for r in preds or []:
        for t in r["types"]:
            c[t] += 1
    return dict(c.most_common())


def vague_counts(preds):
    from collections import Counter
    return dict(Counter(r["vague"] for r in preds or []).most_common())
