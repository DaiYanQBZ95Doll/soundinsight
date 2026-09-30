# -*- coding: utf-8 -*-
"""M1：按官方决赛模板生成主文档（更新世界的锋芒_SoundInsight_决赛入围定稿作品.docx）。

原则（冻结清单 §二 M1 / §八 映射表）：
- 主文档＝填写后的官方模板：打开模板、在对应标题后插入正文、填写表格，保留模板标题与样式；
- 内容映射：模板九节 = v4 一~六节 + 十一~十三节；v4 第七节（实验）压缩为第六节的阶段成果指标表；
  v4 第八节（归因定位）并入 4.1；v4 第九节（局限）、5.4（数据许可）、勘误（E2）、置信度三档（W17）走文末附录；
- 口径：v2 指标带 [v2]，v1 历史值带 [v1]；成本假设（8 小时／30 元每小时）显式标注为假设；
- 数字来源：v2/w5_final.md、v2/w2_perclass_thresholds.md、v2/w7_calibration.md、
  docs/v2_gate_verdict.md、docs/w17_confidence_actions.md、docs/e2_erratum.md。

用法：python build_finals_docx.py [--out 文件名.docx]
"""
from __future__ import annotations

import argparse
import os
import sys

from docx import Document

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "hackathon-决赛入围定稿作品提交模板-天池版.docx")
DEFAULT_OUT = os.path.join(HERE, "更新世界的锋芒_SoundInsight_决赛入围定稿作品.docx")

TEAM = {"团队名称": "更新世界的锋芒", "队长姓名": "黎同竣",
        "联系电话": "19195907942", "联系邮箱": "2799920054@qq.com"}
LINKS = {
    "GitCode": "https://gitcode.com/DaiYanQBZ95Doll/soundinsight",
    "线上 Demo": "https://modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight",
    "产品演示视频": "随包提交（本地 mp4 文件）",
    "测试账号": "无需账号（在线 Demo 公开访问）",
}
BAILIAN_ROWS = [
    ("qwen3.7-plus",
     "跨 LLM 稳健性对照实验（零样本／5-shot／复核；评审用途，非产品推理）",
     "阿里云百炼 Token Plan API（OpenAI 兼容基地址 "
     "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1）"),
    ("deepseek-chat",
     "RLCA 标注复核 + 跨 LLM 对照实验",
     "DeepSeek 官方 API（https://api.deepseek.com/v1/chat/completions）"),
]

CONTENT: dict[str, list[str]] = {
    "二、参赛信息": [
        "参赛场景：AI市场洞察",
        "方案名称：SoundInsight（蓝牙耳机音质差评智能归因系统）",
        "一句话定义：为跨境电商耳机卖家提供音质差评自动识别与五类问题归因的一站式洞察工具，"
        "把人工数小时的差评梳理压缩到分钟级；产品推理 100% 本地，卖家数据不出境。",
    ],
    "3.1 目标用户与业务痛点": [
        "目标用户：跨境电商平台耳机类目的中小卖家（团队 <10 人、无专职数据分析师）。",
        "核心痛点：",
        "1）差评量大：日均 50–200 条，人工翻看耗时；",
        "2）语言杂：以英文为主，夹杂西班牙语、日语等；",
        "3）音质问题隐蔽：藏在长文本里——本项目实测三星评论中 41.5%（95% CI 34.9–48.4%，n=200，"
        "Wilson 区间）实为音质差评却被关键词规则漏检；",
        "4）改进滞后：无法系统归类问题，产品迭代只能凭经验。",
    ],
    "3.2 应用场景与使用流程": [
        "场景一（选品）：产品经理输入竞品 ASIN，生成音质差评对比报告；",
        "场景二（优化）：运营上传自家评论 CSV，一键生成问题分布与整改建议；",
        "场景三（迭代）：研发对比改版前后报告，验证改进效果；",
        "使用流程：上传 CSV → 分析（本地 GPU 实测 1.763 秒／1000 条）→ 查看报告（含优先级排序）"
        "→ 导出 Markdown／Excel。",
    ],
    "3.3 商业价值与预期效果": [
        "| 指标 | 人工翻评 | SoundInsight | 说明 |",
        "|---|---|---|---|",
        "| 处理 1,000 条评论耗时 | 8 小时（假设口径） | 约 1.8 秒（本地 GPU 实测 1.763 s／1000 条；"
        "CPU 28.4 秒） | >99.9% |",
        "| 人力成本（按 30 元／小时，假设口径） | 240 元（假设口径） | 0 元（本地推理，无 API 费用） | 100% |",
        "| 音质差评识别 | 依赖经验、易遗漏 | F1@调优 = 0.7220[v2]；高召回档 F1@0.5 = 0.7206[v2] | 可量化、可复算 |",
        "| 问题归因 | 无法系统分类 | 五类自动归因，宏 F1 = 0.8273[v2]（逐类阈值） | 从无到有 |",
        "| 结论可执行性 | 人工经验判断 | 每条结论带置信度档位与建议动作（高／中／低三档） | 可直接进入整改评审 |",
        "注：性能指标在 v2 留出集（val_v3_test，n=10,000、正例 128）上测得，"
        "与 v1 复赛数字（val_v2）样本集不同、不可直比；v1 值见附录 C。",
    ],
    "3.4 市场前景与落地可行性": [
        "市场规模：全球耳机市场约 280 亿美元（Statista 2025，二手来源，引用请注明）；"
        "亚马逊耳机类目年评论量超 5,000 万条。",
        "目标用户结构：中小卖家占比约 70%，其中约 90% 无专职数据分析师（同上，二手来源）。",
        "品类可迁移性：RLCA 标注框架 + DistilBERT 微调流程可迁移至美妆（肤感）、食品（口味）等品类；"
        "迁移成本可量化，见附录 F。",
        "商业模式：开源版（社区）→ SaaS 版（订阅）→ 企业版（私有化部署，数据不出境）。",
    ],
    "4.1 产品简介": [
        "SoundInsight 是一款面向跨境电商耳机卖家的音质差评智能归因系统，自动识别评论中的音质负面反馈，"
        "并归因到低音、清晰度、杂音、音量、高音五类问题，输出可执行的洞察报告。",
        "差异化定位：与退货根因分析类工具不同，本系统做的是文本内的细粒度归因——"
        "把主观听感映射到可复算的问题类别与型号分布上，并把每一步数字做成可审计的证据链（见第六节与附录）。",
    ],
    "4.2 核心功能清单": [
        "1）单条评论判定：输入评论文本，输出音质负面概率与五类问题类别；",
        "2）批量 CSV 分析：上传评论文件，输出六节完整报告（总体概况／问题分布含占比与优先级／"
        "典型案例附五类归因概率／行动建议／验证指标／置信度档位与建议动作），可下载报告文件；",
        "3）一键洞察 Agent：python soundinsight_agent.py --csv 文件.csv，"
        "与 Demo 共用同一报告模块（report_builder.py），口径完全一致，支持 Markdown／Excel 与中英双语；",
        "4）型号级聚合与趋势预警（v2 新增）：按 parent_asin 汇总差评率 Top-N（样本量门槛 ≥10 条），"
        "按月度追踪波动并给出告警阈值。",
    ],
    "4.3 使用说明": [
        "安装：pip install -r requirements.txt；启动 Demo：python demo_sound_v2.py；"
        "启动 Agent：python soundinsight_agent.py --csv test.csv；"
        "HTTP API：`uvicorn api_server:app`（默认 127.0.0.1:7860）；`GET /health` 返回状态与阈值，`POST /predict` 请求体为 `{\"texts\": [\"评论1\", \"评论2\"]}`，返回 `n`／`n_negative`／`n_unsupported`／`results[]`（每条含 `prob`、`pred`、`issues`）。",
        "在线 Demo：ModelScope 创空间 https://modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight"
        "（应用直链 https://daiyanqbz95doll-soundinsight.ms.show）。",
        "截图：单条判定页、批量分析页、Agent 报告页（各 1 张，见附件其他材料）。",
    ],
    "5.1 系统架构图": [
        "见 architecture.png。文字链路：",
        "[Amazon 评论数据 10 万条] → [RLCA 两阶段标注] → [DistilBERT 二分类 + 五类多标签归因] "
        "→ [Agent 报告／Gradio Demo／HTTP API]。",
        "标注层：关键词规则初筛 → LLM 逐条复核去伪 → 三星／四五星补漏复核；"
        "模型层：1:10 欠采样、阈值扫描、5 折交叉验证；"
        "评测层：tune/test 分离（阈值只在调参划分上选）、长度分桶、校准评估、统计检验。",
    ],
    "5.3 技术组件说明": [
        "前端：Gradio（单条判定／批量分析／边界案例三页）；后端：Python + PyTorch + Transformers；",
        "模型：DistilBERT-base-uncased（66M 参数；权重托管于 ModelScope，见附录 A）；",
        "数据：McAuley Lab Amazon Reviews 2023（AmazonElectronics 类目，10 万条评论）；",
        "标注：RLCA 两阶段流水线（规则初筛 + LLM 全量复核）；",
        "部署：本地 GPU 推理（RTX 4060）与在线 CPU 空间双形态，一键启动；",
        "评测与审计：check_doc_numbers.py 数字审计（186 项检查／0 FAIL）、scan_repo_hygiene.py "
        "仓库卫生扫描（密钥 0）、test_audit_checks.py 负向自测（15 项）。",
    ],
}
