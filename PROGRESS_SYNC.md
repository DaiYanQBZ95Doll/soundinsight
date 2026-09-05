# SoundInsight D5 执行进度同步

## 批次完成状态

### 批次 1：在线部署包 — PASS（产出齐备，部署动作待用户）

- deployment/ 目录四件套：app.py（路径全相对化、config.json 驱动、启动自动下载权重）、requirements.txt（固定版本）、README_Space.md、config.json（model_repo_id 留空待填）
- upload_models.py：权重上传脚本，顶部注明用户三步网页操作
- DEPLOY_GUIDE.md：四步部署指南，用户操作总量约 30 分钟
- 待用户：ModelScope 注册、建仓、取 token、执行上传命令、创建创空间
- 验收（deploy_check.md）：待公网地址就绪后执行

### 批次 2：一致性审计 — PASS（两项用户侧 FAIL 已记录）

- number_audit.md：三份文档逐项核对，违禁项（1297、正文 83.7）全部 PASS
- ppt_text_dump.md：PPT 20 页全部提取；数字全部 PASS；页数 20 超出 8-12 要求 → 用户侧 FAIL
- competition_v3.txt 缺统计验证数字（结构性问题，由 v4 补齐）
- README 旧数字（0.37）→ 批次 5 已更新为当前口径
- results_summary.md 混淆矩阵已加 thr=0.5 与 thr=0.9744 双口径标注，生成器同步防回退

### 批次 3：competition_v4.md — PASS

十一章全文完成：核心发现三连块、指标口径防御段（原文照录）、统计验证（学习曲线 bootstrap 口径注、PR、t 检验、5 折逐折）、消融四行业务化结论、归因定位说明（原文照录）、局限与展望、在线 Demo 占位符、1257/1288 口径脚注。数字审计 17 项全 PASS，无违禁项。

### 批次 4：提交物打包与视频素材 — PASS

- 更新世界的锋芒_SoundInsight_Demo.zip：50 个文件，0.2MB，无权重，含 download_models.py（下载校验一体）
- 更新世界的锋芒_SoundInsight_复赛作品.zip：骨架（Demo.zip + README_SUBMISSION.txt），待用户放入 PDF 与视频
- sample_reviews_100.csv：100 条（12 音质差评 / 62 非音质 / 24 边界 / 2 多语言）
- video_script.md：八镜头 130 秒分镜 + 口播稿 + 录制检查单
- feedback_template.md：五节全留空，禁止预填声明

### 批次 5：收尾同步 — PASS

- README.md：四步快速开始（装依赖→下模型→启 Demo→Agent）、模型性能章节更新为当前口径（0.6871/0.6234/0.7191 等）、在线 Demo 占位符、1257/1288 口径脚注
- QWEN_HANDOFF.md：补齐精确率 47.9% 与 p 值、学习曲线最终值、D5 状态与待办
- 全部变更已提交 git

## 遗留用户事项（DSH 不可代做）

1. git push origin main
2. human_review_conf30.csv 人工审核（8 条）
3. ModelScope 账号三步 + 上传权重 + 创建创空间
4. 演示视频录制（按 video_script.md）
5. 真实用户反馈收集（feedback_template.md）
6. competition_v4.md 团队信息填写
7. PPT 精简（20 页 → 8-12 页）
8. 最终 PDF 导出并放入复赛作品 zip
