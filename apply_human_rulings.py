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
# 批次状态**按席位隔离**（Qwen 指出共享状态会互相覆盖，导致裸数字串落到不同评论）
BATCH_STATE_FMT = os.path.join(HERE, "v2", "gold_set_batch_{author}.json")
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


def print_batch(rows, n: int, author: str = "dsh") -> None:
    todo = [r for r in rows if not (r.get(COL) or "").strip()]
    batch = todo[:n]
    ids = [r["编号"] for r in batch]
    json.dump({"ids": ids}, open(BATCH_STATE_FMT.format(author=author), "w",
                                encoding="utf-8"), ensure_ascii=False)
    print(f"## 下一批（{len(batch)} 条）——请按顺序回 {len(batch)} 个数字（1=是｜0=不是｜2=无法判断）\n")
    for i, r in enumerate(batch, 1):
        print(f"[{i}] G{i:03d} · {r['编号']}（绝对编号 G 与批次无关，推荐用它回）")
        print(f"    原文：{r['原文'][:300]}")
        print(f"    翻译：{(r.get('中文翻译') or '')[:200]}")
        snd = (r.get("关于声音的表述") or "").strip()
        print(f"    声音：{snd[:160] if snd else '（兜底条目：仅提供翻译）'}")
        print(f"    产品：{(r.get('产品') or '')[:60]}")
    print(f"\n（顺序即编号顺序：{ids[0]} … {ids[-1]}；也可用 ②带编号／③只报例外／④区间 格式）")


def parse_text(text: str, ids: list[str], all_ids: list[str] | None = None) \
        -> tuple[dict, list[str]]:
    """解析判定文本。`all_ids` 为工作表全序，用于把 **绝对编号 G###** 映射为 S 编号。"""
    """返回 {编号: 单元格值} 与 错误列表。"""
    out, errs = {}, []
    text = text.strip()
    all_ids = all_ids or ids
    # 只保留"数据行"：丢弃标题／引用／表格／代码块／不含编号的行。
    # 理由：答题卡与席位的**表头说明**里会出现编号与数字（示例、口径），
    # 若一并解析会写入假判定（干跑已实测到假阳性）。
    kept, in_fence = [], False
    for ln in text.splitlines():
        t = ln.strip()
        if t.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or t.startswith(("#", ">", "|")):
            continue
        if not re.search(r"(?:[A-Z]\d-\d{3}|\bG\d{1,3}\b)", t):
            continue
        kept.append(ln)
    text = "\n".join(kept)

    def g2s(tok: str):
        m = re.fullmatch(r"G(\d{1,3})", tok.strip(), re.I)
        if not m:
            return None
        k = int(m.group(1))
        return all_ids[k - 1] if 1 <= k <= len(all_ids) else None

    # G 编号（绝对）：G007=0 或 G007:0
    for m in re.finditer(r"\bG(\d{1,3})\s*[=:：]\s*([012?])(?![0-9])", text, re.I):
        sid = g2s("G" + m.group(1))
        if sid:
            out[sid] = VAL2CELL[m.group(2)]
        text = text.replace(m.group(0), " ")
    # G 区间：G001..G025 = 1,0,2,...
    for m in re.finditer(r"G(\d{1,3})\s*\.\.\s*G(\d{1,3})\s*=\s*([0-9?.,\s]+)",
                         text, re.I):
        a, b = int(m.group(1)), int(m.group(2))
        vals = [v for v in re.split(r"[,\s]+", m.group(3)) if v in VAL2CELL]
        for k, v in zip(range(a, b + 1), vals):
            sid = g2s(f"G{k}")
            if sid:
                out[sid] = VAL2CELL[v]
        text = text.replace(m.group(0), " ")
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
        if not v or v.startswith("#") or re.match(r"^[A-Z]\d-\d{3}$", v):
            continue
        if v in VAL2CELL or _UNFILLED.match(v):
            continue      # 未填占位（_ / ___ / ?）静默跳过
        if re.fullmatch(r"[A-Z]\d-\d{3}[:=：][_\-—?？]*", v) or \
                re.fullmatch(r"G\d{1,3}[:=：][_\-—?？]*", v, re.I):
            continue      # 未填的编号（S2-037:_）不是错误
        if not any(ch.isdigit() for ch in v):
            continue      # 纯文字（表头/说明）不是数据，静默跳过
        errs.append(f"无法解析的片段：{v[:20]}")
    return out, errs


def apply_rulings(rows, mapping: dict, author: str, write_csv: bool = False) -> int:
    """把判定写入**本席位文件**；仅当 write_csv=True 时才写共享 CSV。

    共享 CSV 是单点资源：默认只允许 `--author dsh` 写（Qwen 指出旧版无条件写 CSV，
    会让"只写自己席位"的规则被工具本身破坏）。"""
    by_id = {r["编号"]: r for r in rows}
    applied = []
    for i, cell in mapping.items():
        r = by_id.get(i)
        if not r:
            continue
        r[COL] = cell
        applied.append((i, cell))
    if write_csv:
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


def _slot_value(line: str):
    """从判定位行中稳妥取值：取反引号内容里的 0/1/2。

    决策方的实际写法是**在横线内填数字**（如 `` `_0__` ``、`` `__0_` ``），
    故不能要求"恰好一个字符"。返回 ('0'|'1'|'?'|None, 说明)：
      · 恰好一个不同数字 → 值（2 映射为 ?）；
      · 无数字 → None（未填）；
      · 两个不同数字 → ('AMBIG', 原样内容)，交人工确认，**不猜**。
    """
    m = re.search(r"`([^`]*)`", line)
    content = m.group(1) if m else line
    digs = [c for c in content if c in "012"]
    distinct = sorted(set(digs))
    if len(distinct) > 1:
        return "AMBIG", content
    if not distinct:
        return None, content
    return ("?" if distinct[0] == "2" else distinct[0]), content


def import_from_notes(path: str) -> dict:
    """从 review_notes.md 解析 `**判定（决策方填）**：`<值>`` —— 只接受 1/0/? 。
    空白（`___`）视为未判，不返回。"""
    out = {}
    cur = None
    ambig = []          # 歧义条目（含两个不同数字）——收集后由调用方报出，不猜
    pat_id = re.compile(r"^#{2,4}\s*(S\d-\d{3})(?:\s*[\u3000 ]\s*G\d{1,3})?\s*$")
    pat_val = re.compile(r"判定（决策方填）\*\*：\s*`?\s*([012?])\s*`?\s*$")
    # Kimi 答题卡的内联形式：`### S2-037　**判定**：1`（也容忍「判定：_」未填）
    pat_inline = re.compile(r"^#{2,4}\s*(S\d-\d{3})[^\n]*?\*\*判定\*\*\s*[:：]\s*([012?])(?![0-9])")
    for ln in open(path, encoding="utf-8", errors="replace").read().splitlines():
        # 内联形式（Kimi 的答题卡）：`### S2-037　**判定**：1` —— ID 与值同行
        mi = pat_inline.match(ln.strip())
        if mi:
            cur = mi.group(1)
            out[cur] = VAL2CELL[mi.group(2)]
            continue
        m = pat_id.match(ln.strip())
        if m:
            cur = m.group(1)
            continue
        if cur and ("判定（决策方填）" in ln or "判定" in ln):
            val, raw = _slot_value(ln.strip())
            if val == "AMBIG":
                ambig.append(f"{cur}（内容 {raw!r}）")
            elif val is not None:
                out[cur] = VAL2CELL.get(val, val)
    return out


# 未填占位：静默跳过（答题卡里未判的条目长这样）
_UNFILLED = re.compile(r"^[_\-—\s?？]*$")


def import_answer_sheet(path: str, all_ids: list[str]) -> tuple[dict, list[str]]:
    """接收**任一方**的答题卡：识别 `S#-###:1`／`S#-###=1`／`G###=1`／表格行／
    Kimi 紧凑行（`S2-037:_　S1-040:_`）；未填占位忽略。返回（映射, 备注）。"""
    text = open(path, encoding="utf-8", errors="replace").read()
    # 块式优先：按 `## S2-037　G001` 标题跟踪条目，读该块内的判定位（新答题卡/review_notes）
    block = import_from_notes(path)
    if block:
        blanks = len(re.findall(r"判定（决策方填）[^\n]*", text)) - len(block)
        notes = [f"块式解析：{len(block)} 条已填"
                 + (f"｜另有 {blanks} 条未填（已跳过）" if blanks > 0 else "")]
        return block, notes
    mapping, notes = parse_text(text, all_ids, all_ids)
    # 统计未填（仅提示，不算错误）
    blanks = len(re.findall(r"[SG]\d{1,3}(?:-\d{3})?\s*[:=：]\s*[_\-—?？]", text))
    if blanks:
        notes.append(f"未填 {blanks} 处（已跳过）")
    return mapping, notes


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
    csv_vals = {r["编号"]: (r.get(COL) or "").strip() for r in load_rows()
                if (r.get(COL) or "").strip()}
    prints, missing = {}, []
    if csv_vals:
        prints["csv"] = csv_vals          # 共享 CSV 也是一方（旧版读了却不用，属死代码）
    for a in ("dsh", "kimi", "qwen"):
        p = rulings_path(a)
        if not os.path.isfile(p):
            missing.append(a)
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
            m = re.match(r"\|\s*(S\d-\d{3})\s*\|\s*([012?])\s*\|", ln)
            if m:
                vals[m.group(1)] = m.group(2)
                continue
            # 格式二：行内 `S1-001=1`（红队 Kimi 采用的写法）
            for m2 in re.finditer(r"(S\d-\d{3})\s*[=:：]\s*([012?])(?![0-9])", ln):
                vals[m2.group(1)] = m2.group(2)
        prints[a] = vals
    # 登记为不可用的一方，其席位缺失属**预期**（执行纪律 R30：流程要有降级路径）
    unavailable = set()
    _avp = os.path.join(GDIR, os.pardir, "bus", "availability.json")
    if os.path.isfile(_avp):
        try:
            import json as _json
            _av = _json.load(open(_avp, encoding="utf-8")).get("parties", {})
            unavailable = {k for k, v in _av.items() if v.get("status") == "unavailable"}
        except (OSError, ValueError):
            unavailable = set()
    expected = [m for m in missing if m in unavailable]
    missing = [m for m in missing if m not in unavailable]
    if expected:
        print("（预期缺失：" + ", ".join(sorted(expected)) + " 已登记为不可用，非异常）")
    if missing:
        print("⚠ 缺失席位文件：" + ", ".join(missing)
              + "（未参与对账；若该方判定只写在共享 CSV 里，请其补写席位 md）")
    if len(prints) < 2:
        print("对账需要至少两份来源（含共享 CSV）；当前：", list(prints) or "无")
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
    # 编号解析：数字 2 应映射为 ?
    v2 = {}
    for m2 in re.finditer(r"(S\d-\d{3})\s*[=:：]\s*([012?])(?![0-9])", "S1-009=2"):
        v2[m2.group(1)] = m2.group(2)
    ok2 = v2 == {"S1-009": "2"}
    print(f"  [{'OK ' if ok2 else 'BAD'}] 三档写法 2：{v2}")
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
            m = re.match(r"\|\s*(S\d-\d{3})\s*\|\s*([012?])\s*\|", ln)
            if m:
                vals[m.group(1)] = m.group(2)
                continue
            for m2 in re.finditer(r"(S\d-\d{3})\s*[=:：]\s*([012?])(?![0-9])", ln):
                vals[m2.group(1)] = m2.group(2)
        ok = len(vals) == expect
        bad += 0 if ok else 1
        print(f"  [{'OK ' if ok else 'BAD'}] {label}：解析 {len(vals)} 条（期望 {expect}）")
    print(f"  结果：{len(cases) - bad}/{len(cases)} 通过"
          + ("；三档 2 映射 OK" if ok2 else "；**三档 2 映射失败**"))
    return 1 if (bad or not ok2) else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=0)
    ap.add_argument("--write-csv", action="store_true",
                    help="显式允许写共享 CSV（默认仅 --author dsh 允许）")
    ap.add_argument("--text")
    ap.add_argument("--file")
    ap.add_argument("--from-notes", action="store_true",
                    help="从 docs/gold_set/review_notes.md 的填好的判定位导入")
    ap.add_argument("--from-answer-sheet", nargs="?", const="auto",
                    help="接收答题卡（默认自动寻找 answer_sheet*.md；可指定路径）")
    ap.add_argument("--author", default="dsh",
                    choices=("dsh", "dsh2", "kimi", "qwen"),
                    help="dsh=主接收（可写共享 CSV）；dsh2=第二遍判定（只写自己席位）；kimi/qwen=其席位（执行方不代写）")
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
    # 共享 CSV 的写入闸门：默认只有本席位 dsh 允许（他人须显式 --write-csv）
    write_csv = args.write_csv or args.author == "dsh"
    if args.progress:
        progress(rows)
        return 0
    if args.reconcile:
        reconcile()
        return 0
    if args.batch:
        print_batch(rows, args.batch, args.author)
        return 0
    if args.from_answer_sheet:
        if args.from_answer_sheet == "auto":
            cands = [os.path.join(GDIR, f) for f in
                     ("answer_sheet_decision.md", "answer_sheet.md",
                      "answer_sheet_s1_add100.md", "answer_sheet_kimi.md",
                      "answer_sheet_qwen.md")]
            path = next((c for c in cands if os.path.isfile(c)), None)
        else:
            path = args.from_answer_sheet
        if not path or not os.path.isfile(path):
            print("[缺] 未找到答题卡；可用 --from-answer-sheet <路径>")
            return 1
        mapping, notes = import_answer_sheet(path, [r["编号"] for r in rows])
        print(f"接收答题卡：{os.path.relpath(path, HERE)}｜解析到 {len(mapping)} 条")
        for n in notes:
            print("  [提示] " + n)
        if args.dry_run:
            print("[dry-run] 未写入任何文件")
            return 0
        if not mapping:
            print("[空] 答题卡尚无已填判定")
            return 0
        n = apply_rulings(rows, mapping, args.author, write_csv)
        print(f"已接收 {n} 条 → {os.path.relpath(rulings_path(args.author), HERE)}"
              + (f" 与 {os.path.relpath(CSV_PATH, HERE)}" if write_csv
                 else "（未写共享 CSV：需 --author dsh 或 --write-csv）"))
        progress(rows)
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
        n = apply_rulings(rows, mapping, args.author, write_csv)
        print(f"已从 notes 写入 {n} 条 → "
              f"{os.path.relpath(rulings_path(args.author), HERE)}"
              + (f" 与 {os.path.relpath(CSV_PATH, HERE)}" if write_csv
                 else "（未写共享 CSV）"))
        progress(rows)
        return 0
    text = args.text or ""
    if args.file:
        text = open(args.file, encoding="utf-8").read()
    if not text:
        ap.print_help()
        return 0
    bs = BATCH_STATE_FMT.format(author=args.author)
    ids = json.load(open(bs, encoding="utf-8"))["ids"] if os.path.isfile(bs) \
        else [r["编号"] for r in rows]
    mapping, errs = parse_text(text, ids, [r["编号"] for r in rows])
    if args.dry_run:
        print(f"[dry-run] 解析到 {len(mapping)} 条，未写入任何文件")
        for i, c in list(mapping.items())[:8]:
            print(f"  {i} → {c}（{CELL2NAME.get(c, '')}）")
        for e in errs[:5]:
            print("  [提示] " + e)
        return 0
    n = apply_rulings(rows, mapping, args.author, write_csv)
    print(f"已写入 {n} 条 → {os.path.relpath(rulings_path(args.author), HERE)}"
          + (f" 与 {os.path.relpath(CSV_PATH, HERE)}" if write_csv
             else "（**未写共享 CSV**：本席位只记录，落库由 --author dsh 单点执行）"))
    for e in errs[:5]:
        print("  [提示] " + e)
    progress(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
