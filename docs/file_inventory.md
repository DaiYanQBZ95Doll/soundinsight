# SoundInsight 项目文件总索引（file_inventory.md）

> 用途：项目文件整理与最终确认。列出仓库内**全部重要文件**的分类、用途与状态。
> 状态标记：✅ 提交物/冻结证据 ｜ 📄 文档 ｜ 🔧 脚本 ｜ 📊 生成产物 ｜ 🗄️ 参考材料 ｜ ⚠️ 已知偏差
> 生成于 D12；文件规模以当时实测为准。

## 一、目录约定

| 位置 | 内容 |
|---|---|
| 仓库根 | 数据 CSV、脚本、文档、图表、提交物 zip（扁平结构，便于评委直接查看） |
| `docs/` | 数据集考古、漂移计划、全流程记录、工作总结等过程文档 |
| `deployment/` | ModelScope 创空间部署包（app.py / requirements.txt / config.json / README_Space.md） |
| `exp01-09_*` | 训练与消融实验的原始输出归档（9 个实验目录） |
| `sound_model/`、`multi_label_model/` | 冻结模型权重（**不入 git**，见 .gitignore） |
| `distilbert-base-uncased/`、`roberta-base/` | 基座模型缓存（**不入 git**） |
| `.ms_upload_tmp/` | ModelScope 仓库推送暂存区（**不入 git**，已从打包排除） |
| `SoundInsight_创意方案/` | 初赛阶段的方案素材目录 |

## 二、数据文件（8 个，约 250MB）

| 文件 | 用途 | 状态 |
|---|---|---|
| `electronics_expanded.csv` (38MB, 10 万行) | 复赛主数据集：text / rating / timestamp（时间戳 100% 恢复） | ✅ |
| `labeled_expanded.csv` (38MB) | 规则初筛标注（弱标注，正例 1,502） | ✅ |
| `labeled_llm.csv` (39MB) | LLM 复核后标签（当前工作集正例 1,280） | ✅ |
| `labeled_llm_before_treble.csv` (39MB) | 高音补捞前备份（**冻结实验口径 1,257**） | ✅ |
| `labeled_llm_before_mid_demote.csv` / `_before_mid_remove.csv` (各 39MB) | 中置信处理前后备份（1,288 / 1,283 口径） | ✅ |
| `val_v2.csv` (7.2MB, 20,000 行 / 251 正例) | **固定验证集，红线冻结** | ✅ |
| `local_data.csv` (2.1MB) | 初赛数据集：前 5,000 条评论（fetch_electronics.py 产出） | 🗄️ |
| `labeled_data_final.csv` (2.1MB) | 初赛阶段标注数据（63 正例来源） | 🗄️ |
| `train_quick.csv` (1.2MB) | RoBERTa 快速验证用训练集 | 🗄️ |
| `sample_reviews_100.csv` (58KB) | 演示样例集（含 rating / 期望标签 / 类别） | ✅ |
| `electronics_prefix.bin` (128MB) | 原始下载前缀（gzip），可重新获取 | 🗄️ |

## 三、标注与 LLM 调用原始记录（证据链，14 个文件）

| 文件 | 用途 |
|---|---|
| `review_input.jsonl` / `review_result.jsonl` | 规则初筛候选的 LLM 复核（1,502 条口径） |
| `three_star_input.jsonl` / `three_star_result.jsonl` | 三星评论召回补漏复核（1,271→479） |
| `neg_review_input.jsonl` / `neg_review_result.jsonl` | 负例抽取复核 |
| `conf_review_input.jsonl` / `conf_review_result.jsonl` | 置信度分层复核 |
| `treble_candidates.jsonl` / `treble_result.jsonl` | 高音关键词补捞候选与复核结果 |
| `human_review_50.csv` | 人工抽查 50 条（78% 通过）原始记录 |
| `human_review_conf30.csv` | 中置信 8 条人工复核表（3/8 通过 → 全剔除） |
| `human_review_noise16.csv` | 标注噪声 16 条人工终审表（15/16 确认，含判定与备注） |

## 四、对照实验与评估记录

| 文件 | 用途 |
|---|---|
| `llm_eval_input.jsonl` (420KB) | LLM 对照子集：1,000 条（val_v2 正例全集 + 749 负例采样） |
| `llm_eval_small_preds.jsonl` (39KB) | 小模型同子集预测（阈值 0.9744） |
| `llm_eval_out_{zero,5shot,review}_*.jsonl` (13 个) | deepseek-chat 三设置判定原始输出 |
| `llm_qwen_out_{zero,5shot,review}_*.jsonl` (12 个) | qwen3.7-plus 三设置判定原始输出 |
| `llm_eval_metrics.json` / `llm_qwen_metrics.json` | 两侧指标汇总（口径：子集） |
| `llm_err_input.jsonl` / `llm_err_classes.jsonl` | 错误分类学输入（FP/FN 164 条）与 LLM 预分类结果 |
| `spot_check_30.jsonl` | DSH 抽查 30 条（与 LLM 类别一致 23/30） |
| `val_preds_dump.csv` (7.7MB) | val_v2 全量推理快照（prob/pred/长度/标签），C1/C3/C4 的公共输入 |
| `learning_curve_results.json` | 学习曲线各点结果 |

## 五、提交物与演示材料

| 文件 | 用途 | 状态 |
|---|---|---|
| `更新世界的锋芒_SoundInsight_Demo.zip` (105KB, 50 文件) | Demo 源码包（无权重、无开发脚本） | ✅ |
| `更新世界的锋芒_SoundInsight_复赛作品.zip` (104KB) | 复赛提交包骨架（含 Demo.zip + README_SUBMISSION.txt） | ✅ 待放入 PDF 与视频 |
| `更新世界的锋芒_SoundInsight_其他材料.zip` (466KB, 46 文件 + 说明) | 补充材料：验证报告 10 份、审计与验收脚本 4 个、人工复核原始表 3 张、图表 7 张、复算脚本 13 个、过程文档 5 份 | ✅ |
| `更新世界的锋芒_SoundInsight_复赛作品.pdf` (201KB, 9 页) | 主文档（脚本生成，内嵌宋体/黑体，WPS 等任意阅读器可开） | ✅ |
| `更新世界的锋芒_SoundInsight_复赛作品.docx` (48KB) | 主文档 Word 版（备用，WPS 可直接打开并输出 PDF） | ✅ |
| `md_to_pdf.py` / `md_to_docx.py` / `verify_docx.py` / `pack_final.py` / `hashes.py` | 主文档生成、校验、最终打包与校验值脚本 | 🔧 |
| `启动Demo.bat` | 双击启动本地 Gradio Demo（含代理绕过设置，纯英文提示避免 cmd 码页问题） | 🔧 |
| `打包提交包.bat` | 双击执行 `pack_final.py`：检查四项提交物并更新 `复赛作品.zip` | 🔧 |
| `SoundInsight：跨境电商耳机音质差评智能归因系统.pptx` (18.5MB, 20 页) | 演示 PPT（分工表述与耗时口径已修正） | ⚠️ 用户决定保留 20 页，不精简（与赛事建议的 8-12 页存在偏差，如实记录） |
| `video_script.md` | 演示视频脚本（200 秒 / 9 镜头 / 含台词，模板建议 3-5 分钟） | 📄 待录制 |
| `video_script_silent.md` | **无口播版拍摄卡**（9 个镜头的操作步骤 + 画面要点，适合不录音的纯演示） | 📄 |
| `video_script.srt` | 字幕文件（28 条 / 0:00-3:20，UTF-8，可直接导入剪映或 WPS 演示） | 📄 |
| `视频素材/`（8 张 1920×1080 PNG + `素材清单.md`） | **剪辑用满屏图**：标题卡、学习曲线、PR 曲线、混淆矩阵、校准曲线、系统架构、时序趋势、结尾卡；清单含时间轴对应表与剪映操作步骤 | 📄 待剪辑 |
| `architecture.png`、`learning_curve.png`、`pr_curve.png`、`confusion_matrix.png`、`trend_over_time.png`、`calibration_curve.png`、`demo_output.png` | 文档与 PPT 用图 | ✅ |
| `insight_report_v2.md` / `_en.md` / `insight_report.xlsx` | Agent 输出样例（中文 / 英文 / Excel 三形态） | 📊 |
| `ppt_text_dump.md` | PPT 文本提取（数字审计用） | 📊 |

## 六、核心文档

| 文件 | 用途 |
|---|---|
| `results_summary.md` | **冻结数字唯一权威源**（含 ±1 混淆矩阵调和行） |
| `number_audit.md` | 数字一致性审计结果（135 项 PASS；PPT 页数为已知偏差） |
| `competition_v4.md` / `competition_v3.txt` / `competition_v2.md/.txt` | 复赛完整版（11 章）/ 官方模板九章版 / 初赛版 |
| `llm_baseline.md` | LLM 对照报告（deepseek + qwen，含口径与循环性声明） |
| `length_bucket_eval.md` / `edge_case_benchmark.md` / `calibration_eval.md` / `error_taxonomy.md` / `throughput_eval.md` | 四项验证深化 + 吞吐实测报告 |
| `stats_validation.md` / `ablation_summary.md` / `significance_test.md` / `confidence_tiered.md` | 统计验证 / 消融 / 显著性 / 置信度分层 |
| `MODEL_CARD.md` / `docs/drift_plan.md` | 模型卡 / 漂移监控方案 |
| `qna_preparation.md` / `edge_cases.md` / `user_scenarios.md` / `action_report_template.md` | 答辩 Q&A（10 问）/ 边界案例 / 用户场景 / 报告模板 |
| `README.md` / `DEPLOY_GUIDE.md` | 仓库说明 / 部署指南（含三次部署修复记录） |
| `docs/dataset_audit.md` / `docs/year_split_output.txt` | 数据集字段考古 / 年份分桶脚本输出原文 |
| `docs/project_full_record.md` | **初赛→复赛全流程记录（最终确认用）** |
| `docs/D13_seal_declaration.md` | **D13 封包声明（提交 Kimi 最终审核用，含校验值与审核清单）** |
| `docs/file_inventory.md` | 本文件：全部项目文件分类索引 |
| `AI_HANDOFF/`（9 个文件） | **给 AI 助手的项目导览包**：`README.md`（入口与阅读顺序）、`01_project_overview.md`、`02_repo_map.md`（自动生成的文件地图）、`03_metrics_and_caveats.md`（三套口径与免责边界）、`04_evidence_index.md`（结论→证据→复算）、`05_code_guide.md`（代码导览）、`06_pending_and_redlines.md`（待办/红线/诚信记录）、`07_glossary.md`（术语表）、`manifest.json`（253 条目机器可读索引） |
| `docs/work_summary_d7.md` / `docs/process_review_d10.md` | D7 工作总结 / D10 全流程复盘 |
| `PROGRESS_SYNC.md` / `QWEN_HANDOFF.md` / `PROJECT_BRIEF_QWEN.md` / `REPO_INTRO.txt` | 过程同步与协作交接 |
| `AI_INDUCTION_REDLINE.md` | AI 协作红线与反诱导声明 |

## 七、脚本（按用途分组）

- **数据**：`fetch_electronics.py`、`extend_data.py`、`restore_timestamps.py`
- **标注**：`label_v3.py`、`label_final.py`、`prep_review_input.py`、`merge_review.py`、`prep_three_star.py`、`merge_three_star.py`、`prep_refine.py`、`merge_refine.py`、`prep_neg_review.py`、`retier_conf.py`、`prep_human_review.py`、`make_samples.py`
- **训练**：`train_final.py`、`train_multilabel.py`、`train_sound_model.py`、`train_roberta_quick.py`、`distilbert_cv.py`、`ablation_train.py`、`learning_curve.py`、`prep_quick_split.py`
- **评估与验证**：`test_model.py`、`baseline_cv.py`、`svm_ttest.py`、`pr_curve.py`、`finalize_curve.py`、`results_summary.py`、`miss_rate.py`、`distilbert_vs_llm.py`、`year_split_eval.py`、`val_pred_dump.py`、`calibration_eval.py`、`length_bucket_eval.py`、`edge_case_benchmark.py`、`taxonomy_agg.py`、`throughput_bench.py`、`trend_over_time.py`
- **LLM 对照与错误分析**：`prep_llm_eval.py`、`llm_eval_metrics.py`、`llm_qwen_metrics.py`、`prep_err_taxonomy.py`
- **产品**：`soundinsight_agent.py`、`predict_core.py`、`api_server.py`、`demo_sound_v2.py`（旧版 `demo_sound.py`）、`install.bat`、`download_models.py`、`verify_download_urls.py`、`config.json`
- **部署与验收**：`upload_models.py`、`deploy_check.py`、`batch_check.py`
- **审计与打包**：`check_doc_numbers.py`、`audit_ppt.py`、`build_submission.py`、`archive_exp.py`、`build_pdf.py`、`build_pdf_v2.py`、`capture_demo_output.py`、`final_acceptance.py`、`arch_diagram.py`
- **一次性修复脚本（留档）**：`fix_ppt_roles.py`、`ppt_speed_fix.py`、`a4_mid_remove.py`、`apply_mid_demotion.py`

## 八、日志与生成产物

| 文件 | 说明 |
|---|---|
| `capture_log.txt` / `summary_log.txt` | Demo 输出捕获 / 结果汇总日志（历史产物，生成于"未校准提示"加入之前，**不编辑历史日志**） |
| `training_output.txt`、`exp06_最终二分类模型/training_output.txt` | 训练日志（含早期 99.0%/98.8% 概率展示样例） |
| `exp01`-`exp09` 目录 | 各实验的原始输出（CV、消融、多标签、教师一致性等） |
| `.gitignore` | 排除权重、基座缓存、`*.log`、`*.bin`、暂存区等 |

## 九、本次整理删除的文件

| 文件 | 删除理由 |
|---|---|
| `SoundInsight：…智能归因系统.pptx.bak` (18.5MB) | 分工表述修正前的旧备份；当前 PPTX 已是修正版且经审计，备份不再需要（降低仓库体积） |
| `llm_qwen_out_zero_test.jsonl` | qwen 连通性测试的 5 条临时输出，不计入任何指标 |
| `insight_report.md` | 旧版（v1）报告输出，已被 `insight_report_v2.md` 取代 |
| `__pycache__/` | Python 字节码缓存（本地产物，未入 git） |

## 十、已知偏差与待办（如实）

1. **PPT 20 页**：高于赛事建议的 8-12 页；用户已决定不精简，作为已知偏差记录（`audit_ppt.py` 仍会标记该页数检查为 FAIL，属事实记录）。
2. **用户验证未开展**：无真实用户反馈（v4 §9.1 第 7 条）。
3. **提交物待补**：最终 PDF、演示视频（放入复赛作品 zip）。
4. **未推送变更**：本地若有未推送 commit，执行 `git push origin main`（SSL 报错加 `-c http.sslBackend=openssl`）。
