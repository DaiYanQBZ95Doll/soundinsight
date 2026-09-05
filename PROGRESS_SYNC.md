# SoundInsight D5 缺陷修复执行记录

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
