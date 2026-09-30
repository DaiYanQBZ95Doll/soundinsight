# -*- coding: utf-8 -*-
"""W13（A-尽力）：关键词漏检率——**按 label_v3.py 的真实词表与词边界**测量。

关键更正（2026-10-01）：`label_v3.py` 有两套词表，此前把二者混为一谈：
  · **一阶筛选** `SOUND_KEYWORDS`（23 词）——决定一条评论是否进入管线；
  · **分类词表** `ISSUE_BUCKETS`（如高音仅 `treble/pitch/frequency`）——决定规则初筛给出的类别。
因此"漏检率"有两种定义，本脚本**两种都测**，并明确标注，避免再混用：
  · 定义 A（**入库漏检**）：LLM 正例中不含任何 `SOUND_KEYWORDS` 的比例 → 该条根本不会被处理；
  · 定义 B（**分类漏检**）：LLM 正例中不含该类别分类词的比例 → 规则不会给出该类别标签。

同时给出**扩充词表**（针对高音/清晰度）后的复测。**本轮只测量，不改冻结标签与模型。**
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "labeled_llm.csv")

# 与 label_v3.py 逐字一致
SOUND_KEYWORDS = [
    "sound", "audio", "bass", "treble", "clarity", "muffled", "distortion",
    "static", "hiss", "crisp", "muddy", "volume", "pitch", "frequency",
    "crackling", "popping", "sibilance", "tinny", "boomy", "hollow",
    "scratchy", "buzzing", "rattling",
]
BUCKETS = {
    "低音": ["bass", "boomy"],
    "清晰度": ["muffled", "muddy", "clarity", "hollow", "tinny"],
    "杂音": ["static", "hiss", "distortion", "crackling", "buzzing", "popping",
             "sibilance", "rattling", "scratchy"],
    "音量": ["volume"],
    "高音": ["treble", "pitch", "frequency"],
}
# 扩充：一阶筛选加听感词；分类词表加高音/清晰度词
SOUND_KEYWORDS_EX = SOUND_KEYWORDS + [
    "highs", "high end", "high-end", "sibilant", "harsh", "shrill", "piercing",
    "sharp", "bright", "fatiguing", "ear-piercing", "vocals", "voice", "detail",
    "low end", "low-end", "sub-bass", "subbass", "midrange", "mids", "tone",
    "equalizer", "eq", "soundstage", "imaging",
]
BUCKETS_EX = dict(BUCKETS)
BUCKETS_EX["高音"] = BUCKETS["高音"] + [
    "highs", "high end", "high-end", "sibilant", "harsh", "shrill", "piercing",
    "sharp", "bright", "fatiguing", "ear-piercing", "treble-heavy",
]
BUCKETS_EX["清晰度"] = BUCKETS["清晰度"] + ["vocal", "vocals", "voice", "detail", "clear"]

COLS = {"低音": "issue_bass_llm", "清晰度": "issue_clarity_llm", "杂音": "issue_noise_llm",
        "音量": "issue_volume_llm", "高音": "issue_treble_llm"}


def build_re(words):
    return re.compile(r"\b(?:" + "|".join(map(re.escape, words)) + r")\b", re.IGNORECASE)


def miss_rate(texts, words):
    rx = build_re(words)
    miss = sum(1 for t in texts if not rx.search(t))
    return miss, len(texts), (miss / len(texts) * 100 if texts else 0.0)


def main() -> int:
    pos = {k: [] for k in COLS}
    n_rows = 0
    with open(CSV, encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            n_rows += 1
            if str(row.get("sound_negative_llm", "")).strip() != "1":
                continue
            text = str(row.get("text") or "")
            for name, col in COLS.items():
                if str(row.get(col, "")).strip() == "1":
                    pos[name].append(text)
    print(f"语料 {n_rows} 行；各类正例：" + "、".join(f"{k} {len(v)}" for k, v in pos.items()))

    # 定义 A：入库漏检（全正例集口径）
    all_pos = [t for v in pos.values() for t in v]
    m0, n0, r0 = miss_rate(all_pos, SOUND_KEYWORDS)
    m1, _, r1 = miss_rate(all_pos, SOUND_KEYWORDS_EX)
    print(f"\n[定义 A｜入库漏检] 全正例 {n0} 条：现行 {r0:.1f}% → 扩充 {r1:.1f}%")

    rows = []
    print(f"\n[定义 B｜分类漏检]")
    print(f"{'类别':<6}{'正例':>6}{'现行':>9}{'扩充后':>10}{'改善':>9}{'达标≤40%':>10}")
    for name in COLS:
        a, n, ra = miss_rate(pos[name], BUCKETS[name])
        b, _, rb = miss_rate(pos[name], BUCKETS_EX[name])
        rows.append({"类别": name, "正例数": n, "现行漏检率": round(ra, 1),
                     "扩充后漏检率": round(rb, 1), "改善百分点": round(ra - rb, 1),
                     "达标(≤40%)": rb <= 40})
        print(f"{name:<6}{n:>6}{ra:>8.1f}%{rb:>9.1f}%{ra - rb:>8.1f}pp"
              f"{'✅' if rb <= 40 else '❌':>10}")

    md = ["# W13 关键词漏检率（A-尽力 · 两种定义并列）", "",
          "> **重要口径更正（2026-10-01）**：`label_v3.py` 有**两套词表**——一阶筛选 `SOUND_KEYWORDS`（23 词）",
          "> 决定评论是否入库；分类词表 `ISSUE_BUCKETS` 决定规则给出的类别。此前把二者混用，",
          "> 导致同一「高音漏检率」出现 62.6%／69.4% 两个数。本页两种定义**分别测量并标注**。", "",
          "## 定义 A｜入库漏检率（全正例口径）", "",
          f"- 现行词表：**{r0:.1f}%**（{m0}/{n0} 条正例不含任何一阶关键词 → 根本不会进入管线）",
          f"- 扩充词表后：**{r1:.1f}%**", "",
          "## 定义 B｜分类漏检率（按类别）", "",
          "| 类别 | 正例数 | 现行漏检率 | 扩充后 | 改善 | 达标（≤40%）|",
          "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['类别']} | {r['正例数']} | {r['现行漏检率']}% | "
                  f"**{r['扩充后漏检率']}%** | −{r['改善百分点']}pp | "
                  f"{'✅' if r['达标(≤40%)'] else '❌'} |")
    md += ["", "## 扩充词表", "",
           "- 一阶筛选追加：`" + "`, `".join(SOUND_KEYWORDS_EX[len(SOUND_KEYWORDS):]) + "`",
           "- 高音分类追加：`" + "`, `".join(BUCKETS_EX["高音"][3:]) + "`",
           "- 清晰度分类追加：`" + "`, `".join(BUCKETS_EX["清晰度"][5:]) + "`",
           "",
           "## 结论与边界", "",
           f"1. **高音类（分类漏检）**：现行 {rows[4]['现行漏检率']}% → 扩充后 **{rows[4]['扩充后漏检率']}%**；",
           f"   **仍未达 40% 目标**（差 {rows[4]['扩充后漏检率'] - 40:.1f}pp），需继续扩词或改规则；",
           "2. **本轮不改冻结标签与模型**：词表变更会改变候选集（属下游管线变更），须决策方裁定；",
           "3. 放宽词表的代价是**复核量上升**（初筛是召回闸门），按实测复核成本约 0.03 美元/1,000 条可估算增量；",
           "4. 词表对**已训练模型无影响**（模型看文本，不看关键词）——此项只影响未来重标的成本与召回。"]
    open(os.path.join(HERE, "docs", "w13_keyword_miss_rate.md"), "w",
         encoding="utf-8", newline="\n").write("\n".join(md) + "\n")
    json.dump({"definition_A_gate": {"current": round(r0, 1), "expanded": round(r1, 1),
                                     "n_positives": n0},
               "definition_B_per_class": rows,
               "sound_keywords_expanded": SOUND_KEYWORDS_EX[len(SOUND_KEYWORDS):],
               "treble_expanded": BUCKETS_EX["高音"][3:],
               "gen": "measure_only"}, open(os.path.join(HERE, "w13_keyword_miss_rate.json"),
                                            "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n[写出] docs/w13_keyword_miss_rate.md / .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
