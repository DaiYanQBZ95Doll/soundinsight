# 文档数字一致性审计

## 关键文件完整性（体积下限，防静默截断）
- [PASS] docs/frozen_execution_checklist.md：59371 B ≥ 40000 B
- [PASS] PROGRESS_SYNC.md：42187 B ≥ 20000 B
- [PASS] docs/final_project_review_and_execution_plan.md：36884 B ≥ 15000 B
- [PASS] competition_v4.md：21214 B ≥ 20000 B
- [PASS] results_summary.md：4870 B ≥ 4000 B
- [PASS] AI_HANDOFF/manifest.json：81875 B ≥ 20000 B
- 结论：关键文件体积均正常

## 产品代码健康检查（编译 + 标签污染）
- [PASS] report_builder.py：可编译且无标签污染
- [PASS] deployment/report_builder.py：可编译且无标签污染
- [PASS] soundinsight_agent.py：可编译且无标签污染
- [PASS] demo_sound_v2.py：可编译且无标签污染
- [PASS] demo_sound.py：可编译且无标签污染
- [PASS] api_server.py：可编译且无标签污染
- [PASS] text_utils.py：可编译且无标签污染
- 结论：产品模块健康（编译通过、无 [v1]/[v2] 直贴数字）

## competition_v3.txt
- [PASS] 最终模型 F1 (0\.687): 行 57,144
- [PASS] 5折CV平均F1 (0\.6234): 行 144
- [PASS] CV标准差 (0\.024): 行 144
- [PASS] 阈值 (0\.97): 行 57,144
- [PASS] 召回率 (89\.6): 行 56,144
- [PASS] 精确率（须标阈值档：0.9744 档 66.3% / 0.5 档 47.9%） (47\.9|66\.3): 行 57,144
- [PASS] SVM基线 (0\.497): 行 144
- [PASS] LR基线 (0\.410): 行 144
- [PASS] dummy基线 (0\.025): 行 144
- [PASS] AUC-PR (0\.7191): 行 144
- [PASS] t检验p值 (0\.000932): 行 144
- [PASS] 正例(实验口径) (1257): 行 132,150
- [PASS] 人工抽查精度 (78%): 行 144
- [PASS] 三星漏检率 (41\.5%): 行 37
- [PASS] 弱标注精度 (51\.8%): 行 144
- [PASS] 未发现 错误正例数1297
- [PASS] 未发现 教师一致性出现在正文（仅允许方法说明/附录）
- [PASS] 未发现 已废弃的qwen标注复核claim

## competition_v4.md
- [PASS] 最终模型 F1 (0\.687): 行 65,149,165,209,213
- [PASS] 5折CV平均F1 (0\.6234): 行 222
- [PASS] CV标准差 (0\.024): 行 222
- [PASS] 阈值 (0\.97): 行 65,165,179,213,216
- [PASS] 召回率 (89\.6): 行 64,214,217,263
- [PASS] 精确率（须标阈值档：0.9744 档 66.3% / 0.5 档 47.9%） (47\.9|66\.3): 行 65,209,213,214,216
- [PASS] SVM基线 (0\.497): 行 205,230
- [PASS] LR基线 (0\.410): 行 229
- [PASS] dummy基线 (0\.025): 行 205,228
- [PASS] AUC-PR (0\.7191): 行 205,250
- [PASS] t检验p值 (0\.000932): 行 233
- [PASS] 正例(实验口径) (1257): 行 149,177,185,189,246
- [PASS] 人工抽查精度 (78%): 行 177,277
- [PASS] 三星漏检率 (41\.5%): 行 45,175
- [PASS] 弱标注精度 (51\.8%): 行 177
- [PASS] 未发现 错误正例数1297
- [PASS] 未发现 教师一致性出现在正文（仅允许方法说明/附录）
- [PASS] 未发现 已废弃的qwen标注复核claim

## README.md
- [PASS] 最终模型 F1 (0\.687): 行 85
- [PASS] 5折CV平均F1 (0\.6234): 行 85
- [PASS] CV标准差 (0\.024): 行 85
- [PASS] 阈值 (0\.97): 行 16,85
- [PASS] 召回率 (89\.6): 行 85
- [PASS] 精确率（须标阈值档：0.9744 档 66.3% / 0.5 档 47.9%） (47\.9|66\.3): 行 85
- [PASS] SVM基线 (0\.497): 行 85
- [PASS] LR基线 (0\.410): 行 85
- [PASS] dummy基线 (0\.025): 行 85
- [PASS] AUC-PR (0\.7191): 行 85
- [PASS] t检验p值 (0\.000932): 行 85
- [PASS] 正例(实验口径) (1257): 行 76
- [PASS] 人工抽查精度 (78%): 行 85
- [PASS] 三星漏检率 (41\.5%): 行 76
- [PASS] 弱标注精度 (51\.8%): 行 85
- [PASS] 未发现 错误正例数1297
- [PASS] 未发现 教师一致性出现在正文（仅允许方法说明/附录）
- [PASS] 未发现 已废弃的qwen标注复核claim

## QWEN_HANDOFF.md
- [PASS] 最终模型 F1 (0\.687): 行 21,42
- [PASS] 5折CV平均F1 (0\.6234): 行 21,44
- [PASS] CV标准差 (0\.024): 行 21,44,46
- [PASS] 阈值 (0\.97): 行 21,42
- [PASS] 召回率 (89\.6): 行 21,42
- [PASS] 精确率（须标阈值档：0.9744 档 66.3% / 0.5 档 47.9%） (47\.9|66\.3): 行 21,42
- [PASS] SVM基线 (0\.497): 行 46
- [PASS] LR基线 (0\.410): 行 46
- [PASS] dummy基线 (0\.025): 行 46
- [PASS] AUC-PR (0\.7191): 行 52
- [PASS] t检验p值 (0\.000932): 行 46
- [PASS] 正例(实验口径) (1257): 行 33,34,52
- [PASS] 人工抽查精度 (78%): 行 38
- [PASS] 三星漏检率 (41\.5%): 行 38
- [PASS] 弱标注精度 (51\.8%): 行 38
- [PASS] 未发现 错误正例数1297
- [PASS] 未发现 教师一致性出现在正文（仅允许方法说明/附录）
- [PASS] 未发现 已废弃的qwen标注复核claim

## ppt_text_dump.md
- [PASS] 最终模型 F1 (0\.687): 行 33,36,39
- [PASS] 5折CV平均F1 (0\.6234): 行 33
- [PASS] CV标准差 (0\.024): 行 33
- [PASS] 阈值 (0\.97): 行 33,39
- [PASS] 召回率 (89\.6): 行 33,39,48
- [PASS] 精确率（须标阈值档：0.9744 档 66.3% / 0.5 档 47.9%） (47\.9|66\.3): 行 33
- [PASS] SVM基线 (0\.497): 行 36
- [PASS] LR基线 (0\.410): 行 36
- [PASS] dummy基线 (0\.025): 行 36
- [PASS] AUC-PR (0\.7191): 行 36
- [PASS] t检验p值 (0\.000932): 行 36
- [PASS] 正例(实验口径) (1257): 行 24
- [PASS] 人工抽查精度 (78%): 行 24,57
- [PASS] 三星漏检率 (41\.5%): 行 15
- [PASS] 弱标注精度 (51\.8%): 行 21,24
- [PASS] 未发现 错误正例数1297
- [PASS] 未发现 教师一致性出现在正文（仅允许方法说明/附录）
- [PASS] 未发现 已废弃的qwen标注复核claim

## llm_baseline.md
- [PASS] LLM零样本F1 (0\.940): 行 22,38,41,45,46
- [PASS] 小模型子集F1 (0\.826): 行 21,41,45,50
- [PASS] LLM 5示例F1 (0\.873): 行 41,46,50
- [PASS] LLM复核模式F1 (0\.846): 行 24,41,47
- [PASS] LLM实验tokens合计 (249,703): 行 26
- [PASS] LLM零样本召回 (0\.9044): 行 22
- [PASS] 小模型子集召回 (0\.7092): 行 21
- [PASS] LLM零样本Acc (0\.971): 行 22
- [PASS] 单批40条延迟实测 (2,560|2552): 行 28
- [PASS] qwen零样本F1 (0\.9149): 行 36,50
- [PASS] qwen实验tokens合计 (490,747): 行 40

## qna_preparation.md
- [PASS] Q3/Q5/Q10 LLM零样本F1 (0\.940): 行 10,16,31
- [PASS] Q3 小模型子集F1 (0\.826): 行 10
- [PASS] Q10 5示例F1 (0\.873): 行 31
- [PASS] 每1000条LLM成本 (0\.03): 行 10,16,31
- [PASS] 未发现 已废弃的GPT-4单条$0.01成本claim
- [PASS] 未发现 已废弃的未实测30秒claim
- [PASS] 未发现 已废弃的纯LLM标注$50成本claim

## throughput_eval.md
- [PASS] GPU 1000条中位数(秒) (1\.763): 行 8
- [PASS] GPU 吞吐(条/s) (567\.1): 行 8
- [PASS] CPU 1000条中位数(秒) (28\.443): 行 10
- [PASS] CPU 吞吐(条/s) (35\.2): 行 10

## calibration_eval.md
- [PASS] ECE十箱 (0\.0122): 行 18
- [PASS] 0.8-0.9箱实际正例率 (0\.229): 行 15,20
- [PASS] 0.9-1.0箱实际正例率 (0\.555): 行 16,20

## error_taxonomy.md
- [PASS] 误报数 (FP=91): 行 3
- [PASS] 漏报数 (FN=73): 行 3
- [PASS] FP其他问题占比 (54\.9%): 行 11,79
- [PASS] FN委婉+双面占比 (58\.9%): 行 80
- [PASS] 标注噪声率(人工终审) (9\.1%): 行 82
- [PASS] 人工终审确认数 (15/16): 行 75,82
- [PASS] 与冻结矩阵的调和说明 (TP=179): 行 4

## length_bucket_eval.md
- [PASS] <=64 token F1 (0\.7080|0\.708): 行 7
- [PASS] 65-128 token F1 (0\.7485|0\.749): 行 13
- [PASS] >128 token F1(截断桶) (0\.5649|0\.565): 行 19
- [PASS] >128 token 评论数 (3728): 行 17,25,26
- [PASS] token 口径声明 (tokenizer): 行 1,3

## MODEL_CARD.md
- [PASS] ECE十箱 (0\.0122): 行 25
- [PASS] 阈值 (0\.9744): 行 14,20
- [PASS] 标注噪声率(人工终审) (9\.1%): 行 29
- [PASS] 当前工作集正例数 (1280): 行 13

## results_summary.md
- [PASS] 最终F1 (0\.687): 行 53,55
- [PASS] GPU重跑矩阵调和行 (TP=178): 行 58
- [PASS] GPU重跑FN (FN=73): 行 58
- [PASS] 冻结矩阵 (TP=179): 行 57

## 模板格式对照（官方复赛模板九章 + 在线链接表）
- competition_v4.md：正文章节 13 个
  - [PASS] 模板必备章节：九章齐备
  - [PASS] 章节编号重复：无
  - [PASS] 在线链接填写表
  - [PASS] 团队信息已填写
- competition_v3.txt：正文章节 9 个
  - [PASS] 模板必备章节：九章齐备
  - [PASS] 章节编号重复：无
  - [PASS] 在线链接填写表
  - [PASS] 团队信息已填写

## 口径配对检查（阈值档，全指标）
- [PASS] competition_v4.md：跨档指标均已标注阈值档
- [PASS] competition_v3.txt：跨档指标均已标注阈值档
- [PASS] README.md：跨档指标均已标注阈值档
- [PASS] QWEN_HANDOFF.md：跨档指标均已标注阈值档
- [PASS] MODEL_CARD.md：跨档指标均已标注阈值档
- [PASS] AI_HANDOFF/01_project_overview.md：跨档指标均已标注阈值档
- [PASS] AI_HANDOFF/03_metrics_and_caveats.md：跨档指标均已标注阈值档
- [PASS] docs/retrospective_and_reflection.md：跨档指标均已标注阈值档
- [PASS] docs/finals_stage.md：跨档指标均已标注阈值档
- [PASS] docs/v2_acceptance_benchmark.md：跨档指标均已标注阈值档
- [PASS] docs/final_project_review_and_execution_plan.md：跨档指标均已标注阈值档
- [PASS] docs/final_review_and_execution_plan.md：跨档指标均已标注阈值档
- [PASS] docs/gap_and_roadmap_inventory.md：跨档指标均已标注阈值档
- [PASS] docs/external_sources_register.md：跨档指标均已标注阈值档
- [PASS] docs/frozen_execution_checklist.md：跨档指标均已标注阈值档
- [PASS] docs/pre_lock_completeness_audit.md：跨档指标均已标注阈值档
- [PASS] docs/completeness_audit_round2.md：跨档指标均已标注阈值档
- [PASS] docs/N_line_handoff_protocol.md：跨档指标均已标注阈值档
- [注意] ppt_text_dump.md：0 行跨档未标（无）——PPT 不在提交包内，需用户决定是否改

## 代际检查（当前代：v1）
- [PASS] competition_v4.md：无未标注的代际混用
- [PASS] competition_v3.txt：无未标注的代际混用
- [PASS] README.md：无未标注的代际混用
- [PASS] QWEN_HANDOFF.md：无未标注的代际混用
- [PASS] MODEL_CARD.md：无未标注的代际混用
- [PASS] AI_HANDOFF/01_project_overview.md：无未标注的代际混用
- [PASS] AI_HANDOFF/03_metrics_and_caveats.md：无未标注的代际混用
- [PASS] docs/retrospective_and_reflection.md：无未标注的代际混用
- [PASS] docs/finals_stage.md：无未标注的代际混用
- [PASS] docs/v2_acceptance_benchmark.md：无未标注的代际混用
- [PASS] docs/final_project_review_and_execution_plan.md：无未标注的代际混用
- [PASS] docs/final_review_and_execution_plan.md：无未标注的代际混用
- [PASS] docs/gap_and_roadmap_inventory.md：无未标注的代际混用
- [PASS] docs/external_sources_register.md：无未标注的代际混用
- [PASS] docs/frozen_execution_checklist.md：无未标注的代际混用
- [PASS] docs/pre_lock_completeness_audit.md：无未标注的代际混用
- [PASS] docs/completeness_audit_round2.md：无未标注的代际混用
- [PASS] docs/N_line_handoff_protocol.md：无未标注的代际混用
- [PASS] docs/project_full_record.md：无未标注的代际混用
- [PASS] PROGRESS_SYNC.md：无未标注的代际混用

## 否定性状态断言检查（D7）
- [PASS] 20 份当前态文档中，否定性状态断言均带日期/来源指针或属豁免语境

## 跨材料口径一致性检查（M0b）
- [PASS] README 含全部三句权威表述要素
- [PASS] 更新世界的锋芒_SoundInsight_决赛入围定稿作品.docx 含全部三句权威表述要素

## 提交包冻结校验（红线 9）
- [PASS] hashes.txt 记录的是已提交版本（e6cae286515ef1d2 vs 冻结值 e6cae286515ef1d2）
- [PASS] 磁盘上的包与已提交版本一致（e6cae286515ef1d2 vs e6cae286515ef1d2）

## 决赛模板合规检查（模板九节 + 5.2 百炼栏事实）
- 目标文档：更新世界的锋芒_SoundInsight_决赛入围定稿作品.docx（27162 字符）
  - [PASS] 模板九节：齐备
  - [PASS] 章节编号唯一：无
  - [PASS] 在线链接表：已含链接
  - [PASS] 团队信息已填写
  - [PASS] 5.2 百炼栏按既成事实填写（qwen3.7-plus=有、百炼/Token Plan=有、假称未使用=无）

## v2 可核验产物检查
- [PASS] v2 产物登记齐全且哈希一致
