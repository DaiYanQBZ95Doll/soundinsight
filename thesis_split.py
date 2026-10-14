# -*- coding: utf-8 -*-
"""论文用**冻结划分**（thesis split）——按内容哈希划分，杜绝行序漂移与人工集污染。

设计要点（每条都来自竞赛期的真实教训）：
  ① 宇宙：**闸门内**评论（任务 T1 定义在闸门内），当前 12,929 条、正例 1,280（v2-LLM 标签）；
  ② **按内容哈希**排序划分，而非按行号——W6 实测：标签文件重建后行序变化会让"同一划分"
     与旧留出集重叠 79.5%（记忆导致虚高）；
  ③ **先去重再划分**（X-25 教训）：归一化文本后去重；
  ④ **排除人工已判条目**：292 条人工金标（含重测样本）一律不进训练/验证，避免评测污染；
  ⑤ 分层 80/10/10（按 v2-LLM 标签），种子固定；
  ⑥ 同时登记 v1 标签（sound_negative）计数，便于三方标签对照。
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 42
CORPUS = "labeled_llm.csv"
SHEETS = ["answer_sheet_p0_accept.md", "answer_sheet_recheck.md",
          "answer_sheet_xcat_accept.md", "answer_sheet_retest.md"]


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().lower())


def h(t: str) -> str:
    return hashlib.sha1(norm(t).encode("utf-8")).hexdigest()


def human_hashes() -> set[str]:
    hs = set()
    for name in SHEETS:
        p = os.path.join(HERE, "docs", "gold_set", name)
        if not os.path.isfile(p):
            continue
        for ln in open(p, encoding="utf-8"):
            s = ln.strip()
            if s.startswith("**原文**"):
                hs.add(h(s.split("**原文**：", 1)[-1]))
    return hs


def main() -> int:
    spec = importlib.util.spec_from_file_location("g", os.path.join(HERE, "audio_gate.py"))
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)

    with open(os.path.join(HERE, CORPUS), encoding="utf-8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    uni = [(i, r) for i, r in enumerate(rows) if g.gate(r["text"])]
    print(f"  语料 {len(rows):,}｜闸门内 {len(uni):,}")

    seen, dedup, dup = set(), [], 0
    for i, r in uni:
        k = h(r["text"])
        if k in seen:
            dup += 1
            continue
        seen.add(k)
        dedup.append((i, r, k))
    print(f"  去重后 {len(dedup):,}（去重移除 {dup}）")

    hh = human_hashes()
    kept = [(i, r, k) for i, r, k in dedup if k not in hh]
    print(f"  排除人工已判 {len(dedup) - len(kept)} 条 → 可用 {len(kept):,}"
          f"（人工集哈希 {len(hh)}）")

    def lab(r, col="sound_negative_llm"):
        return 1 if str(r.get(col)) == "1" else 0

    splits = {"train": [], "val": [], "test": []}
    for cls in (1, 0):
        pool = [(i, r, k) for i, r, k in kept if lab(r) == cls]
        # 以 "种子+哈希" 排序 → 与行序无关（可跨文件重建复现）
        pool.sort(key=lambda x: hashlib.sha1(f"{SEED}:{x[2]}".encode()).hexdigest())
        n = len(pool)
        n_tr, n_va = int(n * 0.8), int(n * 0.1)
        splits["train"] += pool[:n_tr]
        splits["val"] += pool[n_tr:n_tr + n_va]
        splits["test"] += pool[n_tr + n_va:]
    for k in splits:
        splits[k].sort(key=lambda x: x[2])

    stats = {}
    for k, v in splits.items():
        p2 = sum(1 for _i, r, _h in v if lab(r) == 1)
        p1 = sum(1 for _i, r, _h in v if lab(r, "sound_negative") == 1)
        stats[k] = {"n": len(v), "pos_v2llm": p2, "pos_v1": p1,
                    "rate_v2llm": round(p2 / max(1, len(v)), 4)}
        print(f"  {k:5s} n={len(v):5d}｜v2-LLM 正例 {p2:4d}（{p2/max(1,len(v))*100:.2f}%）"
              f"｜v1 标签正例 {p1:4d}")

    out = {"seed": SEED, "universe": "gate-inside（audio_gate）", "corpus": CORPUS,
           "corpus_sha256": hashlib.sha256(
               open(os.path.join(HERE, CORPUS), "rb").read()).hexdigest(),
           "label_columns": {"primary": "sound_negative_llm", "secondary_v1": "sound_negative"},
           "dedupe": {"removed": dup}, "excluded_human": len(dedup) - len(kept),
           "human_hashes": sorted(hh), "stats": stats,
           "row_index": {k: [i for i, _r, _h in v] for k, v in splits.items()},
           "content_hash": {k: [x[2] for x in v] for k, v in splits.items()},
           "note": ("按内容哈希排序划分（与行序无关）；已排除人工已判条目；"
                    "训练/验证/测试三侧内容哈希互不相交")}
    json.dump(out, open(os.path.join(HERE, "v2", "thesis_split.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # 自检：三侧哈希交集必须为空
    tr, va, te = (set(out["content_hash"][k]) for k in ("train", "val", "test"))
    inter = (tr & va) | (tr & te) | (va & te)
    print(f"  自检：三侧内容哈希交集 {len(inter)}（应为 0）")
    if inter or not tr:
        print("  [FAIL] 划分自检未通过")
        return 1
    print("[写出] v2/thesis_split.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
