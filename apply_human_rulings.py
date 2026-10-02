# -*- coding: utf-8 -*-
"""人工金标判定：写入与对账（决策方逐条判、极简数字输入）。

支持：
  --batch N            打印下一批 N 条（含中性翻译与解析），并**记住批次顺序**（供格式①按序写入）
  --text "..."         写入判定（支持 4 种格式：按序一串／带编号／只报例外／区间）
  --file path          从文件读判定文本
  --author dsh|kimi|qwen  写哪一份（默认 dsh）
  --progress           进度
  --reconcile          三份对账（不一致即提示可能的转写错误）

写入目标：`docs/gold_set/human_rulings_<author>.md` 与 `assisted_worksheet.csv` 的「人工判定」列。
**只写自己那一份**（默认 dsh），不触碰他人的文件。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GDIR = os.path.join(HERE, "docs", "gold_set")
CSV_PATH = os.path.join(GDIR, "assisted_worksheet.csv")
BATCH_STATE = os.path.join(HERE, "v2", "gold_set_batch.json")
COL = "人工判定(1=音质差评/0=不是)"
VAL2CELL = {"1": "1", "0": "0", "2": "?"}
CELL2NAME = {"1": "是（涉及耳机声音表现）", "0": "不是", "?": "无法判断"}


def load_rows():
    with open(CSV_PATH, encoding="utf-8-sig", errors="replace") as fh:
        return list(csv.DictReader(fh))


def save_rows(rows):
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def rulings_path(author: str) -> str:
    return os.path.join(GDIR, f"human_rulings_{author}.md")


def print_batch(rows, n: int) -> None:
    todo = [r for r in rows if not (r.get(COL) or "").strip()]
    batch = todo[:n]
    ids = [r["编号"] for r in batch]
    json.dump({"ids": ids}, open(BATCH_STATE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"## 下一批（{len(batch)} 条）——请按顺序回 {len(batch)} 个数字（1=是｜0=不是｜2=无法判断）\n")
    for i, r in enumerate(batch, 1):
        print(f"[{i}] {r['编号']}")
        print(f"    原文：{r['原文'][:300]}")
        print(f"    翻译：{(r.get('中文翻译') or '')[:200]}")
        snd = (r.get("关于声音的表述") or "").strip()
        print(f"    声音：{snd[:160] if snd else '（兜底条目：仅提供翻译）'}")
        print(f"    产品：{(r.get('产品') or '')[:60]}")
    print(f"\n（顺序即编号顺序：{ids[0]} … {ids[-1]}；也可用 ②带编号／③只报例外／④区间 格式）")


def parse_text(text: str, ids: list[str]) -> tuple[dict, list[str]]:
    """返回 {编号: 单元格值} 与 错误列表。"""
    out, errs = {}, []
    text = text.strip()
    # ④ 区间：S1-001..S1-020 = 1,0,2,...
    for m in re.finditer(r"([A-Z]\d-\d{3})\s*\.\.\s*([A-Z]\d-\d{3})\s*=\s*([0-9.,\s]+)", text):
        a, b, vals = m.group(1), m.group(2), [v for v in re.split(r"[,\s]+", m.group(3)) if v]
        pre, na = a.split("-")[0], int(a.split("-")[1])
        nb = int(b.split("-")[1])
        for k, v in zip(range(na, nb + 1), vals):
            if v in VAL2CELL:
                out[f"{pre}-{k:03d}"] = VAL2CELL[v]
            else:
                errs.append(f"非法值 {v}")
        text = text.replace(m.group(0), " ")
    # ③ 只报例外
    m = re.search(r"(?:除|except)\s*(S\d-\d{3})\s*=\s*([0-9])\s*[，,]?\s*(?:外)?[，,]?\s*(?:其余|其他|全)\s*(?:为|是)?\s*([0-9])", text)
    if m:
        ex_id, ex_val, rest_val = m.group(1), m.group(2), m.group(3)
        for i in ids:
            out[i] = VAL2CELL[rest_val]
        out[ex_id] = VAL2CELL[ex_val]
        text = text.replace(m.group(0), " ")
    # ② 带编号
    for m in re.finditer(r"(S\d-\d{3})\s*[=:：]?\s*([0-9])", text):
        out[m.group(1)] = VAL2CELL[m.group(2)]
        text = text.replace(m.group(0), " ")
    # ① 按顺序一串（剩下的纯数字）
    rest = [v for v in re.split(r"[\s,;，；]+", text) if v in VAL2CELL]
    if rest:
        if len(rest) > len(ids):
            errs.append(f"按序数字 {len(rest)} 个 > 本批 {len(ids)} 条，多余的已忽略")
        for i, v in zip(ids, rest):
            out.setdefault(i, VAL2CELL[v])
    for v in re.split(r"[\s,;，；]+", text):
        if v and v not in VAL2CELL and not v.startswith("#") and not re.match(r"^[A-Z]\d-\d{3}$", v):
            errs.append(f"无法解析的片段：{v[:20]}")
    return out, errs


def apply_rulings(rows, mapping: dict, author: str) -> int:
    by_id = {r["编号"]: r for r in rows}
    applied = []
    for i, cell in mapping.items():
        r = by_id.get(i)
        if not r:
            continue
        r[COL] = cell
        applied.append((i, cell))
    save_rows(rows)
    # 写作者文件
    p = rulings_path(author)
    lines = []
    if os.path.isfile(p):
        lines = open(p, encoding="utf-8").read().splitlines()
    else:
        lines = [f"# 人工金标判定（{author}）", "",
                 "> 判定由**决策方**逐条作出；本文件是转写记录（一人一文件，互不覆盖）。",
                 "> 值：`1`=是（涉及耳机声音表现）｜`0`=不是｜`?`=无法判断", "",
                 "| 编号 | 判定 | 含义 |", "|---|---|---|"]
    existing = {ln.split("|")[1].strip() for ln in lines if ln.startswith("| S")}
    for i, cell in applied:
        if i in existing:
            lines = [ln for ln in lines if not ln.startswith(f"| {i} ")]
        lines.append(f"| {i} | {cell} | {CELL2NAME.get(cell, '')} |")
    open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    return len(applied)


def import_from_notes(path: str) -> dict:
    """从 review_notes.md 解析 `**判定（决策方填）**：`<值>`` —— 只接受 1/0/? 。
    空白（`___`）视为未判，不返回。"""
    out = {}
    cur = None
    pat_id = re.compile(r"^##\s*(S\d-\d{3})\s*$")
    pat_val = re.compile(r"判定（决策方填）\*\*：\s*`?\s*([01?])\s*`?\s*$")
    for ln in open(path, encoding="utf-8", errors="replace").read().splitlines():
        m = pat_id.match(ln.strip())
        if m:
            cur = m.group(1)
            continue
        if cur:
            m2 = pat_val.search(ln.strip())
            if m2:
                out[cur] = VAL2CELL[m2.group(1)]
    return out


def progress(rows) -> None:
    from collections import Counter
    done = Counter()
    per = Counter()
    for r in rows:
        sid = r["编号"].split("-")[0]
        per[sid] += 1
        if (r.get(COL) or "").strip():
            done[sid] += 1
    total_done = sum(done.values())
    print(f"进度：{total_done}/{len(rows)}（{total_done/len(rows)*100:.1f}%）")
    for sid in sorted(per):
        print(f"  {sid}：{done[sid]}/{per[sid]}")
    if total_done:
        print("  出结论：python score_gold_set.py --sheet assisted")


def reconcile() -> None:
    rows = {r["编号"]: (r.get(COL) or "").strip() for r in load_rows()}
    prints = {}
    for a in ("dsh", "kimi", "qwen"):
        p = rulings_path(a)
        if not os.path.isfile(p):
            continue
        vals = {}
        in_fence = False
        for ln in open(p, encoding="utf-8"):
            # 跳过代码块与引用块：那里常放**格式示例**（如 S1-001=1 S1-002=0），
            # 若当成真实判定会静默污染金标（本函数首版即犯此错，已被自测抓到）
            if ln.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or ln.lstrip().startswith(">"):
                continue
            # 格式一：表格行 | S1-001 | 1 |
            m = re.match(r"\|\s*(S\d-\d{3})\s*\|\s*([01?])\s*\|", ln)
            if m:
                vals[m.group(1)] = m.group(2)
                continue
            # 格式二：行内 `S1-001=1`（红队 Kimi 采用的写法）
            for m2 in re.finditer(r"(S\d-\d{3})\s*[=:：]\s*([01?])(?![0-9])", ln):
                vals[m2.group(1)] = m2.group(2)
        prints[a] = vals
    if len(prints) < 2:
        print("对账需要至少两份裁定文件；当前：", list(prints) or "无")
        return
    keys = set().union(*[set(v) for v in prints.values()])
    diff = [k for k in sorted(keys)
            if len({v.get(k) for v in prints.values() if k in v}) > 1]
    print(f"对账：参与 {list(prints)}｜共同条目 {len(keys)}｜**不一致 {len(diff)}**")
    for k in diff[:20]:
        print("  " + k + "：" + "｜".join(f"{a}={prints[a].get(k,'—')}" for a in prints))
    if diff:
        print("→ 不一致说明**转写有误**，请决策方确认以哪份为准（执行方据此更正 CSV）")


def _self_test() -> int:
    """负向自测：引用块/代码块里的**格式示例**不得被当成真实判定。"""
    import tempfile
    cases = [
        ("> 回传格式：`S1-001=1 S1-002=0`\n", 0, "引用块示例"),
        ("```\nS1-001=1\n```\n", 0, "代码块示例"),
        ("| S1-005 | 1 |\n", 1, "真实表格行"),
        ("S1-007=0\n", 1, "真实行内写法"),
    ]
    bad = 0
    for text, expect, label in cases:
        vals = {}
        in_fence = False
        for ln in text.splitlines(keepends=True):
            if ln.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or ln.lstrip().startswith(">"):
                continue
            m = re.match(r"\|\s*(S\d-\d{3})\s*\|\s*([01?])\s*\|", ln)
            if m:
                vals[m.group(1)] = m.group(2)
                continue
            for m2 in re.finditer(r"(S\d-\d{3})\s*[=:：]\s*([01?])(?![0-9])", ln):
                vals[m2.group(1)] = m2.group(2)
        ok = len(vals) == expect
        bad += 0 if ok else 1
        print(f"  [{'OK ' if ok else 'BAD'}] {label}：解析 {len(vals)} 条（期望 {expect}）")
    print(f"  结果：{len(cases) - bad}/{len(cases)} 通过")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=0)
    ap.add_argument("--text")
    ap.add_argument("--file")
    ap.add_argument("--from-notes", action="store_true",
                    help="从 docs/gold_set/review_notes.md 的填好的判定位导入")
    ap.add_argument("--author", default="dsh", choices=("dsh", "kimi", "qwen"))
    ap.add_argument("--progress", action="store_true")
    ap.add_argument("--reconcile", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="只解析与报告，不写入任何文件")
    ap.add_argument("--csv", help="改用指定的 CSV（测试用；默认辅助版工作表）")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    global CSV_PATH
    if args.csv:
        CSV_PATH = args.csv
    if args.self_test:
        return _self_test()
    if not os.path.isfile(CSV_PATH):
        print("[缺] 先跑 python make_gold_set_notes.py")
        return 1
    rows = load_rows()
    if args.progress:
        progress(rows)
        return 0
    if args.reconcile:
        reconcile()
        return 0
    if args.batch:
        print_batch(rows, args.batch)
        return 0
    if args.from_notes:
        notes = os.path.join(GDIR, "review_notes.md")
        mapping = import_from_notes(notes)
        if not mapping:
            print(f"[空] {os.path.relpath(notes, HERE)} 中未发现已填判定")
            return 0
        if args.dry_run:
            print(f"[dry-run] 从 notes 解析到 {len(mapping)} 条，未写入")
            return 0
        n = apply_rulings(rows, mapping, args.author)
        print(f"已从 notes 写入 {n} 条 → "
              f"{os.path.relpath(rulings_path(args.author), HERE)}"
              f" 与 {os.path.relpath(CSV_PATH, HERE)}")
        progress(rows)
        return 0
    text = args.text or ""
    if args.file:
        text = open(args.file, encoding="utf-8").read()
    if not text:
        ap.print_help()
        return 0
    ids = json.load(open(BATCH_STATE, encoding="utf-8"))["ids"] if os.path.isfile(BATCH_STATE) \
        else [r["编号"] for r in rows]
    mapping, errs = parse_text(text, ids)
    if args.dry_run:
        print(f"[dry-run] 解析到 {len(mapping)} 条，未写入任何文件")
        for i, c in list(mapping.items())[:8]:
            print(f"  {i} → {c}（{CELL2NAME.get(c, '')}）")
        for e in errs[:5]:
            print("  [提示] " + e)
        return 0
    n = apply_rulings(rows, mapping, args.author)
    print(f"已写入 {n} 条 → {os.path.relpath(rulings_path(args.author), HERE)}"
          f" 与 {os.path.relpath(CSV_PATH, HERE)}")
    for e in errs[:5]:
        print("  [提示] " + e)
    progress(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
