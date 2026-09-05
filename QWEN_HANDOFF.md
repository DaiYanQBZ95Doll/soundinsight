# SoundInsight 项目全貌说明（供协作 AI 阅读）

## 一、项目定位与当前阶段

项目名称：SoundInsight 蓝牙耳机音质差评智能归因系统

赛事：AI+跨境黑客松巅峰赛 · 复赛（天池渠道），复赛提交截止 9 月 15 日，参赛场景为 AI 市场洞察。

一句话定义：为跨境电商耳机卖家提供音质差评自动识别与五类问题归因的一站式洞察工具，将人工数小时的差评梳理压缩至分钟级。

当前阶段：初赛已通过，复赛技术工作全部完成，处于 D3 技术修复与材料整合收尾期。最终提交 PDF 为 SoundInsight_创意方案_v5.pdf（初赛版），复赛版文档为 competition_v3.txt（按官方模板九章结构）。

工作目录：C:\deepseek-harness-master\soundinsight（Git 仓库，远程 https://github.com/DaiYanQBZ95Doll/soundinsight.git，本地已提交，远程推送由用户手动执行）

## 二、红线约束（协作 AI 必须遵守）

1. 不得改动模型权重目录 sound_model、multi_label_model。
2. 不得改动训练脚本 train_final.py、ablation_train.py、train_multilabel.py、distilbert_cv.py、train_roberta_quick.py、learning_curve.py。
3. 不得改动验证集划分，train/val 以 seed=42 分层划分为准，固定验证集文件为 val_v2.csv（20000 条 / 251 正例）。
4. 不得重新训练任何模型。
5. 冻结数字不得改动：F1 0.687、阈值 0.97、5 折 CV 0.6234 ± 0.024、召回率 89.6%、初赛 F1 0.37。所有文档数字必须与 results_summary.md 同源。
6. 模型权重不入库，.gitignore 已排除 sound_model、multi_label_model、distilbert-base-uncased、roberta-base 等目录。
7. GPU（RTX 4060 8GB）任务必须串行，CPU 任务可并行。

## 三、数据与标注现状

数据源：McAuley Lab 官方 Amazon Electronics 2023 数据集，通过 HTTP Range 分段拉取 128MB 前缀，解析出十万条真实评论。

核心数据文件：

- electronics_expanded.csv：十万条原始评论（text、rating）。
- labeled_expanded.csv：规则初筛标注（关键词单词边界匹配 + 评分阈值），弱标注正例 1502 条。
- labeled_llm.csv：LLM 复核后的最终标签集。当前正例数为 1280 条（1257 → 高音补捞 +31 → 中期置信复核移除 8）。注意：提交文档中冻结的历史口径为 1257 条，两者差异已记录在案，引用时需注明口径。
- labeled_llm_before_treble.csv：高音补捞合并前的备份（1257 条口径）。
- val_v2.csv：固定验证集，20000 条含 251 正例，所有评估必须用它。
- train_quick.csv：RoBERTa 快速验证用的小训练集。

标注方法论（RLCA 两阶段）：规则初筛召回候选 → LLM 全量复核去伪 → 三星补漏复核。关键数字：弱标注精度 51.8%，三星评论漏检率 41.5%，三星补漏复核 1271 条确认 479 条，人工抽查 50 条通过率 78%，置信度分层为高置信 471 条、中置信 8 条、低置信 0 条。

## 四、模型与实验结果（以 results_summary.md 为唯一权威）

最终二分类模型：DistilBERT-base（66M 参数），训练配置为 1:10 欠采样（约 1006 正例 + 10060 负例）、学习率 2e-5、batch 16、epochs 3。验证集 20000 条（251 正例）上准确率 0.9865，F1@0.5 为 0.6241，调优阈值 0.9744（对外口径 0.97）后 F1 0.6871，召回率 89.6%，精确率 47.9%。模型保存在 sound_model，阈值在 sound_model/threshold.json。

交叉验证：清洗标签 5 折逐折调优 F1 为 0.6655、0.6151、0.6325、0.6054、0.5983，均值 0.6234 ± 0.0240，波动 3.9%。弱标注标签 10 折调优 F1 均值 0.5487。

基线对比（清洗标签）：全判正常 0.025，TF-IDF+逻辑回归 0.410，TF-IDF+线性 SVM 0.497。显著性检验：SVM 五折重跑均值 0.5365 ± 0.0242，Welch t 检验 p = 0.000932，DistilBERT 显著更优。

多标签归因：五类问题（低音、清晰度、杂音、音量、高音），宏 F1 0.65，低音 0.79、清晰度 0.77、杂音 0.84、音量 0.84、高音 0。模型在 multi_label_model。

消融实验（exp07-09）：A 无采样调优 F1 0.6486 但召回率仅 0.53；B class_weight 平衡更差（0.6304）；C Focal Loss 0.6423 未超最终模型。结论：现有 1:10 欠采样 + 交叉熵方案最优。

统计验证：PR 曲线 AUC-PR 0.7191；学习曲线（100/300/500/800/1000/1257 正例）最终值 0.4067/0.5214/0.5099/0.5256/0.5666/0.6179，1257 档为 bootstrap 口径（1006 条不重复训练正例有放回采样，验证集零重叠）。

RoBERTa 快速验证：仅 2 epoch 探测，调优 F1 0.6169，未充分收敛，仅作基座对比参考，不具选型意义（结论已软化写入 results_summary.md）。

教师一致性：小模型与 LLM 标签一致率 83.7% ± 2.1%，仅用于说明蒸馏可行性，不作为性能证据。

## 五、工程组件

- soundinsight_agent.py：一键洞察 Agent，输入 CSV 输出六节结构报告（总体概况/问题分布/典型案例/行动建议/验证指标/附注），优先级自动计算，支持 --format md|excel、--lang zh|en，非英文评论跳过并计数，附成本对照行；输出 insight_report_v2.md（/v2_en.md）。
- predict_core.py：共享推理核心（agent / api_server / benchmark 同路径），E7 非英文显式拒绝（is_unsupported）。
- api_server.py：FastAPI HTTP API（GET /health、POST /predict），默认 127.0.0.1:7860。
- install.bat：Windows 一键安装（venv + 依赖 + 模型下载 + 自检）。
- demo_sound_v2.py：Gradio Demo，三个 Tab，单条评论判定、批量 CSV 分析、边界案例展示（六类场景，概率硬编码）。端口 7860。
- config.json：模型目录、阈值文件、标签映射集中配置，Agent 与 Demo 均读取它。
- test_model.py：验证集评估，输出指标、阈值扫描、混淆矩阵，支持 --csv/--label 参数。
- 数据管线脚本：fetch_electronics.py、extend_data.py、label_v3.py、prep_review_input.py、prep_three_star.py、merge_review.py、merge_three_star.py、prep_refine.py、merge_refine.py、retier_conf.py。
- 文档：README.md、results_summary.md、competition_v2.txt/md（初赛版全文）、competition_v3.txt（复赛九章模板版）、competition_v4.md（11 章完整版）、stats_validation.md、ablation_summary.md、significance_test.md、confidence_tiered.md、edge_cases.md、user_scenarios.md、action_report_template.md、qna_preparation.md、PROGRESS_SYNC.md、llm_baseline.md（Batch B LLM 对照，口径声明已按 P0-2 修正）、length_bucket_eval.md（tokenizer 口径，P0-4 重做）、edge_case_benchmark.md、calibration_eval.md、error_taxonomy.md（含与冻结矩阵的调和说明）、throughput_eval.md（E3）、MODEL_CARD.md、docs/drift_plan.md、docs/dataset_audit.md、docs/year_split_output.txt（年份分桶脚本输出原文）、human_review_noise16.csv（标注噪声人工终审文件）。
- 图表：architecture.png、learning_curve.png、pr_curve.png、confusion_matrix.png、demo_output.png、trend_over_time.png、calibration_curve.png。
- 实验归档：exp01 至 exp06 与 exp07_ablation_A/B/C 目录。

## 六、当前进行中与待办

进行中：无 GPU 任务。D5 五个批次均已落地；D6-D8 遗憾消除清单：Batch B（LLM 对照：零样本 F1 0.940 / 5-shot 0.873 / 复核 0.846 vs 小模型子集 0.826，tokens 24.9 万，Q3/Q5/Q10 已改写）、Batch C（长度分桶 / 边界探针 / ECE 0.0122 校准 / 错误分类学 FP=91 FN=73）、Batch E（api_server + predict_core + install.bat + 吞吐实测 GPU 1.76s/1000 条 + MODEL_CARD + --lang en + 成本对照 + 非英文拒绝）、Batch F（数据许可与 LLM-API 披露 + docs/drift_plan.md）均已完成并通过数字审计（120 项 PASS）。PPT"2 分钟/99.6%"已改为实测口径。Batch G 收尾进行中。

待办（按优先级）：

1. 用户在命令行执行 git push（命令：git push origin main，报 schannel 错误时加 -c http.sslBackend=openssl）；DSH 亦会尝试用 openssl 参数推送。
2. 人工审核 human_review_conf30.csv（8 条中置信样本，判定列填 1 或 0）；另新增 human_review_noise16.csv（16 条 LLM 判定为标注噪声的错误样本，含人工判定列），建议用户过一遍以把 9.8% 噪声率从"AI 说"变为"人说"。
3. 标注噪声终审：error_taxonomy.md 中 LLM 判定约 9.8% 错误样本为标注问题（AI 判定，未人工终审）——人工终审文件 human_review_noise16.csv 已备好，见上一条。
4. 诚信核查（已处理）：v3/v4 5.2 节旧表述已按路线 (a) 改为 deepseek-chat / DeepSeek 官方 API，阿里云百炼栏如实填"未使用"。
   若用户提供 Token Plan Key 并选择路线 (b)，可用 qwen3.7-plus 重跑 Batch B 对照，并把表格改回"已使用"。
5. ModelScope 创空间：**已部署成功并验收通过（2026-09-05）**。地址 https://modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight（直链 .ms.show）。deploy_check 结果：页面 200、单条推理 2/2（负面→杂音归因、正面→正常，含校准提示）、批量 100 条 15.1 秒（12 差评，分布与本地一致）。三次修复记录见 DEPLOY_GUIDE.md 顶部。
6. 演示视频录制（按 video_script.md，2-3 分钟）。
7. 真实用户反馈收集（feedback_template.md，禁止预填）。
8. PPT 视觉走查与精简（当前 20 页，超出 8-12 页要求）。
9. 最终 PDF 导出并放入 更新世界的锋芒_SoundInsight_复赛作品.zip。

## 七、环境事实

Windows，Python 3.12，RTX 4060 Laptop 8GB，torch 2.7.1+cu118，transformers 5.9.0，gradio 6.24.0，scikit-learn 1.8.0。

网络：Hugging Face 官方被墙（401），基座模型一律从 ModelScope 镜像下载；数据源 mcauleylab.ucsd.edu 可达；DeepSeek API 密钥仅存在于 DSH 宿主进程环境中，沙箱内不可见；pip 安装需要沙箱权限升级。

## 八、已知坑（不要重复踩）

1. PDF 排版曾被另一个 AI 的文本提取工具误判为乱码与换行丢失，经人工确认 PDF 完全正常，不要再"修复"。
2. 历次错别字清单（试看、儿乎、每大、可题、儿分钟、实家等）经全文检索均不存在，不要再检索修复。
3. 结果数字引用必须以 results_summary.md 为准，文档、Demo、PDF 必须同源。
4. 训练日志由 PowerShell Tee 产生，可能为 UTF-16 编码，读取脚本需兼容（results_summary.py 已处理）。
5. Python 脚本运行前建议设置环境变量 PYTHONIOENCODING=utf-8，避免 GBK 控制台报错。
