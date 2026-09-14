# 04 证据链索引（哪个文件证明什么 · 怎么复算）

> 原则：项目里每一个结论都应有可复算的落点。本表给出"结论 → 证据文件 → 复算方式"。

## 一、数据与标注

| 结论 | 证据文件 | 复算方式 |
|---|---|---|
| 10 万条评论、字段与时间跨度（2000-2023） | `electronics_expanded.csv`、`docs/dataset_audit.md` | `python -c` 读表头/行数；时间戳覆盖率 100,000/100,000 |
| 规则初筛 1,502 条、弱标注精度 51.8% | `review_input.jsonl` / `review_result.jsonl`、`labeled_expanded.csv` | `merge_review.py` |
| 三星漏检 41.5%（n=200，CI 34.9%-48.4%） | `three_star_input.jsonl` / `three_star_result.jsonl`、`miss_rate.py` | `python miss_rate.py` |
| 正例 1,257 冻结口径 | `labeled_llm_before_treble.csv` | 统计 `sound_negative_llm==1` |
| 高音补捞 +31（84→124） | `treble_candidates.jsonl` / `treble_result.jsonl` | 对比 `labeled_llm.csv` 与 `_before_treble` |
| 中置信 8 条人工复核 3/8，全剔除 | `human_review_conf30.csv`、`confidence_tiered.md` | `retier_conf.py`、`a4_mid_remove.py` |
| 标注噪声 9.1%（人工终审 15/16） | `human_review_noise16.csv`、`error_taxonomy.md` | 与 `llm_err_classes.jsonl` 交叉核对 |
| 人工抽查 78%（50 条） | `human_review_50.csv` | 计通过率 |

## 二、模型与实验（冻结口径）

| 结论 | 证据文件 | 复算方式 |
|---|---|---|
| F1 0.6871 / CV 0.6234±0.024 / 基线 / p 值 | `results_summary.md`、`exp06_最终二分类模型/training_output.txt` | `test_model.py`、`distilbert_cv.py`、`baseline_cv.py`、`svm_ttest.py` |
| 混淆矩阵双口径（179/72 与 178/73） | `results_summary.md`（调和行）、`val_preds_dump.csv` | `val_pred_dump.py` 重跑推理 |
| 多标签宏 F1 0.6481 与逐类 F1 | `exp04_多标签归因/`、`results_summary.md` | `train_multilabel.py` 输出的评估段 |
| 消融 3 组 | `exp07_ablation_A/B/C`、`ablation_summary.md` | `ablation_train.py` |
| 学习曲线（无泄漏） | `learning_curve.png`、`learning_curve_results.json` | `learning_curve.py`（1257 点为 bootstrap 口径） |
| PR 曲线 AUC-PR 0.7191 | `pr_curve.png` | `pr_curve.py` |
| 年份分桶无衰减（2022 桶 0.80） | `docs/year_split_output.txt`（脚本输出原文） | `year_split_eval.py` |

## 三、验证深化（D6-D8）

| 结论 | 证据文件 | 复算方式 |
|---|---|---|
| LLM 对照（deepseek / qwen 三设置） | `llm_baseline.md`、`llm_eval_out_*.jsonl`、`llm_qwen_out_*.jsonl`、`llm_eval_metrics.json`、`llm_qwen_metrics.json` | `llm_eval_metrics.py`、`llm_qwen_metrics.py` |
| 长度分桶（截断桶 0.565） | `length_bucket_eval.md` | `length_bucket_eval.py`（tokenizer 口径） |
| 边界探针 7/10 | `edge_case_benchmark.md` | `edge_case_benchmark.py`（12 条定向样本） |
| 校准 ECE 0.0122 / 过度自信 | `calibration_eval.md`、`calibration_curve.png` | `calibration_eval.py` |
| 错误分类学（FP/FN 构成） | `error_taxonomy.md`、`llm_err_input.jsonl`、`llm_err_classes.jsonl`、`spot_check_30.jsonl` | `prep_err_taxonomy.py` + `taxonomy_agg.py` |
| 吞吐（GPU 1.763s / CPU 28.443s） | `throughput_eval.md` | `throughput_bench.py` |
| **高音归因失效机制**（零触发：最大概率 0.3332 < 阈值 0.5；阈值 0.20 → F1 0.5161；标签重叠 40.5%、关键词漏标 62.6%） | `docs/treble_failure_analysis.md` | `diagnose_treble.py`（只读诊断，复现验证划分） |
| 时序趋势图 | `trend_over_time.png`、`trend_over_time.py` | 同脚本 |

## 四、工程与部署

| 结论 | 证据文件 | 复算方式 |
|---|---|---|
| 在线 Demo 可用（单条 2/2、批量 15.1 秒） | `docs/D13_seal_declaration.md` §四 | `deploy_check.py` + `batch_check.py`（需公网） |
| 部署三次故障与修复记录 | `DEPLOY_GUIDE.md` 顶部 | 阅读文档 |
| DeepSeek/百炼 真实调用 | `llm_baseline.md` §2/§2b | 阅读文档 + 原始判定 jsonl |
| 提交包内容与校验值 | `docs/D13_seal_declaration.md` §三 | `hashes.py`、`pack_final.py` |

## 五、审计与格式合规

| 结论 | 证据文件 | 复算方式 |
|---|---|---|
| 文档数字同源、无违禁 claim | `number_audit.md` | `python check_doc_numbers.py`（143 项） |
| 主文档符合官方模板九章 | `number_audit.md` 末节"模板格式对照" | 同上（自动解析 `## 一、`…`## 九、` 结构） |
| 模板原文（对照基准） | `hackathon-复赛作品提交模板-天池版.docx` | `extract_template.py` 可重新抽取 |

## 六、原始记录规模（供 AI 判断证据充分度）

- 标注/复核 jsonl：17 个文件（`review_*`、`three_star_*`、`neg_review_*`、`conf_review_*`、`treble_*`）
- 对照实验判定：deepseek 13 个 + qwen 12 个 jsonl
- 人工复核表：3 张 CSV（50 条 / 8 条 / 16 条）
- 推理快照：`val_preds_dump.csv`（20,000 行，含 prob/pred/长度/标签）
