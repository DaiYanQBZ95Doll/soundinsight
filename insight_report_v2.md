# SoundInsight 音质洞察报告

> **样例说明**：本样例由**产品默认模型（v1 冻结权重）**生成，因此报告内指标为 v1 口径（验证集 F1 0.687、阈值 0.9744）；决赛主文档中的 v2 指标（`val_v3_test` 上 F1@调优(0.6) = 0.7220）来自 **v2 候选模型**，两者样本集不同、**不可直比**。模型调用边界见 README「模型调用与边界」段。


## 一、总体概况
分析对象：sample_reviews_100.csv
分析时间：2026-10-01 05:10
评论总数：100 条（其中非英文 0 条已跳过）
有效评论：100 条
音质差评数：12 条（占比 12.00%）
平均评分：3.78
结论一句话：严重，音质差评率显著偏高，建议立即排查

## 二、问题分布
| 问题类别 | 数量 | 占比 | 优先级 |
|---------|------|------|--------|
| 低音 | 5 | 38.5% | 高 |
| 杂音 | 4 | 30.8% | 高 |
| 音量 | 3 | 23.1% | 高 |
| 清晰度 | 1 | 7.7% | 中 |
| 高音 | 0 | 0.0% | 低 |

## 三、典型案例
1. （99.0%）The sound quality was horrible! Extreme static. I was very disappointed. Won't buy again.
   归因概率：杂音 0.93、清晰度 0.16、音量 0.08
2. （99.0%）I'm not that impressed with these. The sound is too muted and they get staticy at times. The range for them to work is o
   归因概率：杂音 0.94、清晰度 0.12、音量 0.11
3. （99.0%）The audio quality on this webcam is horrible. Audio is very distorted and is full of noise and intermittent breaks. Vide
   归因概率：清晰度 0.76、杂音 0.65、音量 0.10
4. （98.9%）I bought this Nexus 7 32G at the end of January 2013 via online store and have had it since February 2013.  Within about
   归因概率：音量 0.85、清晰度 0.20、杂音 0.16
5. （98.8%）these work as advertised.  they take crappy sounding, bassless ipod stock earbuds and make them sound at 100% better (ma
   归因概率：低音 0.94、清晰度 0.25、高音 0.24

## 四、行动建议
- 紧急（低音｜置信档：高）：建议检查 生产/质检 环节，预期降低该类差评率。
- 紧急（杂音｜置信档：高）：建议检查 生产/质检 环节，预期降低该类差评率。
- 紧急（音量｜置信档：高）：建议检查 客服/详情页 环节，预期降低该类差评率。

## 五、验证指标
建议复评周期：2-4 周后重新运行批量分析，追踪同口径差评率变化。
- 中置信提示：有 4 条评论概率落在 0.5-0.9744 区间，当前判为正常但建议人工抽查（疑似负面）。

## 六、置信度档位与建议动作
| 档位 | 概率区间 | 含义 | 建议动作 |
|---|---|---|---|
| 高 | ≥ 0.9744（调优档） | 高置信音质差评 | 直接进入整改/研发评审（12 条） |
| 中 | 0.5 – 0.9744 | 疑似负面，证据不足 | 先做小规模人工抽查（4 条） |
| 低 | < 0.5 | 判为正常 | 仅计入趋势观察，不进入问题分布（84 条） |

## 七、附注
本报告由 SoundInsight 自动生成，判定基于 DistilBERT 微调模型（验证集 F1 0.687，阈值 0.97）与五类多标签归因模型，边界案例存在一定误差，关键决策建议结合人工抽查。
模型输出概率未经校准，仅供排序参考（见 calibration_eval.md）。
- 成本对照：本地推理 0 API 费用；同等 100 条若调用 LLM（deepseek-chat，实测约 $0.03/1000 条，见 llm_baseline.md）约 $0.00。