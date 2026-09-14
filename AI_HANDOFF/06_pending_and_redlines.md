# 06 待办 · 红线 · 协作规则

## 一、未完成事项（截至 D13 封包，如实清单）

| # | 事项 | 状态 | 备注 |
|---|---|---|---|
| 1 | **演示视频文件** | ❌ 待录制 | 脚本 `video_script.md`（200 秒/9 镜头）、无口播拍摄卡 `video_script_silent.md`、字幕 `video_script.srt`、满屏素材 `视频素材/` 均已就绪；导出后命名 `更新世界的锋芒_SoundInsight_演示视频.mp4` 放项目根目录，跑 `python pack_final.py` 自动并包 |
| 2 | 主文档 PDF/Word 重生成（若改过 v4） | 已完成 | 改 `competition_v4.md` 后需跑 `md_to_pdf.py` + `md_to_docx.py` 再 `pack_final.py`（PDF 内含链接表，不重生成会与源文不一致） |
| 2b | **创空间重建（新版批量报告生效）** | ⏳ 等待平台构建 | 已推送 `eb01fb2` 到创空间仓库（远端已确认），但线上实例仍是 `a952359b-2026-09-05-16-28-07` 镜像。需在创空间页面点"重新构建/重新部署"触发，或等平台自动构建；触发后用 `python batch_check.py https://daiyanqbz95doll-soundinsight.ms.show` 验证输出是否为新版六节报告 |
| 3 | GitHub 推送 | 视情况 | GitCode 已最新；GitHub 若落后，`git push origin main`（SSL 报错加 `-c http.sslBackend=openssl`） |
| 4 | 上传天池 | ❌ 待做 | 只传一个 zip：`更新世界的锋芒_SoundInsight_复赛作品.zip` |
| 5 | 真实用户验证 | ❌ **不做** | 已从任务清单移除；`competition_v4.md` §9.1 第 7 条如实披露"未开展用户验证" |
| 6 | GitCode 访问令牌轮换 | 建议 | 该令牌曾在聊天中出现过；提交完成后在 GitCode 设置中删除重建 |
| 7 | PPT 页数 | ⚠️ 已知偏差 | 20 页 > 赛事建议 8-12 页；**用户已决定不精简**，`audit_ppt.py` 仍会标 FAIL（事实记录，不隐藏） |
| 8 | 高音归因 F1=0 | ⚠️ 机制已查清；**用户已选方案 C（标签重定义+重训），目标决赛路演（23 日）前完成，当前未启动** | 零触发：最大概率 0.3332 < 阈值 0.5；逐类阈值 0.20 可恢复 F1 0.5161（实测）。方案与执行清单见 `docs/treble_fix_proposal.md`（A 逐类阈值不改权重 / B 加权重训 / **C 标签重定义+重训，已选**）；C 内部还需在"合并（刺耳并入清晰度→四类）"与"细化（保留五类+重标 206 条）"之间拍板 |
| 9 | 多语言支持 | ⚠️ 未做 | 当前对非英文**显式拒绝**，不静默判负 |
| 10 | 漂移监控上线 | ⚠️ 未上线 | 方案见 `docs/drift_plan.md`，无生产流量可跑 |
| 11 | D4 无独立记录 | ⚠️ 事实 | 仓库无 D4 留档，已如实注明，未补造 |

## 二、红线（任何 AI 助手不得触碰）

1. **模型权重冻结**：`sound_model/`、`multi_label_model/` 不得重训或替换。
2. **验证集冻结**：`val_v2.csv` 不得修改、不得混入训练数据。
3. **训练脚本冻结**：`train_final.py`、`train_multilabel.py`、`distilbert_cv.py`、`ablation_train.py`、`learning_curve.py` 等不得改动。
4. **冻结数字不得改**：见 `03_metrics_and_caveats.md` 第二节清单；权威源为 `results_summary.md`。
5. **权重不入 git**：`.gitignore` 已排除权重目录与基座缓存。
6. **GPU 串行**：8GB 显存，任务排队执行。
7. **不编造**：不得虚构数据、用户证言、未实测的性能或成本数字；不得把合成画面冒充实机演示。
8. **口径分离**：三套口径（冻结 / 1,000 条子集 / 工程）不得互相替代或并排比较（详见 `03_metrics_and_caveats.md`）。

## 三、诚信记录（已处理的历史问题，勿复发）

| 曾出现的问题 | 处理方式 |
|---|---|
| §5.2 写"qwen3.7-plus 用于 RLCA 标注复核"（实际是 deepseek-chat） | 改为两模型真实调用：deepseek-chat（RLCA 复核 + 对照）、qwen3.7-plus（跨 LLM 对照，实测已跑）；审计新增违禁项 `qwen3.7-plus × 标注复核` |
| `llm_baseline.md` 口径声明错误（把 val_v2 子集说成训练池） | 修正为"val_v2 正例全集 + 负例采样（小模型未见）"，并补"同源标签红利 + 预训练记忆无法排除"声明 |
| 两套混淆矩阵并存（179/72 与 178/73）且无说明 | `results_summary.md` 增加调和行；`error_taxonomy.md` 与 v4 §7.2 加交叉引用；审计新增检查 |
| 长度分桶做成"字符数"而非 token（未回答截断问题） | 按 tokenizer 重做：0.708 / 0.749 / 0.565；旧口径缺陷（11,888 条"长评"仅 31.4% 真超 128 token）如实记录 |
| 校准结论与产品行为脱节（文档说不该展示概率，Demo 却在展示） | Demo 单条/批量/边界三处 + Agent 中英文报告全部加"概率未经校准，仅供排序参考" |
| 标注噪声 9.8% 只有 AI 判定 | 16 条候选人工终审 15/16 → 修正为 9.1%（下界估算），判定写入 `human_review_noise16.csv` |
| 白皮书/98%、"2 分钟/99.6%"、"GPT-4 $0.01/条"等无出处或未实测表述 | 全部清理并写入审计违禁项 |
| `feedback_template.md` 为未完成环节 | 已删除文件并清理 5 处引用；改由 v4 §9.1 如实披露"未开展用户验证" |

## 四、协作规则（本项目实际执行过的）

1. **一人 + 四 AI 分工**：队长（最终决策）、DSH（代码/实验/部署）、Kimi（技术质检，一票否决权）、DeepSeek（战略叙事）、Qwen（灵感与叙事）。
2. **技术质检的否决权**：涉及数据泄漏、指标虚高、验证集污染、口径不可比的问题可直接否决；本项目据此修过 P0-2/P0-3/P0-4。
3. **如实报告优先于好看**：不利结果（校准过度自信、qwen 在 5-shot/复核反超 deepseek、噪声率、截断性能下降）全部留在文档里。
4. **禁止诱导**：AI 只报告事实与状态，不替用户做产品/时间决策，不制造紧迫感（见 `AI_INDUCTION_REDLINE.md`）。

## 五、改完文档后的标准动作

```powershell
cd C:\deepseek-harness-master\soundinsight
python check_doc_numbers.py     # 必须 0 FAIL
python md_to_pdf.py competition_v4.md "更新世界的锋芒_SoundInsight_复赛作品.pdf"   # 若改了 v4
python md_to_docx.py competition_v4.md "更新世界的锋芒_SoundInsight_复赛作品.docx"
python make_ai_handoff.py       # 若增删文件，刷新索引
python pack_final.py            # 重新打包提交包
```
