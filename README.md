项目名称：SoundInsight 蓝牙耳机音质差评智能归因系统

> ## 版本与口径指引（先读这一段）
>
> **哪个算数**
> - 数字权威源：`results_summary.md`（其余文档引用它；冻结数字见 `AI_HANDOFF/03_metrics_and_caveats.md` §二）。
> - 对外主文档：`competition_v4.md`（提交用的 `更新世界的锋芒_SoundInsight_复赛作品.pdf` / `.docx` 由 `md_to_pdf.py` / `md_to_docx.py` 从它生成）；`competition_v3.txt` 为同源精简版。
> - 提交物校验值：根目录 `hashes.txt`（外层容器）与提交包内 `hashes.txt`（四项提交物内容哈希）。
> - 冻结资产（任何人不改）：`sound_model/`、`multi_label_model/`、`val_v2.csv`、训练脚本。
>
> **哪些是历史材料（保留当时状态，不作为当前口径）**
> - 初赛与过程材料：`competition_v2.*`、`SoundInsight_创意方案/`、`docs/work_summary_*`、`PROGRESS_SYNC.md`、`docs/process_review_d10.md`、`training_output.txt`、`ppt_text_dump.md` 等。
> - 修复脚本本身含"旧表述 → 新表述"的映射（`ppt_speed_fix.py`、`fix_ppt_threshold.py`、`retime_srt.py`），因此正文会出现已废弃字样，属工具输入而非结论。
> - 已废弃 claim 一览、"哪个算数"的完整规则、隐私与凭据说明：**`docs/legacy_materials_notice.md`**。
>
> **三套口径不可混用**：冻结口径（val_v2 20,000 条）／1,000 条子集口径（LLM 对照）／工程口径（吞吐、校准、长度分桶）。同一模型的精确率/召回率还分阈值档（0.9744 与 0.5），必须成对阅读。
>
> **卫生自检**：`python scan_repo_hygiene.py` → 报告 `docs/repo_hygiene_scan.md`（密钥 / 隐私 / 废弃 claim / 生成物一致性）。

项目简介：基于轻量预训练模型的蓝牙耳机音质差评自动识别与归因系统，帮助卖家快速定位音质问题。

**给 AI 助手的入口（推荐先读）**：AI_HANDOFF/README.md —— 项目导览包：阅读顺序、三套数字口径、证据链索引、代码导览、红线与待办、术语表，以及机器可读的全项目索引 AI_HANDOFF/manifest.json。

文件总索引（全部文件的分类清单与状态）：docs/file_inventory.md
全流程记录（初赛→复赛，最终确认用）：docs/project_full_record.md

项目背景：耳机类目差评量大、音质问题藏在长文本里难以人工归因，评论洞察正成为跨境卖家的运营刚需。本项目用少量真实评论训练可用的识别模型，把人工翻评变成自动归因。

项目结构：
local_data.csv：五千条 Amazon Electronics 真实评论，包含评论文本与星级评分。
electronics_expanded.csv：扩充后的十万条真实评论数据。
labeled_expanded.csv：规则初筛标注数据，含音质相关、音质负面与五类问题标签。
labeled_llm.csv：经 LLM 全量复核的最终标签集，含清洗后的音质负面标签与问题类别。
labeled_data_final.csv：早期五千条版本的标准标注数据，保留用于复现。
sound_model 文件夹：最终二分类模型权重、分词器与阈值配置文件。
multi_label_model 文件夹：多标签问题归因模型与类别定义。
label_final.py：早期关键词标注脚本，生成五千条版本标签。
label_v3.py：扩充数据的规则初筛标注脚本，生成音质相关、音质负面与五类问题标签。
prep_review_input.py：抽取规则正例供 LLM 复核。
prep_three_star.py：抽取音质相关三星样本供 LLM 补漏复核。
merge_review.py：合并正例复核结果并计算弱标注精度。
merge_three_star.py：合并三星样本补漏结果。
fetch_electronics.py：数据获取脚本，从官方数据源分段下载前五千条评论。
extend_data.py：数据扩充脚本，续拉前缀并解析十万条评论。
train_sound_model.py：早期小样本训练脚本，保留用于复现。
train_final.py：基于 LLM 清洗标签的最终二分类训练脚本。
train_multilabel.py：多标签问题归因训练脚本。
baseline_cv.py：基线交叉验证脚本，对比全判正常、逻辑回归与线性SVM。
distilbert_cv.py：DistilBERT 交叉验证脚本，支持自定义标签列。
distilbert_vs_llm.py：小模型与 LLM 教师答案一致性对比脚本。
soundinsight_agent.py：一键洞察 Agent，输入评论 CSV 输出洞察报告。
demo_sound.py：基础 Gradio 演示，单条评论判定。
demo_sound_v2.py：升级版 Gradio 演示，支持单条判定与批量 CSV 分析。
test_model.py：验证集评估脚本，输出指标、阈值扫描与混淆矩阵。
results_summary.py：实验结果汇总脚本，生成 results_summary.md。
requirements.txt：依赖库清单。
README.md：本说明文件。
.gitignore：版本控制忽略清单。

环境依赖：Python 3.12 及以上，主要依赖 torch 2.7.1、transformers 5.9.0、pandas 2.3.3、numpy 2.5.1、scikit-learn 1.8.0、gradio 6.24.0、requests 2.34.2，GPU 训练需 CUDA 11.8 版 PyTorch。

快速启动：
第一步，安装依赖。
pip install -r requirements.txt
第二步，下载模型权重。
python download_models.py --repo 你的用户名/SoundInsight_models
第三步，启动 Demo。
python demo_sound_v2.py
第四步，一键批量分析。
python soundinsight_agent.py --csv 你的评论文件.csv
如需 Excel 版报告（总体概况/问题分布/典型案例三个 sheet，高优先级标红）：
python soundinsight_agent.py --csv 你的评论文件.csv --format excel

在线 Demo 地址：https://modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight （应用直链 https://daiyanqbz95doll-soundinsight.ms.show）

数据说明：数据来自 McAuley Lab 官方 Amazon Reviews 2023（AmazonElectronics 类目）数据集，前五千条用于初赛，扩充至十万条用于复赛升级。标注采用 RLCA 两阶段方式，规则初筛命中音质关键词且评分两星以下为正例候选，随后由大模型逐条复核去伪，并补充音质相关三星评论中的漏检样本（三星评论漏检率 41.5%）。实验与交叉验证基于 1257 条冻结口径，后续高音补捞扩展至 1288 条，中期置信区间复核后移除 8 条，当前工作集 1280 条，核心结论不受影响。

数据许可与合规披露：数据集版权归原发布方（McAuley Lab，https://amazon-reviews-2023.github.io/）与原始评论作者所有，本项目仅用于学术研究与竞赛用途；具体许可条款以原发布方页面为准，商用前须自行确认授权。标注阶段的合规说明：仅规则初筛命中的候选评论（约 1502 条）与三星补漏评论经大模型 API（deepseek-chat）复核标注，即只有标注管线触碰外部 API；**产品推理 100% 本地完成，卖家上传的评论数据不出境、不经过任何第三方 API**。

模型性能：最终二分类模型在固定验证集 20000 条（251 正例）上，按两个决策阈值分列——**阈值 0.9744（对外显示 0.97，验证集上 F1 最优）**：精确率 66.3%、召回率 71.3%、F1 0.6871；**阈值 0.5（默认，高召回档）**：精确率 47.9%、召回率 89.6%、F1 0.6241。两档指标须成对阅读，不可跨阈值混用。5 折交叉验证调优 F1 均值 0.6234 加减 0.0240，波动 3.9%；Welch t 检验 p 等于 0.000932，显著优于 SVM 基线 0.497、逻辑回归 0.410 与全判正常 0.025；PR 曲线 AUC-PR 为 0.7191。标注侧弱标注精度 51.8%，人工抽查 50 条通过率 78%。多标签归因宏 F1 0.65，其中低音 0.79、清晰度 0.77、杂音 0.84、音量 0.84，高音因样本稀缺为 0。全部数字以 results_summary.md 为准。

注意事项：首次训练需要联网，脚本会先访问 Hugging Face 下载基座模型，失败时自动切换 ModelScope 镜像；若完全无法访问外网，可手动将基座模型文件放入 distilbert-base-uncased 文件夹。仓库默认不附带模型权重，启动 Demo 或 Agent 前需先运行训练脚本生成 sound_model 与 multi_label_model 文件夹，或使用已有的本地权重。Windows 控制台若出现编码报错，请先设置环境变量 PYTHONIOENCODING 为 utf-8。数据获取与扩充脚本需要访问 mcauleylab.ucsd.edu，网络受限时可直接使用仓库内已提交的数据文件。
