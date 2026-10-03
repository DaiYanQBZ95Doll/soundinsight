# -*- coding: utf-8 -*-
"""判定解析的**唯一实现**（R32 的机制化；由红队 Qwen 指出"R32 只是纪律不是机制"）。

本会话已出现 **6 种**写法，此前被复制到 4 个工具里，每次都要重新踩一遍：
  1. `### S1-001　**判定**：1`            （Kimi 内联）
  2. `**判定（决策方填）**：`_0__``        （决策方：数字填在横线内）
  3. 块式（`## S1-001` + 后续判定位）
  4. 逐行网格 `S1-001:1　S2-002:0`
  5. 表格行 `| S1-001 | 1 |`
  6. 无连字符编号 `## C001` / `## T001`

对外接口（**其他脚本一律引用这里，不得再复制**）：
    read_judgements(path) -> dict[uid -> "0"|"1"|"?"]   # 未填自动跳过；歧义条目拒收并记录
    parse_inline_text(text, ids, all_ids) -> (mapping, notes, ambig)
    slot_value(line) -> "0"|"1"|"?"|None|"AMBIG"
    load_availability(bus_dir) -> dict；is_unavailable(party, avail, now) 支持**到期自动失效**
自测：python rulings_io.py --self-test
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 编号：`S1-049`（带连字符）或 `C001`／`T001`（无连字符）
ID = r"[A-Z]{1,4}(?:\d{1,3}-\d{3}|\d{3})"
# 标题形如 `## S1-049`、`## S1-049　G12`，或**带后缀**（第 7 种变体：
# `## K001　[alert]　（v1 分数 0.9871）`）——后缀必须允许，否则整批漏读。
PAT_ID = re.compile(r"^#{2,4}\s*(" + ID + r")(?![\d\-])(?:\s*[\u3000 ]\s*G\d{1,3})?.*$")
PAT_ID_PREFIX = re.compile(r"^#{2,4}\s*(" + ID + r")")
PAT_INLINE = re.compile(r"^#{2,4}\s*(" + ID
                        + r")[^\n]*?\*\*判定\*\*\s*[:：]\s*[_\-—\s]*([012?])(?![0-9])")
PAT_TABLE = re.compile(r"\|\s*(" + ID + r")\s*\|\s*([012?])\s*\|")
PAT_PAIR = re.compile(r"(" + ID + r")\s*[=:：]\s*[_\-—\s]*([012?])(?![0-9])")
PAT_ANY_ID = re.compile(ID)
_UNFILLED = re.compile(r"^[_\-—\s?？]*$")
CELL = {"0": "0", "1": "1", "2": "?", "?": "?"}


def slot_value(line: str):
    """从判定位取稳妥值：取反引号内容里的 0/1/2。

    决策方实际写法是**在横线内填数字**（`` `_0__` ``、`` `__0_` ``），故不能要求"恰好一个字符"。
    返回 "0"/"1"/"?"／None（未填）／"AMBIG"（含两个不同数字，**绝不猜**）。
    """
    m = re.search(r"`([^`]*)`", line)
    content = m.group(1) if m else line
    digs = sorted({c for c in content if c in "012"})
    if len(digs) > 1:
        return "AMBIG"
    if not digs:
        return None
    return "?" if digs[0] == "2" else digs[0]


def read_judgements(path: str) -> tuple[dict, list]:
    """读任意格式的答题卡/席位文件 → ({uid: 值}, 歧义列表)。

    规则：跳过标题(#)、引用(>)、表格表头、代码块；只认数据行/数据块。
    """
    out, ambig = {}, []
    cur = None
    fence = False
    for ln in open(path, encoding="utf-8", errors="replace"):
        t = ln.strip()
        if t.startswith("```"):
            fence = not fence
            continue
        if fence or t.startswith(">"):
            continue
        # 5. 表格行
        mt = PAT_TABLE.search(t)
        if mt:
            out[mt.group(1)] = CELL[mt.group(2)]
            continue
        # 1. 内联（Kimi 风格：ID 与值同行）
        mi = PAT_INLINE.match(t)
        if mi:
            cur = mi.group(1)
            out[cur] = CELL[mi.group(2)]
            continue
        # 3. 块式标题
        m = PAT_ID.match(t)
        if m:
            cur = m.group(1)
            continue
        # 4. 逐行网格（同一行可有多个 `ID:值`）
        pairs = PAT_PAIR.findall(t)
        if pairs and len(pairs) >= 1 and not t.startswith("#"):
            for uid, v in pairs:
                out[uid] = CELL[v]
            if len(pairs) == 1:
                cur = pairs[0][0]
            continue
        # 2. 块内的判定位
        if cur and "判定" in t:
            v = slot_value(t)
            if v == "AMBIG":
                ambig.append(f"{cur}（内容 {t[:40]!r}）")
            elif v is not None:
                out[cur] = v
    return out, ambig


def parse_inline_text(text: str, ids: list, all_ids: list | None = None):
    """解析"聊天里回的一串"（4 种格式：按序数字、带编号、只报例外、区间）。

    返回 (mapping, notes, ambig)。只解析**数据行**（丢弃标题/引用/说明文字）。
    """
    out, notes, ambig = {}, [], []
    all_ids = all_ids or ids

    def g2s(tok):
        m = re.fullmatch(r"G(\d{1,3})", tok.strip(), re.I)
        if not m:
            return None
        k = int(m.group(1))
        return all_ids[k - 1] if 1 <= k <= len(all_ids) else None

    kept, fence = [], False
    for ln in text.splitlines():
        t = ln.strip()
        if t.startswith("```"):
            fence = not fence
            continue
        if fence or t.startswith(("#", ">", "|")):
            continue
        if not PAT_ANY_ID.search(t) and not re.search(r"\bG\d{1,3}\b", t, re.I) \
                and not re.fullmatch(r"[\s,;，；0-9?._\-]*", t):
            continue
        kept.append(ln)
    text = "\n".join(kept)

    # G 编号（绝对）
    for m in re.finditer(r"\bG(\d{1,3})\s*[=:：]\s*[_\-—\s]*([012?])(?![0-9])", text, re.I):
        sid = g2s("G" + m.group(1))
        if sid:
            out[sid] = CELL[m.group(2)]
        text = text.replace(m.group(0), " ")
    for m in re.finditer(r"G(\d{1,3})\s*\.\.\s*G(\d{1,3})\s*=\s*([0-9?.,\s]+)", text, re.I):
        a, b = int(m.group(1)), int(m.group(2))
        vals = [v for v in re.split(r"[,\s]+", m.group(3)) if v in CELL]
        for k, v in zip(range(a, b + 1), vals):
            sid = g2s("G" + str(k))
            if sid:
                out[sid] = CELL[v]
        text = text.replace(m.group(0), " ")
    # 区间 `S1-001..S1-020 = ...`
    for m in re.finditer(r"(" + ID + r")\s*\.\.\s*(" + ID + r")\s*=\s*([0-9.,\s]+)", text):
        a, b, vals = m.group(1), m.group(2), [v for v in re.split(r"[,\s]+", m.group(3)) if v]
        pre, na = a.split("-")[0], int(a.split("-")[1])
        nb = int(b.split("-")[1])
        for k, v in zip(range(na, nb + 1), vals):
            if v in CELL:
                out[f"{pre}-{k:03d}"] = CELL[v]
        text = text.replace(m.group(0), " ")
    # 只报例外
    m = re.search(r"(?:除|except)\s*(" + ID + r")\s*[=:：]\s*([0-9])\s*[，,]?\s*(?:外)?[，,]?\s*"
                  r"(?:其余|其他|全)\s*(?:为|是)?\s*([0-9])", text)
    if m:
        for i in ids:
            out[i] = CELL[m.group(3)]
        out[m.group(1)] = CELL[m.group(2)]
        text = text.replace(m.group(0), " ")
    # 带编号
    for uid, v in PAT_PAIR.findall(text):
        out[uid] = CELL[v]
    text = PAT_PAIR.sub(" ", text)
    # 按序数字
    rest = [v for v in re.split(r"[\s,;，；]+", text) if v in CELL]
    if rest:
        if len(rest) > len(ids):
            notes.append(f"按序数字 {len(rest)} 个 > 本批 {len(ids)} 条，多余的已忽略")
        for i, v in zip(ids, rest):
            out.setdefault(i, CELL[v])
    for v in re.split(r"[\s,;，；]+", text):
        if not v or v.startswith("#") or PAT_ANY_ID.fullmatch(v):
            continue
        if v in CELL or _UNFILLED.match(v):
            continue
        if re.fullmatch(ID + r"[:=：][_\-—?？]*", v):
            continue
        if not any(ch.isdigit() for ch in v):
            continue
        notes.append(f"无法解析的片段：{v[:20]}")
    return out, notes, ambig


def load_availability(bus_dir: str) -> dict:
    p = os.path.join(bus_dir, "availability.json")
    if not os.path.isfile(p):
        return {}
    try:
        return json.load(open(p, encoding="utf-8")).get("parties", {})
    except ValueError:
        return {}


def is_unavailable(party: str, avail: dict, now=None) -> bool:
    """是否不可用——**带到期自动失效**（红队 Qwen 指出：靠人工改 updated 会长期显示过期状态）。"""
    v = (avail or {}).get(party) or {}
    if v.get("status") != "unavailable":
        return False
    until = v.get("until") or ""
    if not until:
        return True
    try:
        t = datetime.datetime.strptime(until, "%Y-%m-%d %H:%M")
    except ValueError:
        return True
    return (now or datetime.datetime.now()) < t


def _self_test() -> int:
    import tempfile
    cases = [
        ("## S1-001\n\n**判定（决策方填）**：`_0__`\n", {"S1-001": "0"}, "横线内填数字"),
        ("### S2-037　**判定**：_1\n", {"S2-037": "1"}, "Kimi 内联"),
        ("| S3-071 | ? | 是 |\n", {"S3-071": "?"}, "表格行"),
        ("## C001\n\n**判定（决策方填）**：`__2_`\n", {"C001": "?"}, "无连字符编号 C###"),
        ("## T007\n\n**判定（决策方填）**：`___`\n", {}, "未填"),
        ("> 示例：S1-001=1 S1-002=0\n", {}, "引用块示例不得计入"),
        ("## S1-009\n\n**判定（决策方填）**：`_01_`\n", {}, "歧义（两个不同数字）拒收"),
        ("## K001　[alert]　（v1 分数 0.9871）\n\n**判定（决策方填）**：`_1__`\n",
         {"K001": "1"}, "标题带臂名与分数后缀（第 7 种变体）"),
    ]
    bad = 0
    for text, expect, label in cases:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            tmp = fh.name
        try:
            got, ambig = read_judgements(tmp)
        finally:
            os.remove(tmp)
        ok = got == expect and (bool(ambig) == ("歧义" in label))
        bad += 0 if ok else 1
        print(f"  [{'OK ' if ok else 'BAD'}] {label}：{got}"
              + (f"｜歧义 {len(ambig)}" if ambig else ""))
    # 可用性到期
    av = {"qwen": {"status": "unavailable", "until": "2020-01-01 00:00"}}
    expired_ok = is_unavailable("qwen", av) is False
    av2 = {"qwen": {"status": "unavailable", "until": "2099-01-01 00:00"}}
    active_ok = is_unavailable("qwen", av2) is True
    bad += 0 if (expired_ok and active_ok) else 1
    print(f"  [{'OK ' if expired_ok and active_ok else 'BAD'}] 可用性到期：过期→视为可用；未到期→不可用")
    print(f"  结果：{len(cases) + 1 - bad}/{len(cases) + 1} 通过")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    print(__doc__)
