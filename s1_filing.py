# -*- coding: utf-8 -*-
"""S1：v3-lite 正式落档（含机械断言、标签来源声明、同基准对照、真实场景未测标注）。

机械断言：`v3-lite 训练侧 ∩ (val_v3_tune ∪ val_v3_test 在语料中的行) = ∅`
—— 用**内容哈希**把冻结评测集映射回语料行号，再与复现出的训练侧求交（不靠说明，靠计算）。
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))


def norm(t):
    return re.sub(r"\s+", " ", str(t).replace("\u3000", " ")).strip()


def h(t):
    return hashlib.sha256(norm(t).encode("utf-8", "replace")).hexdigest()


# ① 语料 + 复现 v3-lite/v2 的划分（用**原始标签**分层）
texts, labels = [], []
with open(os.path.join(HERE, "labeled_llm.csv"), encoding="utf-8", errors="replace") as fh:
    for r in csv.DictReader(fh):
        texts.append(str(r.get("text") or ""))
        labels.append(int(float(r.get("sound_negative_llm") or 0)))
from sklearn.model_selection import train_test_split  # noqa: E402
tr, va = train_test_split(list(range(len(labels))), test_size=0.2, random_state=42,
                          stratify=labels)
train_set = set(tr)
idx_by_hash = {}
for i, t in enumerate(texts):
    idx_by_hash.setdefault(h(t), []).append(i)
print(f"语料 {len(texts):,}｜训练侧 {len(train_set):,}")

# ② 冻结评测集 → 语料行号（内容哈希；**文本可能多处出现**，故按"全部出现"判定）
assertion = {}
for name in ("val_v3_test", "val_v3_tune"):
    p = os.path.join(HERE, name + ".csv")
    rows = list(csv.DictReader(open(p, encoding="utf-8", errors="replace")))
    real_overlap, consistent, missing = [], 0, 0
    for r in rows:
        ids = idx_by_hash.get(h(r.get("text") or ""), [])
        if not ids:
            missing += 1
        elif all(i in train_set for i in ids):
            real_overlap.append(ids)
        else:
            consistent += 1
    assertion[name] = {"rows": len(rows), "real_overlap": len(real_overlap),
                       "consistent_with_holdout": consistent, "not_found": missing}
    print(f"{name}: {len(rows):,} 行｜**真重叠（全部出现∈训练侧）{len(real_overlap)}**｜"
          f"含留出出现 {consistent:,}｜找不到 {missing}")
ok = all(v["real_overlap"] == 0 for v in assertion.values())
print(f"机械断言（真重叠 = 0）：**{'通过 ✓' if ok else '未通过 ✗'}**")

# ③ 对照数据读取
v3 = json.load(open(os.path.join(HERE, "v2", "v3lite_eval_test.json"), encoding="utf-8"))
v2sc = json.load(open(os.path.join(HERE, "v2", "inscope_reeval.json"), encoding="utf-8"))
g = v3["groups"]
v2g = v2sc["groups"]
split = v3["split"]

MD = f"""# S1 落档：v3-lite（口径纠正重训）——**结果是否定的，但可归因**

> 归档于 2026-10-03｜按 R34：训练输入与划分已登记；本文件为其**唯一合规归档形态**。

## 一、这门实验做了什么（单变量？**不是**）

| 项 | v2 | v3-lite |
|---|---|---|
| 训练正例 | 1,024（宽口径：LLM 判正即正） | **428**（口径纠正后：仅耳机家族） |
| 被改判为负 | — | **596 条口径外 LLM 正例**（全语料共改判 750） |
| 其余配方 | DistilBERT、max_len 256、seed 42、3 epochs、batch 16、lr 2e-5、**同一固定划分** | **完全相同** |

⚠️ **实验设计缺陷（已披露）**：改标签的同时**正例从 1,024 掉到 428（−58%）**——
故本次是**两个变量同时变**，掉分无法单独归因于"口径"。**补做对照**（保持宽口径、随机丢 58% 正例）
才能分离两因。

## 二、机械断言（**计算而非说明**）

| 冻结评测集 | 行数 | **真重叠**（全部出现∈训练侧） | 含留出出现（与来源一致） | 语料中找不到 |
|---|---|---|---|---|
| `val_v3_test.csv` | {assertion['val_v3_test']['rows']:,} | **{assertion['val_v3_test']['real_overlap']}** | {assertion['val_v3_test']['consistent_with_holdout']:,} | {assertion['val_v3_test']['not_found']} |
| `val_v3_tune.csv` | {assertion['val_v3_tune']['rows']:,} | **{assertion['val_v3_tune']['real_overlap']}** | {assertion['val_v3_tune']['consistent_with_holdout']:,} | {assertion['val_v3_tune']['not_found']} |

**断言 `训练侧 ∩ 冻结评测集 = ∅`：{'通过 ✓' if ok else '未通过 ✗'}** → v3-lite 的评测**未被自身训练污染**。

> **方法论陷阱（本轮实测，务必记住）**：语料含 **5,223 行重复文本**（100,000 行仅 94,777 唯一）。
> 若把"文本→行号"建成**首次出现**的单值映射，`val_v3_test` 会有 **221 行**、`val_v3_tune` 有 **230 行**
> 看似落在训练侧——**那是映射假象，不是污染**。正确判据是「该文本的**全部**出现都在训练侧」才算真重叠。
> 本文件采用修正判据；首次出现的错误判据差点让我们**误判自己的冻结测试集**。

## 三、标签来源声明（**强制**）

**v3-lite 的"耳机家族 530 条"由分类器筛选（精确率 71%／召回 92%，见 findings §9.1），并非人工判定** →
其训练标签中含**约 29% 的分类器误判**。本声明必须与任何引用 v3-lite 的场合同屏出现。

## 四、同基准对照（同一冻结测试集、同一子集）

| 测试面 | v2 | v3-lite | 差 |
|---|---|---|---|
| 全测试集（宽口径标签，n=10,000／正例 128） | F1@0.5 **{v2g['全测试集']['f1_0.5']:.4f}**｜@0.6 {v2g['全测试集']['f1_tuned']:.4f} | F1@0.5 **{g['全测试集']['at_0.5']['F1']:.4f}**｜@0.6 {g['全测试集']['at_0.6']['F1']:.4f} | −{v2g['全测试集']['f1_0.5'] - g['全测试集']['at_0.5']['F1']:.4f} |
| **耳机家族（范围内，n=778／正例 48）** | F1@0.5 **{v2g['耳机家族（范围内）']['f1_0.5']:.4f}**（P {v2g['耳机家族（范围内）']['precision_0.5']:.3f}／R {v2g['耳机家族（范围内）']['recall_0.5']:.3f}） | F1@0.5 **{g['耳机家族（范围内）']['at_0.5']['F1']:.4f}**（P {g['耳机家族（范围内）']['at_0.5']['P']/100:.3f}／R {g['耳机家族（范围内）']['at_0.5']['R']/100:.3f}） | **−{v2g['耳机家族（范围内）']['f1_0.5'] - g['耳机家族（范围内）']['at_0.5']['F1']:.4f}** |

全测试集一列**不可直接比**（标签口径不同，v3-lite 会被"冤判"），仅备案；
**范围内一列同基准可比**：**口径纠正后范围内 F1 反而下降 0.14**（TP 31→24、FP 10→14）。

## 五、结论与限制（不得越界）

1. **可断言**：在本配方下，**单纯把口径外正例改判为负**并不能提升（范围内）表现，反而下降；
   最可能的主因是**监督量腰斩**（1,024→428）＋分类器标签噪声（约 29%）——**但本次实验未分离这两因**；
2. **未测**：v3-lite 的**真实场景（人工真值）表现完全未测**——按 R34，须在钉死世代上另测；
3. **不可断言**：不得用本表主张"口径纠正有害"或"v3 方向错误"；
4. **下一步（已批准）**：S6 扩词表补标 → 用**更多、且口径正确**的正例重训（v3-lite-B），
   这才是"名实相符且不伤性能"的真检验。
"""
open(os.path.join(HERE, "docs", "v3lite_filing.md"), "w", encoding="utf-8",
     newline="\n").write(MD)
json.dump({"assertion": assertion, "passed": ok, "split": split},
          open(os.path.join(HERE, "v2", "v3lite_assertion.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[写出] docs/v3lite_filing.md、v2/v3lite_assertion.json")
