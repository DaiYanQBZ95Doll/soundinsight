# 实验证据索引（E3：修复仓库侧证据链断裂）

> **背景**：`exp01`–`exp06` 六个实验目录在**仓库中 0 个跟踪文件**（`git ls-files` 实测），
> 即冻结证据只存在于本地磁盘与 `results_summary.md` 的文字记录中。这构成"证据链在仓库侧断裂"
> （缺憾 A6-33），外部无法从仓库独立核验这些实验的原始输出。
> **本文件的作用**：把本地证据**逐目录登记为可定位的索引**（路径 + 关键文件 + 体量 + 是否入库 + 复现命令），
> 使第三方至少能知道"证据在哪、多大、由谁生成、如何重跑"；**大体积二进制（权重/图）不入库**，
> 依据 `docs/D13_seal_declaration.md` 的内容类/容器类划分。
> 生成：2026-09-30（执行方，按冻结清单 §二 E3）

---

## 一、逐目录登记

| 目录 | 用途 | 关键文件 | 体量 | 入库 |
|---|---|---|---|---|
| `exp01_弱标注交叉验证/` | 弱标注标签下的基线对照与 DistilBERT 5 折 CV | `baseline_cv.log`、`distilbert_cv.log` | 21 KB | **未入库**（可入库：纯文本日志） |
| `exp02_清洗标签交叉验证/` | LLM 清洗标签下的同一对照（最终口径） | `baseline_cv_clean.log`、`distilbert_cv_clean.log` | 12 KB | **未入库**（可入库） |
| `exp03_LLM复核与标签清洗/` | RLCA 两阶段标注的原始输入输出（候选 → 复核结果） | `review_result.jsonl`、`neg_review_result.jsonl`、`labeled_llm.csv`、`three_star_result.jsonl` | 39.3 MB | **未入库**（含评论原文与派生标签；`labeled_llm.csv` 已在仓库根目录另有副本） |
| `exp04_多标签归因/` | 五类多标签模型的训练与产物 | `multilabel.log`、`config.json`、`multi_label_model/issue_labels.json`、权重（`model.safetensors`） | 262 MB | **不入库**（权重类，与 `multi_label_model/` 同源） |
| `exp05_教师一致性/` | DistilBERT 与 LLM 教师标签的一致性（83.7%±2.1%） | `vs_llm.log` | 6 KB | **未入库**（可入库） |
| `exp06_最终二分类模型/` | 冻结模型（v1）的训练日志、混淆矩阵、产物 | `training_output.txt`、`train_final.log`、`confusion_matrix.png`、权重 | 262 MB | **部分入库**（`training_output.txt` 已在仓库根目录同名副本；权重与图不入库） |
| `exp07_ablation_A/`、`exp08_ablation_B/`、`exp09_ablation_C/` | 三组消融（**已入库**，各 3 个跟踪文件） | `config.json`、`training_output.txt`、`confusion_matrix.png` | 各约 40 KB | **已入库** |

## 二、复现命令（从仓库根目录执行）

| 目录 | 复现命令 | 前置 |
|---|---|---|
| exp01 | `python baseline_cv.py` + `python distilbert_cv.py` | `labeled_expanded.csv`（弱标注） |
| exp02 | 同上，标签换用 `labeled_llm.csv` | — |
| exp03 | `python label_v3.py` → LLM 复核脚本（需 API 凭证） | 原始候选来自 `electronics_expanded.csv` |
| exp04 | `python train_multilabel.py` | GPU；输出 `multi_label_model/` |
| exp05 | `python distilbert_vs_llm.py` | 冻结模型 + LLM 教师标签 |
| exp06 | `python train_final.py` | GPU；输出 `sound_model/`（**冻结，不得覆盖**） |

> 注：`exp03` 的 LLM 复核环节需要 API 凭证；**证凭缺失时该目录只能核验已有输出，无法重跑全链路**
> （与当前 W4 的阻塞同源，见 `PROGRESS_SYNC.md`）。

## 三、与对外数字的对应关系

| 对外数字 | 来源目录 | 交叉印证文件 |
|---|---|---|
| 基线 SVM 0.497 / LR 0.410 | exp01、exp02 | `results_summary.md` 基线对照两节 |
| CV 0.6234 ± 0.0240 | exp02 | `results_summary.md`「DistilBERT 交叉验证（LLM 清洗标签）」 |
| 主指标 F1@调优 0.6871 | exp06 | `results_summary.md`「最终二分类模型」+ `sound_model/threshold.json` |
| 多标签宏 F1 0.6481 | exp04 | `results_summary.md`「多标签问题归因」 |
| 教师一致性 83.7% ± 2.1% | exp05 | `results_summary.md`「教师一致性」（口径：仅方法说明，不作性能结论） |

## 四、后续动作（不属本轮范围，登记备查）

1. 三个纯文本日志目录（exp01/02/05）体积小、无隐私风险，**建议后续入库**以补齐证据链；
2. exp03 的 `*.jsonl` 含评论原文，入库前须评估再分发条款（同数据集授权）；
3. 权重类（exp04/exp06 与 `sound_model/`、`multi_label_model/`）**不入库**，改为登记 SHA256 与获取方式
   （见 `v2/README.md` 的 `weight_availability` 策略）。
