# 数据集字段清单与考古汇总（dataset_audit.md）

> 目的：D6-D8 任务清单要求的数据集字段清单文档，把散在 restore_timestamps.py / year_split_eval.py / Q6 的考古证据汇总到一处。所有数字为本文件生成日实测。

## 1. 来源与获取方式

- 数据源：McAuley Lab Amazon Reviews 2023（Hou et al., arXiv:2203.16852），AmazonElectronics 类目，官方下载站 https://amazon-reviews-2023.github.io/（本机经 mcauleylab.ucsd.edu 获取）。
- 获取方式：HTTP Range 分段拉取 `electronics_prefix.bin`（128MB gzip 前缀），解析出 10 万条原始评论记录（fetch_electronics.py / extend_data.py）。
- 许可：版权归原发布方与原始评论作者；本项目仅研究/竞赛用途（披露见 README 与 competition_v4.md §5.4）。

## 2. 各文件字段清单（实测表头）

| 文件 | 行数 | 列 | 关键统计 |
|---|---|---|---|
| electronics_expanded.csv | 100,000 | text, rating, timestamp | timestamp 非空 100,000/100,000；时间范围 2000-10-07 → 2023-03-18（UTC，毫秒 epoch） |
| labeled_expanded.csv | 100,000 | text, rating, sound_related, sound_negative, issue_bass, issue_clarity, issue_noise, issue_volume, issue_treble | 规则初筛正例 1,502 |
| labeled_llm.csv | 100,000 | 上表 9 列 + 后缀 _llm 的 6 列（sound_negative_llm 及五类） | LLM 复核后正例 1,280（当前工作集；冻结实验口径 1,257，见 results_summary.md） |
| val_v2.csv | 20,000 | text, sound_negative | 正例 251；固定验证集，红线冻结 |
| sample_reviews_100.csv | 100 | text, rating, 期望标签, 类别 | 样例集（rating 已回填） |
| train_quick.csv | （小样本） | — | RoBERTa 快速验证用训练集 |

- 说明：仓库内**不存在** `train_v2.csv` 文件；最终模型的训练集由冻结训练脚本在运行时按 seed=42 从标注池分层划分（约 1006 正例 + 10060 负例，见 QWEN_HANDOFF）。若需复现，训练脚本 + labeled_llm 系列备份文件即为原料。

## 3. 字段语义

- `timestamp`：原始记录自带（毫秒 epoch，UTC），restore_timestamps.py 重建后与文本逐条精确匹配（100k/100k 行全部恢复，非抽样）。
- `rating`：1-5 星，全部非空。
- 标签列：0/1。`sound_related`=是否提及音质；`sound_negative`=是否音质负面；issue_* = 五类问题（低音/清晰度/杂音/音量/高音）。`_llm` 后缀为 LLM 复核后版本。
- 多标签允许重叠（一条评论可同时命中多类）。

## 4. 已知数据质量问题（如实）

1. 部分评论文本含 HTML 转义残留（`&#34;`）、`<br />` 标签与 `[[VIDEOID:...]]` 占位符——推断与分词时被当作普通字符，未做清洗（影响程度未单独量化）。
2. 非英文评论占比：val_v2 中 27/20,000（0.14%，实测），产品层已做显式拒绝（predict_core.is_unsupported）。
3. 评论横跨 22 年（2000-2023），类目为全品 AmazonElectronics（含镜头、Kindle、笔记本外壳等非音频产品）——这是误报"其他问题"类（54.9%）的根因（error_taxonomy.md）。

## 5. 时序考古证据索引

- 时间戳恢复与月度趋势：trend_over_time.py → trend_over_time.png（2021-2023 月度音质差评率）。
- 年份分桶验证：year_split_eval.py，覆盖 19,996/20,000 条 val_v2；脚本输出原文存档于 docs/year_split_output.txt。
- Q6 引用数字：2022 桶 F1@0.5=0.80（2515 条中 42 条正例）；2014-2022 各年桶 F1 0.44-0.88 波动，未发现单调衰减；2023 桶仅 5 正例，噪声大。
