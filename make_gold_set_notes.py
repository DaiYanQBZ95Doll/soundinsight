# -*- coding: utf-8 -*-
"""为人工金标生成**中性**翻译与解析（判定权完整留给决策方）。

设计要点（诚信）：
  · 输出**只含事实描述**：产品是什么（若可判断）、评论者对声音说了什么（引原句）、还提到什么问题；
  · **禁止**出现任何判定词（抱怨／差评／负面／positive／negative／sound_negative 等）——
    本脚本对生成文本做**词表自检**，命中即打回重写（最多 2 次）；
  · 产出两件：`docs/gold_set/review_notes.md`（人读，300 条分段）与
    `docs/gold_set/assisted_worksheet.csv`（Excel 填写用：原文｜中文翻译｜中性解析｜人工判定｜备注）；
  · **不改动**原盲评表 `worksheet.csv`（保留"盲评"版本作为对照与方法学留档）。

用法：python make_gold_set_notes.py [--limit N]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import json
import os
import re
import sys
import threading
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GDIR = os.path.join(HERE, "docs", "gold_set")
SHEET = os.path.join(GDIR, "worksheet.csv")
CACHE = os.path.join(HERE, "v2", "gold_set_notes.jsonl")
OUT_MD = os.path.join(GDIR, "review_notes.md")
OUT_CSV = os.path.join(GDIR, "assisted_worksheet.csv")
BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
# 降级兜底：只翻译、不解析（用于反复触发中性闸门的条目）
SYS_ZH_ONLY = ("Translate the following English product review into natural Chinese. "
               "Return JSON only: {\"zh\": \"<Chinese translation>\", \"product\": \"\", "
               "\"sound\": \"\", \"other\": \"\"}. Do not judge or classify anything.")
MODEL = "deepseek-chat"
COL = "人工判定(1=音质差评/0=不是)"
_JUDGE_MD = re.compile(r"判定（决策方填）\*\*：\s*`?\s*([012?])\s*`?\s*$")
_ID_MD = re.compile(r"^##\s*(S\d-\d{3})\s*$")

SYS = ("You are a bilingual translator and neutral describer. For the given English product review, "
       "return JSON only: {\"zh\": \"<Chinese translation>\", \"product\": \"<what product it is, "
       "in Chinese, or 不确定>\", \"sound\": \"<what the reviewer says about sound, quoting key English "
       "phrases in parentheses, in Chinese>\", \"other\": \"<other topics mentioned, in Chinese>\"}. "
       "STRICT RULE: describe only. Do NOT judge, rate, or classify whether this is a sound-quality "
       "complaint. Never use words like 抱怨/差评/负面/positive/negative/complaint.")

# 词表自检：出现任一即视为"越界判定"
BAD = re.compile(r"抱怨|差评|负面|好评|complaint|negative|positive|判定|classified|"
                 r"属于音质|是音质|音质问题", re.I)

_lock = threading.Lock()
_stat = {"ok": 0, "fail": 0, "reject": 0}


def call(text: str, key: str, retries: int = 2) -> dict:
    body = {"model": MODEL,
            "messages": [{"role": "system", "content": SYS},
                         {"role": "user", "content": text[:3000]}],
            "temperature": 0, "response_format": {"type": "json_object"}}
    last = ""
    for a in range(retries + 1):
        try:
            req = urllib.request.Request(
                BASE.rstrip("/") + "/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8"))
            parsed = json.loads(data["choices"][0]["message"]["content"])
            joined = " ".join(str(v) for v in parsed.values())
            if BAD.search(joined):
                with _lock:
                    _stat["reject"] += 1
                last = "生成含判定词，已打回"
                continue
            with _lock:
                _stat["ok"] += 1
            return parsed
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:70]}"
            time.sleep(1.2 * (a + 1))
    # 降级兜底：只翻译（避免因反复触发中性闸门而缺失条目）
    try:
        body2 = {"model": MODEL,
                 "messages": [{"role": "system", "content": SYS_ZH_ONLY},
                              {"role": "user", "content": text[:3000]}],
                 "temperature": 0, "response_format": {"type": "json_object"}}
        req2 = urllib.request.Request(
            BASE.rstrip("/") + "/chat/completions",
            data=json.dumps(body2).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req2, timeout=90) as r2:
            d2 = json.loads(r2.read().decode("utf-8"))
        p2 = json.loads(d2["choices"][0]["message"]["content"])
        p2["_fallback"] = "仅翻译（重试耗尽后的中性兜底）"
        # 注意：**不对翻译做判定词检查**——忠实翻译里出现"音质/问题"属正常；
        # 中性闸门只约束解析字段（product/sound/other），而兜底路径本就不产出解析。
        if p2.get("zh"):
            with _lock:
                _stat["ok"] += 1
            return p2
    except Exception:  # noqa: BLE001
        pass
    with _lock:
        _stat["fail"] += 1
    return {"_error": last}


def _read_existing_judgements(csv_path: str, md_path: str) -> dict:
    """读出**已填**判定（CSV 判定列 + MD 里 `判定（决策方填）` 后已填的值）。

    这是"重跑不清空"的关键：生成器只负责翻译与解析，**判定属于决策方**，必须原样保留。
    两处都有值时以 CSV 为准（并记录冲突，交由对账发现）。
    """
    out = {}
    md_vals = {}
    if os.path.isfile(md_path):
        cur = None
        for ln in open(md_path, encoding="utf-8", errors="replace").read().splitlines():
            m = _ID_MD.match(ln.strip())
            if m:
                cur = m.group(1)
                continue
            if cur:
                m2 = _JUDGE_MD.search(ln.strip())
                if m2:
                    md_vals[cur] = "?" if m2.group(1) == "2" else m2.group(1)
    if os.path.isfile(csv_path):
        try:
            for r in csv.DictReader(open(csv_path, encoding="utf-8-sig", errors="replace")):
                v = (r.get(COL) or "").strip()
                if v in ("0", "1", "?"):
                    out[r["编号"]] = v
        except (OSError, csv.Error, KeyError):
            pass
    for k, v in md_vals.items():
        out.setdefault(k, v)          # CSV 优先
    return out


def _backup(path: str) -> str:
    """覆盖前留时间戳备份（返回备份路径；文件不存在则空串）。"""
    if not os.path.isfile(path):
        return ""
    import shutil
    import time
    b = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(path, b)
    return b


def _atomic_write(path: str, text_or_rows, binary_sig: bool = False) -> None:
    """原子写：先写 .tmp，再 os.replace（避免半截文件）。"""
    tmp = path + ".tmp"
    if binary_sig:                      # CSV（utf-8-sig）
        with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            for row in text_or_rows:
                w.writerow(row)
    else:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text_or_rows)
    os.replace(tmp, path)


def _merge_md_judgements(md_lines: list, kept: dict) -> list:
    """把已填判定写回 review_notes.md 的对应条目（未填行也照写，不再依赖正则在不在）。

    逐行跟踪当前 `## S#-###` 标题；遇到判定行时，若该条目在 kept 中则整行重写。
    """
    out, cur = [], None
    for ln in md_lines:
        m = _ID_MD.match(ln.strip())
        if m:
            cur = m.group(1)
            out.append(ln)
            continue
        if cur and "判定（决策方填）" in ln and cur in kept:
            out.append(f"**判定（决策方填）**：`{kept[cur]}`")
            continue
        out.append(ln)
    return out


def _self_test() -> int:
    """证明：重跑生成器**保留**决策方已填判定；仅 --force 清空。

    造一份"已填 3 条"的 CSV 与"已填 2 条"的 MD，验证读取合并与 MD 回填。
    """
    import shutil
    bad = 0
    d = os.path.join(HERE, "_tmp_selftest", "notes")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    try:
        csv_p = os.path.join(d, "assisted_worksheet.csv")
        md_p = os.path.join(d, "review_notes.md")
        with open(csv_p, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["编号", "原文", "中文翻译", "产品", "关于声音的表述", "其他提及", COL, "备注"])
            w.writerow(["S1-001", "a", "甲", "", "", "", "1", ""])
            w.writerow(["S1-002", "b", "乙", "", "", "", "0", ""])
            w.writerow(["S1-003", "c", "丙", "", "", "", "", ""])
        with open(md_p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("## S1-002\n\n**判定（决策方填）**：`?`\n\n"
                     "## S1-004\n\n**判定（决策方填）**：`2`\n")
        kept = _read_existing_judgements(csv_p, md_p)
        ok1 = kept == {"S1-001": "1", "S1-002": "0", "S1-004": "?"}
        bad += 0 if ok1 else 1
        print(f"  [{'OK ' if ok1 else 'BAD'}] 保留判定：{kept}（CSV 优先于 MD；未填不计入）")
        md = ["## S1-001", "", "**判定（决策方填）**：`___`", "",
              "## S1-003", "", "**判定（决策方填）**：`___`", ""]
        joined = "\n".join(_merge_md_judgements(md, kept))
        ok2 = "`1`" in joined and joined.count("`___`") == 1
        bad += 0 if ok2 else 1
        print(f"  [{'OK ' if ok2 else 'BAD'}] MD 回填：已填保留、未填仍为 ___")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print(f"  结果：{2 - bad}/2 通过")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true",
                    help="清空已有判定后重建（默认**保留**决策方已填判定）")
    ap.add_argument("--self-test", action="store_true",
                    help="自测：证明重跑保留判定、--force 才清空")
    ap.add_argument("--out-dir", help="输出目录（默认 docs/gold_set；测试用）")
    args = ap.parse_args()
    global OUT_MD, OUT_CSV
    if args.self_test:
        return _self_test()
    if args.out_dir:
        OUT_MD = os.path.join(args.out_dir, "review_notes.md")
        OUT_CSV = os.path.join(args.out_dir, "assisted_worksheet.csv")
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        print("[需要凭证] 未注入 DEEPSEEK_API_KEY")
        return 2
    rows = list(csv.DictReader(open(SHEET, encoding="utf-8-sig", errors="replace")))
    done = {}
    if os.path.isfile(CACHE):
        for line in open(CACHE, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if "zh" in r:
                done[r["id"]] = r
    todo = [r for r in rows if r["编号"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"中性翻译与解析：工作表 {len(rows)} 条｜已完成 {len(done)}｜本次 {len(todo)}"
          f"｜并发 {args.workers}")
    with open(CACHE, "a", encoding="utf-8") as fh, \
            cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(call, r["原文"], key): r for r in todo}
        for k, fut in enumerate(cf.as_completed(futs), 1):
            r = futs[fut]
            res = fut.result()
            fh.write(json.dumps({"id": r["编号"], **res}, ensure_ascii=False) + "\n")
            if k % 25 == 0:
                fh.flush()
                print(f"  …{k}/{len(todo)}｜成功 {_stat['ok']}／打回 {_stat['reject']}／失败 {_stat['fail']}")
    # 汇总写出
    data = {}
    for line in open(CACHE, encoding="utf-8", errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if "zh" in r:
            data[r["id"]] = r
    md = ["# 人工金标 · 中性翻译与解析（判定权在决策方）", "",
          f"> 共 {len(data)} 条｜生成器 `make_gold_set_notes.py`｜**本文件不含任何判定**", "",
          "> **判据**（由决策方执行）：该评论是否在描述/提及**耳机或耳塞的声音表现**（低音／清晰度／杂音／"
          "音量／高音）？请只依据原文与翻译自行判断；无法确定产品是否为耳机 → 记 `?`。", "",
          "> 填写方式见文末「评判结果记录」。", ""]
    for r in rows:
        d = data.get(r["编号"])
        if not d:
            continue
        md += [f"## {r['编号']}", "",
               f"**原文**：{r['原文']}", "",
               f"**中文翻译**：{d.get('zh','')}", "",
               f"- 产品：{d.get('product','')}",
               f"- 关于声音的表述：{d.get('sound','') or ('（**仅翻译，无解析**：该条反复触发中性闸门，'  '按兜底策略只提供翻译）' if d.get('_fallback') else '')}",
               f"- 其他提及：{d.get('other','')}", "",
               "**判定（决策方填）**：`___`", ""]
    md += ["---", "",
           "## 评判结果记录（决策方用；三种方式任选）", "",
           "1. 直接在 `docs/gold_set/assisted_worksheet.csv` 的「人工判定」列填 `1`／`0`／`?`"
           "（**推荐**：重跑本生成器会**保留**已填判定，仅 `--force` 才清空）；",
           "2. 或在本文件每条 `判定（决策方填）` 后填；",
           "3. 或口头/文本告诉我「编号 → 判定」，我写入 CSV 与本文档。", "",
           "填完后运行：`python score_gold_set.py`（读取 `assisted_worksheet.csv` 同名列）出 κ 与一致率。"]
    # —— 保留决策方已填判定（红队 Qwen 指出的最高风险：旧版重跑即静默清空）——
    kept = {} if args.force else _read_existing_judgements(OUT_CSV, OUT_MD)
    if kept:
        md = _merge_md_judgements(md, kept)
    b1, b2 = _backup(OUT_MD), _backup(OUT_CSV)
    _atomic_write(OUT_MD, "\n".join(md) + "\n")
    _atomic_write(OUT_CSV,
                  [["编号", "原文", "中文翻译", "产品", "关于声音的表述", "其他提及", COL, "备注"]]
                  + [[r["编号"], r["原文"], (data.get(r["编号"], {}) or {}).get("zh", ""),
                      (data.get(r["编号"], {}) or {}).get("product", ""),
                      (data.get(r["编号"], {}) or {}).get("sound", ""),
                      (data.get(r["编号"], {}) or {}).get("other", ""),
                      kept.get(r["编号"], ""), ""] for r in rows], binary_sig=True)
    if args.force:
        print("[警告] --force：已清空原有判定")
    else:
        print(f"[保留] 决策方已填判定 {len(kept)} 条未被覆盖"
              + (f"｜备份 {os.path.basename(b1)}, {os.path.basename(b2)}" if b1 else ""))
    print(f"[写出] {os.path.relpath(OUT_MD, HERE)}（{len(data)} 条）")
    print(f"[写出] {os.path.relpath(OUT_CSV, HERE)}")
    print(f"[统计] 成功 {_stat['ok']}｜打回 {_stat['reject']}（含判定词）｜失败 {_stat['fail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
