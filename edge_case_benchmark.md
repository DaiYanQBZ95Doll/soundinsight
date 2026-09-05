# 边界案例基准报告（edge_case_benchmark.md）

口径：样本取自 `edge_cases.md` 收录的真实评论（n=12，定向探针，非大规模基准）；期望标签按该文档判据由 DSH 标注并在此如实披露。多语言类标记为"未支持"，不参与命中率统计。阈值 0.9744。

| 类别 | 评论 | 期望 | 模型判定 | 概率 |
|---|---|---|---|---|
| 委婉表达类 | Was expecting a deeper bass given the price poin… | 负面 | 正常 ✗ | 0.9536 |
| 委婉表达类 | The sound is fine for the price, nothing special… | 负面 | 正常 ✗ | 0.5320 |
| 中性比较类 | Not as loud as my previous pair, but the clarity… | 正常 | 正常 ✓ | 0.0008 |
| 中性比较类 | Bass is weaker than brand X, treble is smoother … | 正常 | 负面 ✗ | 0.9877 |
| 关键词误命中类 | It sounds like a great deal, and shipping was fa… | 正常 | 正常 ✓ | 0.0005 |
| 关键词误命中类 | The packaging keeps the unit safe from static da… | 正常 | 正常 ✓ | 0.0002 |
| 评分语义冲突类 | Great product, though the bass is a little muddy… | 负面 | 负面 ✓ | 0.9806 |
| 评分语义冲突类 | Arrived broken due to poor packaging, refund was… | 正常 | 正常 ✓ | 0.0002 |
| 多语言类 | La calidad del sonido es regular, esperaba más g… | 未支持 | 正常 — | 0.0002 |
| 多语言类 | 音质一般般，低音不够，有点失望。… | 未支持 | 正常 — | 0.0003 |
| 极短评论类 | Meh.… | 正常 | 正常 ✓ | 0.0001 |
| 极短评论类 | Sound broke after a week.… | 负面 | 负面 ✓ | 0.9895 |

| 类别 | 命中 | 样本数 | 命中率 |
|---|---|---|---|
| 委婉表达类 | 0 | 2 | 0% |
| 中性比较类 | 1 | 2 | 50% |
| 关键词误命中类 | 2 | 2 | 100% |
| 评分语义冲突类 | 2 | 2 | 100% |
| 极短评论类 | 2 | 2 | 100% |
| 合计（除多语言） | 7 | 10 | 70% |

## val_v2 层面的定量补充

- 非英文/含非英文字符评论占比：27/20000 （0.14%），其中被模型判为音质负面 0 条。

如实结论：定向探针 n=12 仅能暴露已知边界类别的行为模式，不能替代大规模评测；其价值是验证边界类别是否如预期失败/通过，而非给出置信的性能数字。
- 委婉表达类 0/2：确认是该类别的已知漏检来源（与 C4 错误分类学一致）。
- 中性比较类 1/2："Bass is weaker..." 被高置信误判负面，确认双面评价存在误报风险。
- 多语言类：两条非英文评论概率均接近 0，模型对非英文评论静默判为正常而非拒绝——这是静默漏报风险，E7 将加入非英文显式拒绝。
