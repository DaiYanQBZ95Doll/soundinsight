# 历史材料与版本指引（公开仓库声明）

本仓库公开（GitHub + GitCode），且**保留了初赛、过程日志与修复脚本等历史文件**。本文件回答两个问题：**哪个算数**、**哪些只是过程留痕**。凡引用本项目数字，请以本文第一节的权威来源为准；第二节列出的文件反映的是写作当时的状态，**不作为当前口径**。

维护方式：改了文档后按第五节顺序重跑脚本；`python scan_repo_hygiene.py` 会自动核对本文第三节的废弃 claim 是否已从当前文档清除。

---

## 一、权威来源（唯一口径）

| 内容 | 权威文件 | 说明 |
|---|---|---|
| 全部指标数字 | `results_summary.md` | 训练/评估原始输出汇总；其他文档一律引用它 |
| 口径与局限说明 | `AI_HANDOFF/03_metrics_and_caveats.md` | 三套口径定义、冻结数字清单、已知局限 |
| 对外主文档 | `competition_v4.md` | 提交用 PDF / Word 由 `md_to_pdf.py` / `md_to_docx.py` 从它生成；`competition_v3.txt` 为同源精简版 |
| 模型与验证资产（冻结） | `sound_model/`、`multi_label_model/`、`val_v2.csv`、`train_final.py` 等训练脚本 | 不得重训、不得修改、不得混入训练数据 |
| 提交物校验值 | 根目录 `hashes.txt`（外层容器）＋ 提交包内 `hashes.txt`（四项提交物内容哈希） | 容器哈希随重打变化，以文件为准 |
| 卫生自检 | `scan_repo_hygiene.py` → `docs/repo_hygiene_scan.md` | 密钥 / 隐私 / 废弃 claim / 生成物一致性 |

**三套口径不可混用**（详见 `AI_HANDOFF/03_metrics_and_caveats.md`）：

1. **冻结口径**：固定验证集 `val_v2.csv`（20,000 条 / 251 正例），阈值 0.9744（对外 0.97）；
2. **1,000 条子集口径**：小模型与 LLM 对照实验（含同源标签红利声明）；
3. **工程口径**：吞吐（GPU 1.763 s / CPU 28.443 s per 1000 条）、校准（ECE 0.0122）、长度分桶、错误分类学。

同一模型的**精确率/召回率还分阈值档**，必须成对阅读：

| 阈值 | 精确率 | 召回率 | F1 |
|---|---|---|---|
| 0.9744（F1 最优，对外 0.97） | 66.3% | 71.3% | **0.6871** |
| 0.5（默认，高召回档） | 47.9% | 89.6% | 0.6241 |

---

## 二、历史材料（保留当时状态，不作为当前口径）

| 类别 | 文件 | 为什么保留 |
|---|---|---|
| 初赛材料 | `competition_v2.md`、`competition_v2.txt`、`SoundInsight_创意方案/` | 展示从初赛 F1 0.37 到复赛的完整改进轨迹 |
| 过程日志 | `docs/work_summary_d7.md`、`docs/process_review_d10.md`、`PROGRESS_SYNC.md`、`docs/project_full_record.md` | 记录每一步做了什么、修过什么问题（含错误与回滚） |
| 交接文档 | `QWEN_HANDOFF.md`、`PROJECT_BRIEF_QWEN.md`、`AI_HANDOFF/*` | 给协作者/AI 的上下文，部分内容写于数字修正之前 |
| 历史产物 | `insight_report*.md`、`batch_report.md`、`training_output.txt`、`summary_log.txt`、`ppt_text_dump.md` | 某一轮运行的真实输出快照（PPT 文本转储随 PPT 更新） |
| 修复脚本 | `ppt_speed_fix.py`、`fix_ppt_threshold.py`、`retime_srt.py`、`rebuild_video_timing.py` | 脚本正文包含"旧表述 → 新表述"的映射表，**出现旧字样是工具输入，不是结论** |
| 早期数据版本 | `labeled_data_final.csv`、`labeled_llm_before_*.csv` | 标注口径演进留痕，可复现 |

---

## 三、已废弃 claim 一览（历史文件中出现属正常；当前文档不得再出现）

| 旧表述 | 现口径 | 处理 |
|---|---|---|
| "1000 条 2 分钟"、"效率提升 99.6%" | GPU **1.763 s** / CPU **28.443 s** per 1000 条（实测），提升 >99.9% | 已改为实测值，审计列为违禁项 |
| "GPT-4 $0.01/条" | 未实测，已删除；成本对照只用"人工 240 元/1000 条 vs 本地 0 元" | 已删除并列入违禁项 |
| "白皮书"、"98%" | 无出处，已删除 | 同上 |
| "qwen3.7-plus 用于标注复核" | 标注复核实际用 **deepseek-chat**；qwen3.7-plus 仅作跨 LLM 对照，**未参与标注** | 已改正，审计新增违禁项 |
| 正例数 "1297" | 口径演进：**1257**（冻结多标签）→ **1288**（高音补捞）→ **1280**（中置信剔除） | 出现 1288/1280 必须带口径说明 |
| "教师一致性 83.7%" | 仅说明蒸馏可行性，**不得作为性能证据**，正文不得出现 | PPT 与主文档审计均有护栏 |
| 长度分桶按"字符数" | 改按 **tokenizer token**：≤64 = 0.708 / 65-128 = 0.749 / >128（截断桶）= 0.565 | 旧字符口径报告已取代 |
| "F1=0.6871（阈值0.97），召回率 89.6%，精确率 47.9%" | 两档并排属误读：89.6%/47.9% 来自阈值 **0.5** | 已改为双档分列表；审计新增"口径配对检查" |
| 容器体积类（`44,432,904`、`208,471`、`107,294` 等） | 随每次重打变化 | 以 `hashes.txt` 与提交页为准 |
| `feedback_template.md`、"用户反馈/试用证言" | 未开展用户验证，如实披露于 `competition_v4.md` §9.1 第 7 条 | 文件已删除，引用已清理 |

---

## 四、隐私与凭据（公开仓库实扫结果）

扫描范围：`git ls-files` 的 269 个跟踪文件逐行扫 + git 历史文本文件；工具 `scan_repo_hygiene.py`，报告 `docs/repo_hygiene_scan.md`。

- **密钥 / 令牌 / 口令：0 命中**（跟踪文件与历史提交均为 0）。`upload_models.py` 中的 `https://oauth2:{args.token}@…` 是命令行参数占位符，令牌不落盘；ModelScope 与 GitCode 的令牌只在本机命令行使用，未写入任何文件。
- **本机绝对路径（`C:\Users\…`）：0 命中**。
- **竞赛联系信息（有意填写，模板要求）**：`competition_v3.txt` / `competition_v4.md` §一 团队信息表含队长手机号与邮箱；`docs/D13_seal_declaration.md`、`docs/project_full_record.md` 引用同一信息。**公开仓库可见**。如需脱敏：主文档保留邮箱、手机号改为赛事平台可查（会偏离模板"联系电话"要求，建议赛后再处理或改为仅在提交 PDF 中保留）。
- **数据集正文**：来自公开数据集 Amazon Reviews 2023（McAuley Lab），不含个人身份信息；扫描中出现的"手机号/身份证号"命中均为 **sha256 十六进制串与浮点数中的数字连串**，经逐条核对为误报（`AI_HANDOFF/manifest.json` 两条、`learning_curve_results.json` 一条）。

---

## 五、改了文档后的标准顺序

```powershell
cd C:\deepseek-harness-master\soundinsight
python check_doc_numbers.py      # 数字与模板一致性，必须 0 FAIL
python scan_repo_hygiene.py      # 密钥 / 隐私 / 废弃 claim / 生成物一致性
python md_to_pdf.py competition_v4.md "更新世界的锋芒_SoundInsight_复赛作品.pdf"   # 若改了 v4
python md_to_docx.py competition_v4.md "更新世界的锋芒_SoundInsight_复赛作品.docx"
python build_submission.py       # 重建 Demo.zip 与 其他材料.zip（文档变更必须走这步）
python pack_final.py             # 组装 复赛作品.zip + 写 hashes.txt
python make_ai_handoff.py        # 最后跑：刷新 manifest.json（否则其记录的大小/哈希会过期）
```

顺序要点：`make_ai_handoff.py` **必须最后一个跑**——它记录每个文件的大小与哈希，任何后续改动都会让它过期（`scan_repo_hygiene.py` 第四节会直接报出来）。`pack_final.py` 只组装外层 zip，不会重建内层两个包。
