# -*- coding: utf-8 -*-
"""生成 v2 产物登记（`v2/v2_artifacts.json`）与 `v2/MODEL_CARD_v2.md`。

依据（冻结清单 §二 P0-2 / W5）：审计的"v2 可核验产物"检查要求
`v2/v2_artifacts.json` 含 model_sha256 / threshold_json / train_command /
eval_outputs / model_card，并对登记的哈希**逐个校验**；缺文件或哈希不符即 FAIL。
本脚本从**实际产物**计算哈希，因此天然一致。

同时写明**权重提供策略**（P0-2 的附加要求，二者必居其一）。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.join(HERE, "v2")


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    model_dir = os.path.join(V2, "model_maxlen256")
    weight = os.path.join(model_dir, "model.safetensors")
    if not os.path.isfile(weight):
        print(f"[FAIL] 缺少权重 {weight}")
        return 1

    # 1) 阈值文件：写入 v2 选定的调优档与高召回档
    thr_path = os.path.join(V2, "threshold.json")
    threshold = {"gen": "[v2]",
                 "tuned": 0.6,
                 "high_recall": 0.5,
                 "tuned_selected_on": "val_v3_tune（扫描网格 0.05–0.95）",
                 "reported_on": "val_v3_test",
                 "note": "两档口径与 v1 的 0.9744/0.5 不同，因标签集与训练划分均为 v2 口径；不可跨代混用"}
    with open(thr_path, "w", encoding="utf-8") as fh:
        json.dump(threshold, fh, ensure_ascii=False, indent=2)
    print(f"[写出] {os.path.relpath(thr_path, HERE)}")

    # 2) MODEL_CARD
    card_path = os.path.join(V2, "MODEL_CARD_v2.md")
    card = """# MODEL_CARD v2（决赛口径）

> 生成：2026-09-30 ｜ 代际标签 `[v2]` ｜ 与 v1 的关系：**不同标签集与不同划分，指标不可直比**

## 模型
- 架构：DistilBERT-base-uncased（二分类头）；训练数据 `labeled_llm.csv`（100,000 条，正例 1,280）
- 训练超参：max_len **256**、epochs 3、batch 16、lr 2e-5、seed 42、分层 80/20 留出划分
- 产物：`v2/model_maxlen256/`（权重 + tokenizer）

## 主指标（`val_v3_test`，n=10,000／正例 128）
- 阈值在 `val_v3_tune` 上选定（**0.6**），指标在 test 上报：
  - **F1@调优(0.6) = 0.7220**（P 77.0%／R 68.0%，TP87/FP26/FN41）
  - F1@0.5 = 0.7206（P 74.8%／R 69.5%）
  - **PR-AUC = 0.7811**
- 采纳闸门第 (1) 条：F1@调优 ≥0.72 或 PR-AUC ≥0.75 → **通过**（本页见 `v2/w5_final.md`）

## 校准（W7）
- 温度缩放 T=1.59（只在 `val_v3_tune` 上拟合）；test 决策区间 ≥0.9 偏差 −0.172 → **−0.060**
- 抗稀释 ECE（p≥0.5）0.222 → 0.117；整体 ECE 0.0055 → 0.0024（**被 98.7% 负例稀释**）

## 归因（多标签，W2）
- 五类逐类阈值（tune 选）：低音 0.25／清晰度 0.25／杂音 0.35／音量 0.6／高音 0.25
- test 宏 F1 **0.8273**（统一 0.5 档 0.7180）；高音 F1 0.5333
- **限定**：归因模型只在**正例**上训练与评估（RLCA 第二阶段）

## 已知边界（必须随模型一同引用）
- 长文本：>128 token 桶召回 51.2%（截断）～82.9%（切窗），**未达 70% 验收线**（见 `docs/w1_longtext_variants.md`）
- 标注噪声 9.1%（CI 5.6–14.5%）；共享教师偏差；无第二标注者
- 无真实用户验证（无渠道）
- v1 的阈值选择偏差已披露；v2 起采用 tune/test 分离

## 权重提供策略
- **policy = hash_and_command_only**：仓库**不存权重**（`.gitignore` 排除 `v2/model_*/`），
  提供 SHA256 与训练命令供第三方复算；如需权重本体，由决策方另行决定分发方式。
"""
    with open(card_path, "w", encoding="utf-8") as fh:
        fh.write(card)
    print(f"[写出] {os.path.relpath(card_path, HERE)}")

    # 3) 登记（哈希由实际文件计算）
    eval_files = [os.path.join(V2, n) for n in
                  ("w5_final.json", "w5_final.md", "w2_perclass_thresholds.json",
                   "w7_calibration.json")]
    eval_outputs = {os.path.relpath(p, HERE): sha(p) for p in eval_files
                    if os.path.isfile(p)}
    registry = {
        "_说明": "v2 可核验产物登记；哈希由 gen_v2_artifacts.py 从实际文件计算，审计会逐个校验",
        "generation": "[v2]",
        "created_at": "2026-09-30",
        "model_sha256": {os.path.relpath(weight, HERE): sha(weight)},
        "threshold_json": {os.path.relpath(thr_path, HERE): sha(thr_path)},
        "train_command": ("python v2_w1_longtext.py train --max-len 256 "
                          "--out-dir v2/model_maxlen256  # seed 42, epochs 3, batch 16, lr 2e-5"),
        "eval_outputs": eval_outputs,
        "model_card": os.path.relpath(card_path, HERE),
        "weight_availability": {
            "policy": "hash_and_command_only",
            "url": None,
            "note": "仓库不含权重；提供 SHA256 与训练命令供复算。分发权重本体须决策方另行决定。",
        },
        "generation_note": ("v1（复赛已提交口径）数字见 results_summary.md；"
                            "v1 与 v2 的标签集与划分不同，指标不可直比"),
    }
    reg_path = os.path.join(V2, "v2_artifacts.json")
    with open(reg_path, "w", encoding="utf-8") as fh:
        json.dump(registry, fh, ensure_ascii=False, indent=2)
    print(f"[写出] {os.path.relpath(reg_path, HERE)}")
    print(f"  权重 SHA256: {registry['model_sha256'][os.path.relpath(weight, HERE)][:16]}…")
    print(f"  评估产物 {len(eval_outputs)} 个已登记")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
