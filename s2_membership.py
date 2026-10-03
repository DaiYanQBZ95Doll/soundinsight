# -*- coding: utf-8 -*-
"""S2d + S2c：人工真值与冻结评测集的**内容哈希**归属，以及 v1/v2 在 v1 真留出侧上的命中计数。

S2d：500 条人工判定 → 落在 val_v3_test / val_v3_tune 各多少（raw + normalized 两口径），分层构成 S1–S5。
S2c：落在 v1 真留出侧 val_v2 的条目 → 跑 v1 与 v2 推理 → **只报计数**（不报方向性结论）。
     判读限制写死：n=109／正例 8，未达可断言样本量，仅报计数与区间。

用法：python s2_membership.py
产物：v2/s2_membership.json、docs/s2c_true_holdout.md
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
COL = "人工判定(1=音质差评/0=不是)"
STRATA = ("S1", "S2", "S3", "S4", "S5")


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", str(t).replace("\u3000", " ")).strip()


def h(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8", "replace")).hexdigest()


def load_human():
    """→ list of (uid, text, label|None, stratum)"""
    rows = []
    ws = {r["编号"]: r["原文"] for r in csv.DictReader(
        open(os.path.join(HERE, "docs/gold_set/worksheet.csv"), encoding="utf-8-sig",
             errors="replace"))}
    lab = {r["编号"]: (r.get(COL) or "").strip() for r in csv.DictReader(
        open(os.path.join(HERE, "docs/gold_set/assisted_worksheet.csv"),
             encoding="utf-8-sig", errors="replace"))}
    for uid, t in ws.items():
        v = lab.get(uid, "")
        rows.append((uid, t, 1 if v == "1" else (0 if v == "0" else None), uid.split("-")[0]))
    for f, st in (("docs/gold_set/s1_add100.csv", "S4"),
                  ("docs/gold_set/s5_clean_probe.csv", "S5")):
        for r in csv.DictReader(open(os.path.join(HERE, f), encoding="utf-8-sig",
                                     errors="replace")):
            v = (r.get(COL) or "").strip()
            rows.append((r["编号"], r["原文"], 1 if v == "1" else (0 if v == "0" else None), st))
    return rows


def load_ref(path):
    raw, nrm = set(), set()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            t = str(r.get("text") or "")
            raw.add(h(t))
            nrm.add(h(norm(t)))
    return raw, nrm


def wilson(k, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


human = load_human()
print(f"人工条目 {len(human)}（S1–S5）")

refs = {name: load_ref(os.path.join(HERE, fn)) for name, fn in
        (("val_v3_test", "val_v3_test.csv"), ("val_v3_tune", "val_v3_tune.csv"),
         ("val_v2", "val_v2.csv"))}

# ---------------- S2d ----------------
s2d = {}
for name in ("val_v3_test", "val_v3_tune"):
    raw, nrm = refs[name]
    hit_raw = [u for u, t, _y, _s in human if h(t) in raw]
    hit_nrm = [u for u, t, _y, _s in human if h(norm(t)) in nrm]
    comp = {}
    for u in hit_nrm:
        st = u.split("-")[0]
        comp[st] = comp.get(st, 0) + 1
    s2d[name] = {"hit_raw": len(hit_raw), "hit_norm": len(hit_nrm),
                 "ids": hit_nrm, "by_stratum": comp}
    print(f"S2d {name}：命中 {len(hit_nrm)} 条（raw {len(hit_raw)}）｜分层 "
          + "｜".join(f"{k} {v}" for k, v in sorted(comp.items())))

# ---------------- S2c ----------------
raw_v2, nrm_v2 = refs["val_v2"]
sel = [(u, t, y, s) for u, t, y, s in human if h(norm(t)) in nrm_v2]
comp = {}
for u, _t, _y, s in sel:
    comp[s] = comp.get(s, 0) + 1
lab = [x for x in sel if x[2] is not None]
pos = [x for x in lab if x[2] == 1]
print(f"\nS2c 落入 v1 真留出侧：**{len(sel)} 条**｜可比对 **{len(lab)}**｜正例 **{len(pos)}**"
      f"｜'?' {len(sel)-len(lab)}")
print("  分层：" + "｜".join(f"{k} {v}" for k, v in sorted(comp.items())))

spec = importlib.util.spec_from_file_location("rwe", os.path.join(HERE, "realworld_eval.py"))
rwe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rwe)
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
t2 = json.load(open(os.path.join(HERE, "v2", "threshold.json"), encoding="utf-8"))
texts = [x[1] for x in lab]
y = [x[2] for x in lab]
models = {}
_PROBS = {}
for name, d, ml, thr in (("v1（出厂）", cfg["bin_model_dir"], 128, float(cfg.get("threshold", 0.5))),
                         ("v2（候选）", os.path.join(HERE, "v2", "model_maxlen256"), 256,
                          float(t2.get("thr", 0.6)))):
    if not os.path.isdir(d):
        print(f"  [跳过] {name}：{d} 不存在")
        continue
    p = rwe.predict(texts, d, ml)
    _PROBS[name] = p
    rec = {"dir": os.path.relpath(d, HERE), "max_len": ml, "thr_own": thr,
           "hits_own_thr": int(sum(1 for a, b in zip(y, p) if a == 1 and b >= thr)),
           "hits_at_0.5": int(sum(1 for a, b in zip(y, p) if a == 1 and b >= 0.5)),
           "alerts_own_thr": int(sum(1 for b in p if b >= thr)),
           "positives": len(pos)}
    lo, hi = wilson(rec["hits_own_thr"], len(pos))
    rec["hit_rate_own_thr"] = round(rec["hits_own_thr"] / max(1, len(pos)), 4)
    rec["hit_rate_ci"] = [round(lo, 3), round(hi, 3)]
    models[name] = rec
    print(f"  {name}：正例 {len(pos)} 条中命中 **{rec['hits_own_thr']}**（阈值 {thr}）"
          f"｜@0.5 命中 {rec['hits_at_0.5']}｜告警 {rec['alerts_own_thr']} 条"
          f"｜命中率 {rec['hit_rate_own_thr']:.3f}（95% CI {lo:.3f}–{hi:.3f}）")

out = {"s2d": s2d,
       "s2c": {"n_total": len(sel), "n_comparable": len(lab), "n_positives": len(pos),
               "n_unclear": len(sel) - len(lab), "by_stratum": comp,
               "ids": [x[0] for x in sel], "positives_ids": [x[0] for x in pos],
               "models": models,
               "reading_limit": "n=109／正例 8，未达可断言样本量：仅报命中计数与区间，"
                                "不做方向性归因，不写『v1 真实场景 F1 ≈ X』"}}
# ---- 分层拆解（必须：112 条含 S2/S3 等非"真实场景"层，混报会被误读） ----
per = {}
for name, r in models.items():
    p = _PROBS[name]
    per[name] = {}
    for st in STRATA:
        idx = [i for i, x in enumerate(lab) if x[3] == st]
        if not idx:
            continue
        yy = [lab[i][2] for i in idx]
        pp = [p[i] for i in idx]
        k = sum(1 for a, b in zip(yy, pp) if a == 1 and b >= r["thr_own"])
        alerts = sum(1 for b in pp if b >= r["thr_own"])
        lo2, hi2 = wilson(k, sum(yy))
        per[name][st] = {"n": len(idx), "positives": sum(yy), "hits": k,
                         "alerts": alerts,
                         "hit_rate": round(k / sum(yy), 3) if sum(yy) else None,
                         "hit_rate_ci": None if not sum(yy) else [round(lo2, 3), round(hi2, 3)]}
        print(f"  [{name}][{st}] n={len(idx)} 正例={sum(yy)} 命中={k} 告警={alerts}"
              + (f" 命中率={k/sum(yy):.3f}" if sum(yy) else ""))
out["s2c"]["per_stratum"] = per
# 真实场景子集（S1/S4/S5，闸门外三层）
real_ids = [i for i, x in enumerate(lab) if x[3] in ("S1", "S4", "S5")]
for name, r in models.items():
    p = _PROBS[name]
    yy = [lab[i][2] for i in real_ids]
    pp = [p[i] for i in real_ids]
    k = sum(1 for a, b in zip(yy, pp) if a == 1 and b >= r["thr_own"])
    lo3, hi3 = wilson(k, sum(yy))
    out["s2c"].setdefault("realworld_subset", {})[name] = {
        "n": len(real_ids), "positives": sum(yy), "hits": k,
        "alerts": sum(1 for b in pp if b >= r["thr_own"]),
        "hit_rate": round(k / max(1, sum(yy)), 3),
        "hit_rate_ci": [round(lo3, 3), round(hi3, 3)]}
    print(f"  [真实场景子集 S1+S4+S5][{name}] n={len(real_ids)} 正例={sum(yy)} 命中={k}"
          f"｜命中率 {k/max(1,sum(yy)):.3f}（CI {lo3:.3f}–{hi3:.3f}）")
json.dump(out, open(os.path.join(HERE, "v2", "s2_membership.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

md = ["# S2c：v1 真留出侧（val_v2）上的人工真值口径", "",
      f"> 世代钉死：`labeled_llm_before_treble.csv`（sha256 全量 `7618d2976deffe56…`）"
      f"＋真留出侧 `val_v2.csv`（`1779a6404323d7fb…`）", "",
      f"**条目 {len(sel)}｜可比对 {len(lab)}｜正例 {len(pos)}｜「无法判断」{len(sel)-len(lab)}**", "",
      "分层构成：" + "｜".join(f"{k} {v}" for k, v in sorted(comp.items())), "",
      "| 模型 | 自带阈值 | 正例中命中 | 命中率 | 95% CI | @0.5 命中 | 告警条数 |",
      "|---|---|---|---|---|---|---|"]
for name, r in models.items():
    md.append(f"| {name} | {r['thr_own']} | **{r['hits_own_thr']}/{r['positives']}** | "
              f"{r['hit_rate_own_thr']:.3f} | {r['hit_rate_ci'][0]}–{r['hit_rate_ci'][1]} | "
              f"{r['hits_at_0.5']} | {r['alerts_own_thr']} |")
md += ["", "**判读限制（预注册）**：n=109／正例 8，**未达可断言样本量**——"
       "仅报命中计数与区间，**不做方向性归因**；不得写作「v1 真实场景 F1 ≈ X」。",
       "本表归档位置：**附录探索性数字**，不进正文、不进摘要、不进状态卡。"]
open(os.path.join(HERE, "docs", "s2c_true_holdout.md"), "w", encoding="utf-8",
     newline="\n").write("\n".join(md) + "\n")
print("\n[写出] v2/s2_membership.json、docs/s2c_true_holdout.md")
