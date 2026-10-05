# MODEL_CARD.md — SoundInsight 模型卡

> **出厂权重（2026-10-05 换型）**：`sound_model/` 现为 **v2**（`max_len=256`）；v1 权重归档于 `v2/model_v1_archive/`（哈希 `405d0a3f…`），仓库内 `sound_model/` 已同步为 v2（哈希 `690d3374…`，下载时自动校验）。
> **换型依据（人工真值）**：同一张 100 条盲判卡上，v2 精确率 **62.1%**（≥0.5）／**73.3%**（≥0.9）、漏判 **0/50**；v1 为 **42.0%／46.5%** 且属**开卷口径**（v1 训练语料覆盖全部评测集）——见登记表 X-25／X-26。


> **代际说明（2026-10-01）**：本文档主体为 **v1（复赛已提交口径）**，其中 v1 数字均已标注 `[v1]`；
> **当前代际为 v2**：`val_v3_test`（n=10,000／正例 128，阈值取自 `val_v3_tune`）上
> **F1@调优(0.6) = 0.7220`[v2]`、F1@0.5 = 0.7206`[v2]`、PR-AUC = 0.7811`[v2]`、归因宏 F1 = 0.8273`[v2]`、高音 F1 = 0.5333`[v2]`**；
> 两代**样本集不同、不可直比**；v2 完整证据见 `v2/w5_final.md`、`v2/w2_perclass_thresholds.md`、`v2/w7_calibration.md`、`docs/v2_gate_verdict.md`。


## 模型概述

> **适用范围（2026-10-03）**：仅对**含音频词汇**的评论判定（预筛由 `audio_gate.py` 定义，与标注口径同源）；其余标为未判定。该子集上分布内 F1 0.7220（P 0.748／R 0.695）。


- **任务**：英文耳机类评论二分类（是否为音质负面）+ 五类多标签归因（低音/清晰度/杂音/音量/高音）。
- **基座**：DistilBERT-base-uncased（66M 参数，Sanh et al. 2019），从 ModelScope 镜像下载（Hugging Face 官方源在本机网络不可达）。
- **训练数据**：McAuleyLab Amazon Reviews 2023（AmazonElectronics 类目）10 万条评论；正例来自 RLCA 两阶段标注（关键词规则初筛 + LLM 全量复核 + 三星评论召回补漏），1257 条冻结实验口径（当前工作集 1280 条）。
- **训练方式**：1:10 欠采样、5 折交叉验证、阈值扫描（最优阈值 0.9744[v1]）、Focal Loss（ICCV 2017）。
- **硬件**：RTX 4060 Laptop 8GB，batch_size=64，max_len=128。

## 性能（冻结口径，以 results_summary.md 为准）

- 二分类：val_v2（20,000 条，251 正例）F1 0.687；5 折 CV 平均 F1 0.6234[v1]±0.024；AUC-PR 0.7191[v1]；对比 SVM 0.497 / LR 0.410 / dummy 0.025（Welch t 检验 p=0.000932[v1]）。
- 阈值 0.5 时召回 89.6[v1]%、F1 0.62；阈值 0.9744[v1] 时 Precision≈66.2%、Recall≈70.9%（本次重算 TP=178/FP=91/FN=73）。
- 多标签：高音 F1=0（84 条样本与清晰度语义重叠），其余类别见 results_summary.md。

## 已知局限（如实披露）

1. **概率未校准**：十箱 ECE=0.0122，但 [0.8,0.9) 置信 0.854 vs 实际正例率 0.229；[0.9,1.0) 0.975 vs 0.555。概率值不可当作真实概率，UI 应使用置信分层。
2. **误报主因**：物流/耐用/连接/佩戴等"其他问题"占误报 54.9%，含非音频产品（镜头、Kindle、笔记本外壳）。
3. **漏报主因**：委婉表达与双面评价占漏报 58.9%；存在阈值边界漏报（最近一例差 1.2×10⁻⁷）。
4. **仅支持英文**：非英文评论显式拒绝（is_unsupported），多语言基座为未来工作。
5. **标注噪声**：候选 16 条经人工终审 15/16 确认（2026-09-05），估算标注噪声率约 9.1%（95% CI 5.6%-14.5%）——该数字为 LLM 候选集确认率下的下界估算，真实率只高不低。
6. **数据时效**：训练/验证语料截至 2023-03；跨年份分桶验证（2014-2022）未发现随时间衰减，2023 年桶样本少（5 正例）波动大，需持续监控。
7. **高音归因 F1=0 的机制**：已定位为"校准偏低导致的零触发"——该头在验证划分（252 条）最大概率仅 0.3332，0.5 阈值下从不判正（TP 0 / FP 0 / FN 13）；阈值降到 0.20 可恢复 F1 0.5161。根因：高音样本 84 条、与清晰度标签重叠 40.5%、含高音关键词的评论漏标 62.6%。诊断见 `docs/treble_failure_analysis.md`，复算脚本 `diagnose_treble.py`。当前模型仍冻结，未修（F1 仍为 0）。

## 使用方式

- 本地推理：`predict_core.py`（agent / api_server / benchmark 共用路径）。
- HTTP API：`python api_server.py` → `POST /predict {"texts":[...]}`；`GET /health`。
- Demo：`python demo_sound_v2.py`；批量报告：`python soundinsight_agent.py --csv x.csv --format md|excel`。
- 阈值与配置：`config.json`（max_len / batch_size / server 端口）。

## 许可与引用

- 模型权重存于 ModelScope `DaiYanQBZ95Doll/SoundInsight_models`，不入 git。
- 数据集引用：Hou et al. Bridging Language and Items for Retrieval and Recommendation, arXiv:2203.16852。
- 基座引用：Sanh et al. DistilBERT, arXiv:1910.01108。
