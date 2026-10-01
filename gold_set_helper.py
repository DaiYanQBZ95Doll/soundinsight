# -*- coding: utf-8 -*-
"""人工金标工作流辅助（**不替决策方做判断**）。

决策方 2026-10-01 裁定：金标 300 条由**决策方本人判别**，网页端 LLM 仅辅助翻译与解释。
本工具据此提供三件事：
  1) `--status`：进度（已填/剩余/分层进度）；
  2) `--show N`：逐条显示（英文原文 + 可复制的**仅翻译/解释**提示词，明确禁止问"是不是差评"）；
  3) `--next`：定位下一个未填条目（便于续做）。

用法：
    python gold_set_helper.py --status
    python gold_set_helper.py --show S1-003
    python gold_set_helper.py --next
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, "docs", "gold_set", "worksheet.csv")
KEY = os.path.join(HERE, "v2", "gold_set_key.json")
COL = "人工判定(1=音质差评/0=不是)"

# 提示词：只许翻译/解释，**禁止**给判定——避免用 LLM 判断污染人工金标
PROMPT = """请只做这件事：把下面这条英文商品评论**翻译成中文**，并用一两句话解释它在说什么（涉及的产品是什么、用户满意还是不满）。
**不要**判断它是否属于"耳机音质差评"，**不要**给出 1/0 结论——判定由我本人做。

评论原文：
{text}
"""


def rows():
    with open(SHEET, encoding="utf-8-sig", errors="replace") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--next", action="store_true")
    args = ap.parse_args()
    if not os.path.isfile(SHEET):
        print("[缺] 先跑 python make_gold_set.py 生成工作表")
        return 1
    data = rows()
    filled = [r for r in data if (r.get(COL) or "").strip()]

    if args.status or not (args.show or args.next):
        from collections import Counter
        per = Counter()
        done = Counter()
        for r in data:
            sid = r["编号"].split("-")[0]
            per[sid] += 1
            if (r.get(COL) or "").strip():
                done[sid] += 1
        print(f"金标工作表：{len(data)} 条｜已填 {len(filled)}（{len(filled)/len(data)*100:.1f}%）")
        for sid in sorted(per):
            print(f"  {sid}：{done[sid]}/{per[sid]}")
        rest = len(data) - len(filled)
        print(f"\n剩余 {rest} 条｜按 20–35 秒/条 ≈ {rest*20/60:.0f}–{rest*35/60:.0f} 分钟")
        print("填写位置：docs/gold_set/worksheet.csv 的「人工判定」列（Excel 可直接打开）")
        print("判据：这条评论是否在抱怨【耳机/耳塞/头戴】的音质（低音/清晰度/杂音/音量/高音）；"
              "无法判断产品是否耳机 → 填 ?")
        if filled:
            print("\n完成后运行：python score_gold_set.py")
        return 0

    if args.next:
        for r in data:
            if not (r.get(COL) or "").strip():
                args.show = r["编号"]
                break
        else:
            print("全部已填 ✓ 运行 python score_gold_set.py 出结论")
            return 0

    target = next((r for r in data if r["编号"] == args.show), None)
    if not target:
        print(f"[未找到] 编号 {args.show}")
        return 1
    print(f"=== {target['编号']} ===")
    print(f"当前填写值：{(target.get(COL) or '（空）')}")
    print("\n--- 原文 ---")
    print(target["原文"])
    print("\n--- 可复制的翻译/解释提示词（明确禁止给判定）---")
    print(PROMPT.format(text=target["原文"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
