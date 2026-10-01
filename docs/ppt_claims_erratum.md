# PPT 主张勘误（耐久件，勿删）

> **为什么单独一份**：`ppt_text_dump.md` 是 `audit_ppt.py` 的**导出物**（`open(...,"w")` 全量覆盖），
> 任何手工追加的注解都会在下次导出时丢失（红队 QWEN-2/SPIKE-12 指出）。
> 故**所有对 PPT 主张的更正都写在本文件**，导出物只保留一行指针。
> 生成时刻：2026-10-01 20:05｜pptx：`SoundInsight：跨境电商耳机音质差评智能归因系统.pptx`
> （20 页，mtime 2026-09-14 20:03，属**复赛期产物**）

## 一、竞品表述（slide4 与 slide14，**已过时**）

**PPT 原文**：
- slide4：「Helium 10、Jungle Scout 等主流 SaaS 仅做通用情感分析，无法识别低音浑浊、高音刺耳等专业声学问题」＋「0 款专业…」
- slide14：「Helium 10 与 Jungle Scout 仅提供通用情感分析…」

**外部核验（2026-10-01，执行方实测）**：
- 市场上已有**专门的评论 AI 分析平台**：[Shulex VOC.AI](https://www.shulex.com/)（跨境电商评论分析 + AI 客服，
  官网列示 **ANKER／eufy／ESR／GameSir 等 100+ 头部品牌**，提供 Agent 问答、API/MCP、VOC 看板）；
  [Skieer VOC](https://chromewebstore.google.com/detail/skieer-voc/bcniifmdiagmbieijjpmnlfnbhimcmde)（插件形态）。
- **因此"仅做通用情感分析"不成立**（对 Helium 10／Jungle Scout 两家的描述亦随之不充分）。

**修正后的可用表述**：
> 通用工具（Helium 10／Jungle Scout）偏向关键词与选品；VOC 平台（如 Shulex VOC.AI）已用 LLM 做评论洞察。
> **本项目的差异点是**：① 声学五类归因（低音／清晰度／杂音／音量／高音）；② 本地推理、零 API 成本、数据不出境；
> ③（规划中）与客观频响数据挂钩。

**不可说**：「比竞品更准／更强」——**未做过同数据集对比实测**。

## 二、吞吐数字（slide 中出现两个未标环境的说法）

- 「30 秒/千条」≈ **CPU 实测**（35.2 条/s ＝ 28.4 秒/千条），原文未标 CPU；
- 「约 2 秒(GPU 实测)」＝ **GPU 567.1 条/s ＝ 1.76 秒/千条** ✓ 与 `throughput_eval.md` 一致。
- **权威表述**：**GPU 1.76 秒/千条、CPU 28.4 秒/千条**（`throughput_eval.md`，RTX 4060 Laptop 8GB）。

## 三、人力成本口径

- 「240 元」＝ **假设口径**（30 元/时 × 8 小时），**非实测**；决赛主文档已标注，复赛期材料本轮补注。

## 四、若进 6 强（路演 PPT）

**必须在路演版 PPT 中改用本文件 §一 的修正表述**（slides 4／14），
并核对 §二 的吞吐数字标注运行环境。此项已登记到 `docs/frozen_execution_checklist.md`。
