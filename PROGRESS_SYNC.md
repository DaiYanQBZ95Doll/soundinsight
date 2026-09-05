# SoundInsight 执行记录

## D5 缺陷修复执行记录（历史）

（A1-C3 见下方，全部 PASS。）

## 修复结果（A1-C3）

- A1 下载链路目录前缀：PASS。verify_download_urls.py 输出 11 行 URL 全部含目录前缀；download_models.py 与 deployment/app.py 均已改为 FilePath={dname}/{fname}。
- A2 上传路径与前置检查：PASS。upload_models.py 路径修正为项目根目录，模型目录缺失时直接报错退出；dry-run 实测列出 10 个文件共 537MB，不执行 git 推送。
- A3 无出处表述：PASS。README、competition_v2.txt、competition_v2.md、build_pdf.py 四处白皮书 98% 表述全部删除；.py/.md/.txt 全文检索"白皮书"与"98%"命中 0（数据 CSV 内评论原文中的 98% 属真实数据，不在清理范围）。
- B1 样例集 rating 回填：PASS。sample_reviews_100.csv 共 100 条，rating 分布 1 星 15、2 星 9、3 星 10、4 星 15、5 星 51，无 0 值；Agent 实测平均评分 3.78；类别组成与修复前一致（12/62/24/2）。
- B2 审计脚本修复与终审：PASS。PPT 审计截断自动核对区消除自匹配；四份目标文件（competition_v4.md、README.md、QWEN_HANDOFF.md、ppt_text_dump.md）FAIL 计数均为 0。competition_v3.txt 的 11 项未出现 FAIL 为结构性记录（v3 已被 v4 取代，不在验收清单内）。
- B3 PPT 分工对调：PASS（4 处替换）。slide19 原始 XML 复核：产品经理 0、头脑风暴 0、灵感与质检 0，技术质检 4、灵感与叙事 1；原文件备份为 .pptx.bak；PowerPoint 打开确认待用户肉眼验证。
- B4 高音数字拆解：PASS。实测新增 31 条正例全部携带高音标签（X=31），既有正例补标 9 条（Y=9），X+Y=40；v4 表格已改写并附计算口径。
- B5 v4 提交物清单：PASS。Demo 压缩包勾选并注明内容。
- C1 max_len 配置化：PASS。deployment/app.py 三处 max_length 均读 CFG["max_len"]。
- C2 部署指南 CPU 说明：PASS。常见问题节已追加 extra-index-url 说明。
- C3 Demo.zip 剔除开发脚本：PASS。11 个开发期脚本已排除。

## 重建产物实测值

- 更新世界的锋芒_SoundInsight_Demo.zip：91,179 字节，41 个文件，无权重、无开发脚本，download_models.py 与运行复现脚本全部在位。
- 更新世界的锋芒_SoundInsight_复赛作品.zip：90,039 字节，2 个文件（Demo.zip + README_SUBMISSION.txt），待用户放入 PDF 与视频。

## 遗留用户事项（DSH 不可代做）

1. git push origin main
2. human_review_conf30.csv 人工审核（8 条）
3. ModelScope 账号三步 + 上传权重 + 创建创空间
4. 演示视频录制（按 video_script.md）
5. 真实用户反馈收集（feedback_template.md）
6. competition_v4.md 团队信息填写
7. PPT 精简（20 页 → 8-12 页）并用 PowerPoint 打开确认 B3 修改未损坏文件
8. 最终 PDF 导出并放入复赛作品 zip

## D6-D8 遗憾消除执行记录（Batch A-G）

- Batch A（A1 excel 报告 / A2 参考文献 / A3 Wilson CI / A4 中置信移除 1288→1280）：全部落地，commit 29033d7、437878b、215ab41、6204530。
- Batch B（LLM 对照实验）：1000 条固定子集实测，零样本 F1 0.940 / 5-shot 0.873 / 复核 0.846 vs 小模型 0.826；tokens 249,703；成本估算 ~$0.1/3000 判定；单批 40 条 2.5s 实测。产出 llm_baseline.md + llm_eval_metrics.py + 原始判定 jsonl；Q3/Q5/Q10 改写为实测口径。commit 3868759。
- Batch C（C1 长度分桶 / C2 边界探针 / C3 校准 / C4 错误分类学）：产出 4 份报告 + calibration_curve.png + val_preds_dump.csv（TP=178/FP=91/FN=73 重算）。关键如实结论：ECE 0.0122 但决策区间严重过度自信；FP 54.9% 为"其他问题"、FN 58.9% 为委婉+双面；LLM 判定标注噪声 9.8%（CI 6.1%-15.3%，未人工终审）；DSH 抽查 30 条与 LLM 类别一致 23/30。v4 九章局限与展望扩充。commit 694f6ea。
- Batch D（时间戳恢复 + 趋势 + 年份分桶）：electronics_expanded.csv 10 万条时间戳 100% 恢复；trend_over_time.png；19,996/20,000 覆盖；2022 桶 F1 0.80、2014-2022 无衰减。此前已 commit。
- Batch E（E1 api_server.py + predict_core.py / E2 install.bat / E3 吞吐实测 GPU 1.763s、CPU 28.443s per 1000 条 / E4 MODEL_CARD.md / E5 --lang en / E6 成本对照行 / E7 非英文显式拒绝）：全部实测通过（curl UTF-8 验证、混合语言 CSV 验证、excel 回归 7,280 字节不变）。
- Batch F（数据许可与 LLM-API 披露写入 README/v4 5.4；docs/drift_plan.md）：完成。标注阶段 ~1502 候选 + 三星补漏经 deepseek-chat API 复核已披露；产品推理零外发。
- Batch G（审计扩展 120 项全 PASS / Demo.zip 50 文件重建 / PPT"2 分钟 99.6%"改实测口径 / QWEN_HANDOFF 与 PROJECT_BRIEF 更新 / 3 次 commit）：完成。git push 因网络（github.com 连接重置）未能完成，用户按下方命令执行即可。

## 诚信核查遗留（如实上报，待用户决策）

1. competition_v3.txt / competition_v4.md 5.2 节写"qwen3.7-plus 用于 LLM 复核"，但 RLCA 实际复核模型是 deepseek-chat（llm_baseline.md 有实测账单口径）。二选一：改为 deepseek-chat，或提供 qwen 复核重跑证据。
2. error_taxonomy.md 的标注噪声率 9.8% 为 AI 判定，人工终审未做。
3. PPT 页数 20 超 8-12 页要求（用户精简）；Speed 表述已由 DSH 修正完毕。

## 重建产物实测值（最新）

- 更新世界的锋芒_SoundInsight_Demo.zip：107,294 字节，50 个文件（含 api_server.py、predict_core.py、install.bat、MODEL_CARD.md；无权重、无开发脚本）。
- 更新世界的锋芒_SoundInsight_复赛作品.zip：105,784 字节，2 个文件（骨架，待用户放入 PDF 与视频）。
