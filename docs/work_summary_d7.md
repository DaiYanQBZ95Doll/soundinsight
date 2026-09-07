# SoundInsight D7 工作总结（2026-09-05）

> 项目：SoundInsight 蓝牙耳机音质差评智能归因系统（AI+跨境黑客松巅峰赛·复赛，AI 市场洞察赛道）
> 团队：更新世界的锋芒。所有数字以 results_summary.md 为权威源，本文件为全周期工作汇总。

## 一、数据与标注

- 数据源：McAuleyLab Amazon Reviews 2023（AmazonElectronics 类目）10 万条真实评论；时间戳 100% 恢复（2000-10-07 → 2023-03-18），字段清单见 docs/dataset_audit.md。
- RLCA 两阶段标注：规则初筛（1502 条）→ LLM 全量复核（deepseek-chat）→ 三星评论召回补漏（479 条）。
- 标注质量：规则初筛精度 51.8% → LLM 复核后人工抽查 78%（n=50，Wilson 95% CI 64.8%-87.2%）；三星漏检率 41.5%。
- 正例口径演进：1257（冻结实验口径）→ 1288（高音补捞 +31）→ 1280（中置信复核移除 8）。
- 标注噪声：16 条候选人工终审 15/16 确认 → 噪声率约 9.1%（95% CI 5.6%-14.5%，候选集下界估算）。
- 时序验证：年份分桶 2014-2022 无单调衰减（2022 桶 F1@0.5=0.8049，覆盖 19,996/20,000），月度趋势图 trend_over_time.png。

## 二、模型与实验（全部冻结口径）

- 二分类：DistilBERT-base（66M），val_v2（20,000 条 / 251 正例）F1 0.687（阈值 0.9744）；5 折 CV 0.6234±0.024；AUC-PR 0.7191；Welch t 检验 p=0.000932，显著优于 SVM 0.497 / LR 0.410 / dummy 0.025。
- 混淆矩阵：冻结 TP=179/FP=91/FN=72；GPU 重跑 TP=178/FN=73（F1 0.685）已显性调和（results_summary.md）。
- 多标签五类归因：宏 F1 0.65（低音 0.79 / 清晰度 0.77 / 杂音 0.84 / 音量 0.84 / 高音 0，高音样本稀缺已披露）；复合差评（≥2 类）占 23.5%。
- 消融 3 组 + 无泄漏学习曲线（100→1257 正例，0.4067→0.6179）。

## 三、验证深化（D6-D8 遗憾消除清单，A-G 全部完成）

- LLM 对照（1000 条固定子集 = val_v2 正例全集 + 749 负例采样）：
  - deepseek-chat：零样本 0.940 / 5-shot 0.873 / 复核 0.846（tokens 24.9 万）
  - qwen3.7-plus（百炼 Token Plan）：零样本 0.9149 / 5-shot 0.8937 / 复核 0.8661（tokens 49.1 万）
  - 小模型同子集 0.826；口径声明含循环性红利与预训练记忆不可排除（llm_baseline.md）
- 长度分桶（tokenizer）：≤64 token 0.708 / 65-128 0.749 / >128（截断桶）0.565 —— 截断暴露面首次量化。
- 边界探针 12 条 7/10；发现多语言评论被静默判负，已做显式拒绝（is_unsupported）。
- 校准：ECE 0.0122，决策区间过度自信（[0.9,1.0) 置信 0.975 vs 实际 0.555）→ 全链路加"概率未经校准，仅供排序参考"。
- 错误分类学：FP=91/FN=73；误报 54.9% 为"其他问题"、漏报 58.9% 为委婉+双面；标注噪声 9.1%（人工终审）。
- 吞吐实测：GPU 1.76s / CPU 28.4s per 1000 条（throughput_eval.md）；旧"2 分钟"表述全部改为实测口径。

## 四、工程与产品

- 产品链路：soundinsight_agent.py（md/excel 报告、--lang zh|en、非英文跳过、成本对照行）、predict_core.py（共享推理核心）、api_server.py（FastAPI，curl 实测通过）、demo_sound_v2.py（Gradio 三页）、install.bat、MODEL_CARD.md。
- 合规：数据许可与 LLM-API 加工披露（README、v4 §5.4）；docs/drift_plan.md 漂移监控方案。
- 在线部署：ModelScope 创空间上线并发布（https://modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight）；权重托管 DaiYanQBZ95Doll/SoundInsight_models（LFS）。deploy_check 验收：单条 2/2、批量 100 条 15.1 秒。三次部署修复：torch ABI 硬钉冲突、平台敏感词回滚、下载路径 bug。
- §5.2 模型调用表：两行均为真实调用（qwen3.7-plus 百炼 Token Plan + deepseek-chat 官方 API），诚信闭环。

## 五、诚信与审计

- 数字审计脚本覆盖 12+ 文件、135 项检查全 PASS（number_audit.md）；废弃 claim 自动拦截。
- P0 修复四项全部落地：§5.2 表述、llm_baseline 口径（子集来源+循环性）、两套混淆矩阵调和、长度分桶 tokenizer 重做。
- 清理：白皮书/98% 无出处表述、qwen 错误表述、"2 分钟/99.6%"未实测表述、GPT-4 $0.01 旧成本 claim。

## 六、提交物状态

- 已完成：Demo.zip（50 文件，无权重/无开发脚本）、复赛作品 zip 骨架、competition_v3/v4、README、PPT 数字口径、video_script、feedback_template（空白待填）、deploy_check 脚本。
- 用户侧待办：GitHub push（本地约 19 个 commit）、PPT 精简 20→8-12 页、演示视频录制、真实用户反馈收集、最终 PDF 放入复赛作品 zip、（可选）Token Plan key 轮换、human_review_conf30 确认。
