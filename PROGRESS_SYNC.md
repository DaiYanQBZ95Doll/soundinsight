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
5. 用户验证：本轮不做真实用户反馈收集（已从清单移除；v4 局限第 7 条已注明"未开展用户验证"）。
6. competition_v4.md 团队信息填写
7. PPT：用户决定保留 20 页不精简（与 8-12 页要求存在偏差，已知偏差记录）；分工表述与耗时口径修正已生效
8. 最终 PDF 导出并放入复赛作品 zip

## D6-D8 遗憾消除执行记录（Batch A-G）

- Batch A（A1 excel 报告 / A2 参考文献 / A3 Wilson CI / A4 中置信移除 1288→1280）：全部落地，commit 29033d7、437878b、215ab41、6204530。
- Batch B（LLM 对照实验）：1000 条固定子集实测，零样本 F1 0.940 / 5-shot 0.873 / 复核 0.846 vs 小模型 0.826；tokens 249,703；成本估算 ~$0.1/3000 判定；单批 40 条 2.5s 实测。产出 llm_baseline.md + llm_eval_metrics.py + 原始判定 jsonl；Q3/Q5/Q10 改写为实测口径。commit 3868759。
- Batch C（C1 长度分桶 / C2 边界探针 / C3 校准 / C4 错误分类学）：产出 4 份报告 + calibration_curve.png + val_preds_dump.csv（TP=178/FP=91/FN=73 重算）。关键如实结论：ECE 0.0122 但决策区间严重过度自信；FP 54.9% 为"其他问题"、FN 58.9% 为委婉+双面；LLM 判定标注噪声 9.8%（CI 6.1%-15.3%，未人工终审）；DSH 抽查 30 条与 LLM 类别一致 23/30。v4 九章局限与展望扩充。commit 694f6ea。
- Batch D（时间戳恢复 + 趋势 + 年份分桶）：electronics_expanded.csv 10 万条时间戳 100% 恢复；trend_over_time.png；19,996/20,000 覆盖；2022 桶 F1 0.80、2014-2022 无衰减。此前已 commit。
- Batch E（E1 api_server.py + predict_core.py / E2 install.bat / E3 吞吐实测 GPU 1.763s、CPU 28.443s per 1000 条 / E4 MODEL_CARD.md / E5 --lang en / E6 成本对照行 / E7 非英文显式拒绝）：全部实测通过（curl UTF-8 验证、混合语言 CSV 验证、excel 回归 7,280 字节不变）。
- Batch F（数据许可与 LLM-API 披露写入 README/v4 5.4；docs/drift_plan.md）：完成。标注阶段 ~1502 候选 + 三星补漏经 deepseek-chat API 复核已披露；产品推理零外发。
- Batch G（审计扩展 120 项全 PASS / Demo.zip 50 文件重建 / PPT"2 分钟 99.6%"改实测口径 / QWEN_HANDOFF 与 PROJECT_BRIEF 更新 / 3 次 commit）：完成。git push 因网络（github.com 连接重置）未能完成，用户按下方命令执行即可。

## 诚信核查与 P0 修复记录（技术质检方审计后，如实执行）

- P0-1（§5.2 模型调用表述）：已按路线 (a) 落地——v3/v4 5.2 改为 deepseek-chat / DeepSeek 官方 API，阿里云百炼栏如实写"未使用"；路线 (b)（qwen3.7-plus 重跑对照）仍开放，需用户提供 Token Plan Key 并拍板。
- P0-2（llm_baseline 口径声明）：已修正——子集 = val_v2 正例全集 + 749 负例采样（seed 42，小模型未见，无训练记忆效应）；补充循环性声明（同源标签自我一致性红利 + 公开语料预训练记忆无法排除），结论 1/5 相应重写；Q3/Q5/Q10 同步加注口径警示。
- P0-3（两套混淆矩阵调和）：results_summary.md 已加 GPU 重跑调和行（TP=178/FN=73，F1 0.685，±0.002）；error_taxonomy.md 与 v4 7.2 加交叉引用；check_doc_numbers.py 新增 results_summary 组与废弃 claim 违禁项。
- P0-4（长度分桶重做）：按 tokenizer 重算——≤64 token F1 0.708（n=12,471）/ 65-128 token 0.749（n=3,801）/ >128 token 0.565（n=3,728，截断桶，召回 54.4%）；旧字符口径的覆盖性缺陷（11888 条"长评"中仅 31.4% 真正 >128 token）已如实记录；v4 9.1 与 drift_plan §4 同步更新。
- P1-1（概率展示一致性）：Demo 单条/批量/边界案例三处输出加"概率未经校准，仅供排序参考"提示；Agent 中英文报告附注同步；capture_log.txt 与 exp06/training_output.txt 为历史日志产物（生成于加注前），不再编辑历史日志。
- P1-2（标注噪声人工终审）：**已完成（2026-09-05，用户）**。16 条候选 15/16 确认（93.8%，CI 71.7%-98.9%）→ 标注噪声率修正为 9.1%（CI 5.6%-14.5%），FP 侧 12.1%、FN 侧 5.5%；id69 人工确认为模型误报（标注正确）；id48/id93 两条边界已记录；判定写入 human_review_noise16.csv，error_taxonomy/v4/MODEL_CARD 同步更新。
- P2-1（数据集考古汇总）：docs/dataset_audit.md 已产出（来源/字段清单/行数/时间范围/数据质量问题）；year_split_eval.py 重跑，输出原文存档 docs/year_split_output.txt（2022 桶 F1@0.5=0.8049，覆盖 19,996/20,000，与 Q6 一致）。
- P2-2（git push）：**已完成（2026-09-05，用户执行）**——2c07717..a560734 推送成功，全部本地 commit 已上 GitHub。
- 在线 Demo（ModelScope 创空间）：**部署成功、deploy_check 通过、已由用户发布（2026-09-05）**。地址 https://modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight（直链 https://daiyanqbz95doll-soundinsight.ms.show）。验收：页面 200；gradio_api/info 暴露 single_predict+batch_analyze；单条推理 2/2（负面→98.9%+杂音、正面→正常，均带校准提示）；批量上传 100 条 15.1 秒（12 差评、五类分布与本地一致）。修复过程三次：torch/torchvision ABI 硬钉冲突、平台敏感词扫描自动回滚（"内网"措辞）、下载 URL 误拼绝对路径致 404。URL 已回填 README 与 v4。
- P0-1 路线 (b)（qwen3.7-plus 重跑对照）：**已完成（2026-09-05）**。Token Plan 专属基地址（token-plan.cn-beijing.maas.aliyuncs.com）+ qwen3.7-plus 三设置：零样本 F1 0.9149 / 5-shot 0.8937 / 复核 0.8661（tokens 合计 490,747，费用走套餐额度）。v3/v4 5.2 表已改为两模型真实调用（qwen3.7-plus 百炼 Token Plan + deepseek-chat 官方 API）；llm_baseline.md 新增 2b 节与结论 6（跨 LLM 稳健性，qwen 无同源红利）。key 未落盘、未进 git，建议用户轮换。

- **D14 产品改进（提交前）**：批量分析页原先只输出摘要，与命令行 Agent 的六节报告不一致（用户指出 Demo 呈现过薄）。已抽出共享模块 `report_builder.py`（六节报告 + 优先级 + 结论判定 + 成本对照 + 中置信提示），三方统一：`soundinsight_agent.py`、`demo_sound_v2.py`、`deployment/app.py`；语种判定统一到 `text_utils.py`（`predict_core` 仅再导出，避免两份实现）。典型案例新增**五类归因概率**，报告第五节新增**中置信条数提示**（v4 §9.2 对应条目已标注"本轮已实现"）。本地 Demo 与 Agent（zh/en/excel）回归通过；创空间已推送 `eb01fb2`，用户于 9/14 触发重新部署 → 新镜像 `363008-453f56d8-2026-09-14-17-55-37`，**线上实测通过**：批量页返回完整六节报告（1,622 字符；含归因概率、三条紧急建议、"中置信提示 4 条"、成本对照、校准声明），单条推理 2/2，100 条 20.1 秒。

## 重建产物实测值（最新，2026-09-14 封包后）

- **包内说明纠错（用户指出）**：`README_SUBMISSION.txt` 原写有"请手动放入最终 PDF / 演示视频"，与包内实际已含这两项矛盾 → 按实际内容重写（五项清单 + 在线 Demo / 双仓库链接）；`pack_final.py` 现每次打包都从 `build_submission.py` 重写它，说明不会再漂移。同时清掉 Demo.zip 中误入的 12 个开发脚本（63 → 51 文件）。
- **校验清单**：`pack_final.py` 在根目录与包内各写一份 `hashes.txt`（四项提交物的完整 SHA256）。外层 zip 与 `其他材料.zip`（内含文档）属"自引用容器"，哈希每次重打必变，因此 D13 §三 改为按内容类/容器类分别登记。
- 更新世界的锋芒_SoundInsight_Demo.zip：109,550 字节 `da1f0f514d50ecf1`，51 个文件（含 api_server.py、predict_core.py、report_builder.py、text_utils.py、install.bat、MODEL_CARD.md；无权重、无开发脚本）。
- 更新世界的锋芒_SoundInsight_其他材料.zip：467,441 字节，46 个文件 + README_其他材料.txt（容器类，哈希见包内 `hashes.txt`）。
- 更新世界的锋芒_SoundInsight_复赛作品.zip：44,432,904 字节，6 个条目（Demo.zip + 其他材料.zip + README_SUBMISSION.txt + 主文档 PDF + 演示视频.mp4 + hashes.txt）——**已含全部四项，可直接提交**；完整 SHA256 见根目录 `hashes.txt`。
- 数字审计：`python check_doc_numbers.py` → **0 FAIL / 150 PASS**（含模板格式对照 8 项 + 新增"口径配对检查"7 项）。
- **D14 口径混用修正（用户指出 §7.2）**：v4 §7.2 原写"F1=0.6871（阈值 0.97），召回率 89.6%，精确率 47.9%"，把两个阈值的指标并排（89.6%/47.9% 来自阈值 0.5，0.6871 来自 0.9744）→ 改为按阈值分列的双档表（0.9744：P 66.3%/R 71.3%/F1 0.6871；0.5：P 47.9%/R 89.6%/F1 0.6241）+ 成对阅读说明；§3.3 价值表、§7.6 消融表同样标注阈值档位；v3、README、QWEN_HANDOFF、PROJECT_BRIEF_QWEN、PPT（slide10/12/15）同步修正。审计新增"口径配对检查（阈值并排）"防复发：一行同时出现调优档 F1 与阈值 0.5 档 P/R 时必须显式标出两个阈值，否则 FAIL。PPT 用 `fix_ppt_threshold.py` 整段精确映射改 XML（先备份 `.pptx.bak`），页数仍 20 页。
- 同步状态：GitCode 已推送（本轮 commit 待推）；GitHub 因本机代理未运行（7890 端口无监听）连接失败，待网络可用后执行 `git push origin main`。
- **公开仓库声明与卫生扫描（用户要求）**：仓库含初赛与过程材料 → 新增 `docs/legacy_materials_notice.md`（权威来源 / 历史材料清单 / 已废弃 claim 一览 / 隐私与凭据 / 生成顺序），README 顶部加"版本与口径指引"，`AI_HANDOFF/README.md` 挂入口；新增 `scan_repo_hygiene.py`（密钥含 git 历史、隐私、废弃 claim 分类、manifest 记录值一致性）。实扫：**密钥 0、本机路径 0**；隐私 13 处 = 模板要求的竞赛联系信息（v3/v4/D13/项目全记录）+ 3 条误报（sha256 与浮点数数字串）；废弃 claim 全部属历史材料或护栏脚本，当前文档需确认 **0** 处。
- 生成顺序（改了文档必须按此顺序）：`check_doc_numbers.py` → `scan_repo_hygiene.py` → `md_to_pdf/docx` → `build_submission.py` → `pack_final.py` → **最后** `make_ai_handoff.py`（否则 manifest 记录的大小/哈希过期，扫描第四节会直接报出来）。
- **复赛提交完成（2026-09-14 21:44:28）**：已提交 `更新世界的锋芒_SoundInsight_复赛作品.zip`（44,446,308 B / `e6cae286515ef1d2`，包内 PDF 为口径修正版 215,103 B）；平台侧文件名 `1789393462453_MGG2SmTdYL.zip`，状态**待评测**，剩余提交次数 1 次，格式限制 zip ≤ 10000M。页面不显示大小/哈希，归属判断依据：最终封包 21:23 < 提交 21:44，且磁盘上该 zip 唯一。
- **提交后冻结**：不再重打提交包（重打会改变容器哈希、使仓库版本与已提交版本不一致）；后续文档更新只改仓库与 `hashes.txt`。若确需重打，必须在文档中注明"仓库版本 ≠ 已提交版本"。
- 注意：`更新世界的锋芒_SoundInsight_复赛作品.zip` 在 Bandizip 打开期间被独占，`pack_final.py` 无法替换（已加等待重试）。**上传天池前必须确认 zip 是修正后的版本**（包内 PDF 应为 215,103 B / `7a92e5cc`）。
- **决赛入围（2026-09-14 官方公示，用户告知 + 页面已核验）**：148 → **50 支战队**，本团队序号 **15**；官方公示页 <https://builderx.csdn.net/activity-site/ceshi1/bansaimingdan> 正文含"更新世界的锋芒 / SoundInsight"。新时间线：**决赛作品提交截止 10 月 8 日** → 线上评审出 **6 支** → 线下路演，需准备 **10–15 分钟 PPT 分享**。据此修正项目内此前"路演 23 日"的假设。决赛待办见 `docs/finals_stage.md`。决赛属新一轮提交，复赛包仍按红线 9 冻结。
- **决赛模板已到手（2026-09-24）**：`hackathon-决赛入围定稿作品提交模板-天池版.docx`（官方，36,689 B，已入仓库）。与复赛的**实质差别**：① 主文档＝**填写后的该模板**（.docx/.pdf），不是自拟的 v4 文档 → v4 内容需按模板九节重排；② zip 与主文档命名改为 `团队名_方案名称_决赛入围定稿作品`；③ 模板 5.2 要求填"阿里云百炼模型"表，本项目产品推理全本地、未用百炼，须如实填"未使用"；④ 视频建议 3–5 分钟（现有 3:23 可复用）；⑤ 明确"代码仓库不强制公开源码，可私有仓库 + 授权评审可见，或用 Demo + 视频验证"。逐条要求、差别与交付物映射见 `docs/finals_stage.md` §三/§五；`extract_template.py` 已支持传入模板路径，便于后续"填写稿 vs 模板"格式对照。
