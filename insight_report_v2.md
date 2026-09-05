# SoundInsight 音质洞察报告

## 一、总体概况
分析对象：sample_reviews_100.csv
分析时间：2026-09-05 13:57
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
2. （99.0%）I'm not that impressed with these. The sound is too muted and they get staticy at times. The range for them to work is o
3. （99.0%）The audio quality on this webcam is horrible. Audio is very distorted and is full of noise and intermittent breaks. Vide
4. （98.9%）I bought this Nexus 7 32G at the end of January 2013 via online store and have had it since February 2013.  Within about
5. （98.8%）these work as advertised.  they take crappy sounding, bassless ipod stock earbuds and make them sound at 100% better (ma

## 四、行动建议
- 紧急（低音）：建议检查 生产/质检 环节，预期降低该类差评率。
- 紧急（杂音）：建议检查 生产/质检 环节，预期降低该类差评率。
- 紧急（音量）：建议检查 客服/详情页 环节，预期降低该类差评率。

## 五、验证指标
建议复评周期：2-4 周后重新运行批量分析，追踪同口径差评率变化。

## 六、附注
本报告由 SoundInsight 自动生成，判定基于 DistilBERT 微调模型（验证集 F1 0.687，阈值 0.97）与五类多标签归因模型，边界案例存在一定误差，关键决策建议结合人工抽查。
- 成本对照：本地推理 0 API 费用；同等 100 条若调用 LLM（deepseek-chat，实测约 $0.03/1000 条，见 llm_baseline.md）约 $0.00。