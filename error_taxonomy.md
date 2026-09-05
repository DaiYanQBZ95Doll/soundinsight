# 错误分类学报告（error_taxonomy.md）

> 口径：冻结模型 + val_v2（20,000 条），阈值 0.9744。本次重算：TP=178，**FP=91，FN=73**，TN=19,658。
> 与 results_summary.md 冻结矩阵（TP=179/FN=72，F1 0.687）为同一验证集同一阈值下 GPU 推理不确定性的 ±1 样本翻转（重算 F1 0.685），非口径冲突；本报告统一采用本次重算值。
> 错误预分类由 LLM（deepseek-chat, temperature=0）完成（164/164 条），随后 DSH 对等距抽取的 30 条（15 FP + 15 FN）独立抽查；标注噪声候选 16 条已由用户人工终审（2026-09-05），结果见第 4 节。

## 1. FP（误报）分布：91 条

| 类别 | 数量 | 占比 | 含义 |
|---|---|---|---|
| fp_other_issue | 50 | 54.9% | 物流/耐用/连接/佩戴等其他问题被误判为音质负面 |
| fp_other | 16 | 17.6% | 整体正面评价（音质被称赞）被误判 |
| fp_label_noise | 12 | 13.2% | 标注噪声候选：人工终审 11/12 确认（修正估算 11/91=12.1%，Wilson 95% CI [6.9%, 20.4%]） |
| fp_neutral_compare | 7 | 7.7% | 双面/中性比较被误判 |
| fp_short | 6 | 6.6% | 短文本歧义 |
| fp_keyword | 0 | 0% | 关键词表面命中类误报为 0 |

FP 真实样例：
- （非音频产品）"the AF motor sounded like it was 'too tight'... made a high-pitched, almost abrasive sound whenever it would focus"——相机镜头对焦马达，非音频设备（prob 0.982）。
- （设备故障）"Less than 8 months in, the sound on this device just quit... 90 day warranty"——Kindle 故障，非音质（prob 0.987）。
- （标注存疑）"The bass. That's my ONLY complaint... there isnt any at all"——明确低音抱怨但整体满意，被标为正常。

## 2. FN（漏报）分布：73 条

| 类别 | 数量 | 占比 | 含义 |
|---|---|---|---|
| fn_soft | 27 | 37.0% | 委婉表达，无强负面词 |
| fn_other | 23 | 31.5% | 其他（含被 LLM 保守归类的声音问题） |
| fn_mixed | 16 | 21.9% | 整体正面但含音质不足的双面评价 |
| fn_label_noise | 4 | 5.5% | 标注噪声候选：人工终审 4/4 确认（4/73=5.5%，Wilson 95% CI [2.2%, 13.3%]） |
| fn_short | 3 | 4.1% | 短文本 |

FN 真实样例：
- （委婉）"for the price the sound quality should a lot better. It's like listening to an am radio station that goes in and out of range"（prob 0.956）。
- （双面）"Poor sound and low battery life but our kids love the minions so it served its purpose"——prob 0.97444963，与阈值 0.97444975 仅差 1.2×10⁻⁷，属于阈值边界漏报。
- （近阈值）"Cheap, terrible sound!"（prob 0.947）。

## 3. DSH 抽查 30 条（15 FP + 15 FN，等距抽样）

| id | kind | 文本（截断） | LLM 类别 | DSH 判定 |
|---|---|---|---|---|
| 0 | fp | audio sounds kinda distorted... 5.1 audio output "was not happening" | fp_label_noise | 同意：标注存疑，实为音质负面 |
| 6 | fp | sound on this device just quit... warranty | fp_other_issue | 同意 |
| 12 | fp | only Bluetooth... sound... short bursts... too long | fp_other_issue | 同意 |
| 18 | fp | this radio sounded great... stereo sound | fp_other | 同意 |
| 24 | fp | They aren't loud but they were perfect for my use | fp_neutral_compare | 同意 |
| 30 | fp | left earbud didn't work... Sound is good, but not great | fp_other_issue | 同意 |
| 36 | fp | audio sounds muffled and cuts in and out（指对比产品）... both loud and clear | fp_other_issue | 同意 |
| 42 | fp | cord uncomfortable... sound is decent | fp_other_issue | 同意 |
| 48 | fp | The bass... there isnt any at all... rest is PERFECT | fp_label_noise | 同意：标注存疑，实为低音负面 |
| 54 | fp | cover... blocks and dampen the sound | fp_other_issue | 同意（配件设计问题） |
| 60 | fp | sound is ok... weak | fp_other | 同意 |
| 66 | fp | Broke after only a few weeks. Sound quality was ok. | fp_other_issue | 同意 |
| 72 | fp | Voice quality is a little muffled | fp_short | 不同意类别：应归 fp_label_noise（轻微音质负面，标注存疑） |
| 78 | fp | do not produce an overwhelming amount of bass... comfortable | fp_other | 同意 |
| 84 | fp | AF motor... abrasive sound whenever it would focus（镜头） | fp_other_issue | 同意（非音频产品典型误报） |
| 91 | fn | sound quality should a lot better... am radio station | fn_soft | 同意 |
| 95 | fn | right ear is very very quiet... audio skipping and lagging | fn_soft | 同意 |
| 99 | fn | This isnt too bad if you dont like to listen to music loud | fn_other | 不同意：应归 fn_label_noise（标注存疑） |
| 103 | fn | bluetooth for a phone conversation... muffled... | fn_other | 不同意：通话问题非音质，应归 fn_label_noise（标注存疑） |
| 107 | fn | camera... built in microphone... sound like a robot | fn_label_noise | 同意：标注存疑 |
| 111 | fn | Cheap, terrible sound! | fn_short | 同意 |
| 115 | fn | Callers have difficulty hearing... enough volume | fn_soft | 同意 |
| 119 | fn | clips... broke... hard to hear due to static | fn_mixed | 同意 |
| 123 | fn | Poor sound and low battery life but our kids love... | fn_mixed | 同意（阈值边界 1.2e-7 漏报） |
| 127 | fn | speaker started making popping and hissing noises | fn_other | 不同意类别：杂音属音质问题，应为 fn_soft 类声音缺陷 |
| 131 | fn | Cannot understand voice on system - muffled | fn_other | 不同意类别：声音发闷属清晰度问题 |
| 135 | fn | don't mind a little static... uncomfortable | fn_other | 基本同意（轻微杂音提及，标签可商榷） |
| 139 | fn | I sound low and far away | fn_soft | 同意 |
| 143 | fn | laptop case... crackling noise（笔记本外壳） | fn_other | 不同意：非音频产品，应归 fn_label_noise（标注存疑） |
| 147 | fn | Some stations are nothing but static | fn_soft | 同意 |

抽查汇总：与 LLM 类别一致 23/30（76.7%）；标注存疑样本 FP 侧 3/15、FN 侧 4/15，合计 7/30（23.3%）。

人工终审（用户，2026-09-05）：16 条噪声候选全部复核，**15/16 确认**（93.8%，Wilson 95% CI [71.7%, 98.9%]）；唯一未确认的是 id69——LLM 判为"标注噪声"，人工确认实为**正面音质评价**（"blown away at the sound... rivals my JBL dock and my Bose dock"），即模型误报、标注正确。

## 4. 如实结论与改进方向

1. **误报主因是"其他问题"**（54.9%）：物流、耐用、连接、佩戴乃至非音频产品（镜头、Kindle、笔记本外壳）——这是训练语料来自全品类 Amazon Electronics 的固有代价，不是标注缺陷。改进方向（计划）：对非耳机产品评论做前置品类过滤；报告中对 FP 高频特征（broke/warranty/comfort）加规则后筛。
2. **漏报主因是委婉表达与双面评价**（58.9%）："should be better""isn't too bad""kids love it but poor sound"——单靠关键词/强负面词无法覆盖，与三星补漏 41.5% 漏检率互证。改进方向（计划）：保持 LLM 复核兜底；对 prob ∈ [0.5, 0.9744) 的中置信区在报告中显示"疑似负面"提示。
3. **阈值边界漏报真实存在**：至少 1 条（id 123）因 1.2×10⁻⁷ 概率差被漏报。阈值本身是验证集最优点，边界样本属于任何固定阈值都无法避免的代价；产品上以置信分层提示缓解。
4. **标注噪声（人工终审后）**：修正后估算 15/164 ≈ **9.1%**（Wilson 95% CI [5.6%, 14.5%]），其中 FP 侧 12.1% [6.9%, 20.4%]、FN 侧 5.5% [2.2%, 13.3%]。两条边界样本已记录在案：id48（整体正面但明确抱怨"完全没有低音"，判实为音质负面）、id93（主因线材问题，判实为非音质）。诚实边界：该数字只覆盖 LLM 标记的 16 条候选，若 LLM 漏标噪声样本，真实噪声率只高不低——本数字是候选集确认率下的**下界估算**。本报告不据此修改任何冻结数字。
5. **fp_keyword = 0**：规则时代的"关键词表面命中"误报在模型上已消失，说明微调模型学会了语义而非关键词——这是 RLCA 两阶段标注有效性的一个间接证据（如实记录，属模型在验证集上的行为）。

复算脚本：`val_pred_dump.py`（推理）、`prep_err_taxonomy.py`（错误抽取）、`llm_errclass`（宿主侧分类工具）、`taxonomy_agg.py`（聚合与抽查抽取）。
