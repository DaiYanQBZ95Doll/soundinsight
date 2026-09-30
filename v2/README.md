# v2 产物目录（P0-2 骨架）

> **用途**：登记 v2（决赛口径）的可核验产物，使第三方能在**不获取权重**的前提下复算或核验。
> **审计联动**：`check_doc_numbers.py` 的"v2 可核验产物检查"读取 **`v2/v2_artifacts.json`**；该文件不存在时该项为 `SKIP`。
> **当前状态**：**SKIP（骨架阶段）**——`v2_artifacts.json` **尚未创建**，因为其 `model_sha256` 等字段必须指向真实存在的产物文件，写入占位值会让审计 FAIL。
> **创建时机**：W5（重训 + 阈值扫描 + 5 折 CV）产出 v2 模型与评估输出后，由执行方按 `v2_artifacts.template.json` 的字段填入真实值。

## 字段要求（审计强制）

| 字段 | 含义 | 形式 |
|---|---|---|
| `model_sha256` | 权重文件路径 → SHA256 映射 | 对象；路径相对仓库根 |
| `threshold_json` | 阈值文件路径 → SHA256 | 同上（含 `@调优` 与 `@0.5` 两档取值） |
| `train_command` | 可复算的训练命令（含种子与超参） | 字符串 |
| `eval_outputs` | 评估原始输出文件列表（路径 → SHA256） | 对象；至少含 `val_v3_test` 主指标原始输出 |
| `model_card` | v2 MODEL_CARD 路径 | 字符串 |

**附加要求（冻结清单 §二 P0-2）**：须同时明确**权重提供策略**——沿用复赛做法（上传公开模型仓库供第三方核验），或显式声明"仅提供哈希与训练命令，第三方需重训复算"。二者必居其一，不得留空。

## 生成顺序（改完 v2 产物后）

```
python check_doc_numbers.py     # v2 产物检查须由 SKIP 转 PASS
python scan_repo_hygiene.py
python make_ai_handoff.py       # 最后跑，刷新 manifest
```
