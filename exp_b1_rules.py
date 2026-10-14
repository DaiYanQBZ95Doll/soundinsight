# -*- coding: utf-8 -*-
"""B1 基线：规则/词典（音频词汇闸门已知 ∧ 负面词典 ∧ 否定处理）。

定位：**下界基线**——不需要训练，用于回答"规则能做到多少"。
输出：v2/exp_b1_{val,test}.json（{row_index: prob}），prob 由命中数线性映射到 (0,1) 以便算 AUC-PR。
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

NEG = [
    "bad", "poor", "poorly", "terrible", "terribly", "awful", "horrible", "horrendous",
    "disappoint", "disappointing", "disappointed", "useless", "garbage", "trash",
    "muffled", "muddy", "tinny", "harsh", "sibilant", "distort", "distorted", "distortion",
    "static", "staticy", "crackle", "crackling", "hiss", "hissing", "buzz", "buzzing",
    "rattle", "rattling", "noisy", "noise", "interference", "cut out", "cutting out",
    "no bass", "lacks bass", "lack of bass", "no treble", "weak bass", "flat sound",
    "not loud", "too quiet", "volume", "mute", "muted", "unclear", "not clear",
    "can't hear", "cannot hear", "hard to hear", "echo", "echoes", "wobble",
]
NEG_RE = re.compile("|".join(re.escape(w) for w in NEG), re.I)
NEG_WORDS = {w: re.compile(re.escape(w), re.I) for w in NEG}
NEGATORS = re.compile(r"\b(no|not|never|without|isn't|wasn't|aren't|don't|doesn't|didn't)\b",
                      re.I)


def score(text: str) -> float:
    """命中数 → (0,1)；否定前缀（"no noise"）不计入。返回伪概率。"""
    t = text or ""
    hits = 0
    for w, rx in NEG_WORDS.items():
        for m in rx.finditer(t):
            pre = t[max(0, m.start() - 18):m.start()]
            if NEGATORS.search(pre):
                continue
            hits += 1
            break
    if hits == 0:
        return 0.05
    return min(0.95, 0.35 + 0.15 * (hits - 1) + 0.2)


def main() -> int:
    sp = json.load(open(os.path.join(HERE, "v2", "thesis_split.json"), encoding="utf-8"))
    texts = {}
    with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            texts[i] = r["text"]
    for part in ("val", "test"):
        idx = sp["row_index"][part]
        pred = {str(i): score(texts[i]) for i in idx}
        outp = os.path.join(HERE, "v2", f"exp_b1_{part}.json")
        json.dump(pred, open(outp, "w", encoding="utf-8"))
        fire = sum(1 for v in pred.values() if v >= 0.5)
        print(f"  [B1] {part}: n={len(pred)}｜触发 {fire}（{fire/len(pred)*100:.1f}%）→ "
              f"{os.path.relpath(outp, HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
