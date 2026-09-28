# 外部数字来源登记表（可引用性裁定）

> 用途：凡在项目材料中引用**外部**数字（非本项目实测），必须在本表登记来源、性质、核验状态与标注要求。
> 背景：`SoundInsight 激动线：一份严苛到不讲道理的验收标准.txt` 引用了多组行业数字，各方对其"是否有出处"先后给出过**两个方向的错误判断**（执行方"全部无出处"、桌面端"判为生成内容"），本表以逐条实检结论取代猜测。
> 规则：**"未能证实" ≠ "已被证伪"**；未核到来源的条目一律登记为"未核实"，不得描述为"虚假/生成内容"，也不得直接引用。
> 编制：2026-09-28（执行方）｜核验方式：`web_fetch` 取原文 + 本地解析一手 PDF

---

## 一、已核到来源（可引用，须按"标注要求"使用）

### S1 亚马逊无线耳机差评结构（151,295 条 / 67% / 37% / 33%）

| 项 | 内容 |
|---|---|
| 声明 | 3 个 Amazon US 热销无线耳机 ASIN 共 151,295 条评论；67% 差评集中在同一方向；可靠性差评率 37%（TOZO A1）、连接 33%、续航 33%；音质好评率 77%、音质差评最少 |
| 来源 | 《我们分析了11万条亚马逊差评，发现无线耳机卖家踩了同一个坑》，AMZ123 跨境头条，作者「卖家之家」，2026-05-09 ｜ <https://www.amz123.com/t/5qjFUmFd> |
| 数据方 | **Pangolinfo**（抓取 API 厂商）实时抓取 + 其 AI 情感分析引擎；原文自述方法：8 维度情感摘要 + 单独提取 1–3 星 critical reviews 逐条归类 + 统计占比 |
| 核验 | **2026-09-28 逐项比对原文，全部一致**（151,295 条、67%、37%、33%、33%、音质好评率 77%、"意外发现：音质差评反而最少"、价位 $9.99–$29.99） |
| 性质 | **厂商内容营销 + 跨境门户转载**；样本定义清楚但方法不可复现（无原始数据、无置信区间、无人工一致性检验）；原文自带免责声明"分析结果仅供参考" |
| 标注要求 | 引用须写：**"据 Pangolinfo 抓取分析、AMZ123 转载（2026-05）"**，并注明"厂商内容、方法概要、不可复现"。**不得**写成"行业数据显示"或用作论述的唯一支柱 |
| 备注 | 该文对"续航虚标"的分析与本项目讨论的**期望管理**概念同源，可作为该概念的实务例证 |

### S2 Harman/Olive 听音者分段（64% / 15% / 21%）

| 项 | 内容 |
|---|---|
| 声明 | Harman 研究存在三个听音者分段，比例 64% / 15% / 21%，分段主轴与低频偏好相关 |
| 来源 | Sean E. Olive, "The Perception and Measurement of Headphone Sound Quality: What Do Listeners Prefer?", *Acoustics Today*, Spring 2022 ｜ <https://acousticstoday.org/wp-content/uploads/2022/03/The-Perception-and-Measurement-of-Headphone-Sound-Quality-What-Do-Listeners-Prefer-Sean-E.-Olive.pdf> |
| 核验 | **2026-09-28 下载一手 PDF（10 页）本地解析，原文逐字命中**：<br>"A statistical method known as agglomerative hierarchical clustering exposed three different segments or classes of listeners…"<br>"Class 1 includes most listeners (**64%**) who prefer headphones that closely comply with the Harman target. Class 2 listeners (**15%**) prefer the Harman target with 4-6 dB more bass. Class 3 listeners (**21%**) prefer the Harman target curve with 2 dB less bass."<br>"…the preferred bass level is the main feature that defines membership in a class." |
| 性质 | **一手同行评议刊物（AIP/ASA 旗下 Acoustics Today）**，引用价值最高 |
| 标注要求 | 可直接引用，注明作者、刊物、年份；分段主轴确为**低频**（这一点与转述一致） |
| 未核到 | 转述中"7 年 / 9 年研究"这一**年限**表述，我在文中未核到对应句子（文中"30 years ago"指扬声器行业），故年限这一点保持**未核实**，引用时不要带年限 |

---

## 二、核到来源但**不可作为行业事实引用**（原始出处不可得）

### S3 "72% 新硬件产品六个月内未达音频性能基准" / "退货率平均降低 18%"

| 项 | 内容 |
|---|---|
| 来源 | Apps Scale Lab（SEO 内容站），"Audio Hardware Failures: 72% Miss 2026 Benchmarks"，2026-09-15 ｜ <https://appscalelab.com/audio-hardware-failures-72-miss-2026-benchmarks/> |
| 核验 | **2026-09-28 取原文**：72% 的表述为 "A recent industry report indicates that 72% of new hardware products fail…"——**该报告无名称、无链接、无发布方**；18% 挂在 "The Gartner Group, in their 2026 industry outlook" 名下，但链接只指向 Gartner 客户体验行业页，**无报告编号或可查条目**；同页另有 45%（称 Statista 2025 调查）、25%（称 Deloitte 2025）、15%（称 PwC 2026）等，均为无链接的二手转述 |
| 性质 | **二手转述 + 内容营销**；页面作者简介为模板化虚构形象（同一站点多位"作者"共用套话），不可作为研究来源 |
| 裁定 | **不得作为行业事实引用**。若必须提及，只能写"某内容站转述称…（原始报告未公开）"，且不得用于支撑任何结论 |
| 备注 | 桌面端 Kimi 判"疑似有出处"、执行方原判"无出处"——**两者都不准确**：出处存在，但出处的性质决定它不可引用 |

---

## 三、仍未核实（登记为缺口，不得当事实）

| # | 声明 | 核验状态 |
|---|---|---|
| S4 | ASR（Audio Science Review）"好的工程意味着一个测量的闭环…"引语 | **未核实**（未取到原始页面）；引用前须核到具体帖子/文章 |
| S5 | 两阶段 DNN 逆向预测谐振吸声单元尺寸、Helmholtz 共振器逆向设计、扬声器非线性谐波失真混合模型 | **方向真实、具体配置未核实**；引用须核到论文原文 |
| S6 | Olive 研究的"年限（7 年 / 9 年）" | **未核实**（见 S2 备注） |

---

## 四、使用规则（写入项目材料前必读）

1. **能引用**：S2（一手文献）→ 正常引用并给出版本信息；S1（厂商内容）→ 必须标"来源 + 厂商性质 + 不可复现"。
2. **不能引用**：S3（无原始出处的二手转述）→ 只能作为"外部存在此类说法"的旁证，不得支撑结论，不得写成"行业数据"。
3. **未核实**：S4–S6 → 先核到来源再谈引用。
4. **判断纪律**（本轮教训）：对任何外部声明，"没搜到"只能得出**未核实**，不能得出**不存在/虚假**；对任何状态类断言（未使用 / 未开展 / 无出处），必须给出**核验日期或状态源**。
5. 引用外部数字时，**不得**与本项目实测数字并排成"同一口径"（项目实测与二手行业数字不可混比）。
