项目名称：SoundInsight 蓝牙耳机音质差评智能归因系统

项目简介：基于轻量预训练模型的蓝牙耳机音质差评自动识别与归因系统，帮助卖家快速定位音质问题。

项目背景：亚马逊2026年跨境电商白皮书显示，中国卖家的人工智能使用率已超过九成八，评论洞察正成为运营刚需。耳机类目差评量大，音质问题藏在长文本里难以人工归因。本项目用少量真实评论训练可用的识别模型，把人工翻评变成自动归因。

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
第二步，启动 Demo。
python demo_sound_v2.py
第三步，一键批量分析。
python soundinsight_agent.py --csv 你的评论文件.csv
第四步，重新训练模型（可选）。
python train_final.py
python train_multilabel.py

数据说明：数据来自 McAuley Lab 官方 Amazon Electronics 评论数据集，前五千条用于初赛，扩充至十万条用于复赛升级。标注采用规则初筛加 LLM 全量复核的两阶段方式，规则初筛命中音质关键词且评分两星以下为正例候选，随后由大模型逐条复核去伪，并补充音质相关三星评论中的漏检样本，最终得到正例一千二百五十七条。

模型性能：弱标注标签上，DistilBERT 五折交叉验证准确率约 0.987，调优阈值 F1 约 0.55，显著高于 TF-IDF 加线性 SVM 的 0.42 与逻辑回归的 0.36。LLM 清洗标签上，小模型与教师答案一致率达 85.9%，F1 0.865。多标签问题归因宏 F1 0.64，其中低音 0.93、清晰度 0.83、杂音 0.77、音量 0.69。清洗标签上的最终交叉验证与模型性能以 results_summary.md 为准。

注意事项：首次训练需要联网，脚本会先访问 Hugging Face 下载基座模型，失败时自动切换 ModelScope 镜像；若完全无法访问外网，可手动将基座模型文件放入 distilbert-base-uncased 文件夹。仓库默认不附带模型权重，启动 Demo 或 Agent 前需先运行训练脚本生成 sound_model 与 multi_label_model 文件夹，或使用已有的本地权重。Windows 控制台若出现编码报错，请先设置环境变量 PYTHONIOENCODING 为 utf-8。数据获取与扩充脚本需要访问 mcauleylab.ucsd.edu，网络受限时可直接使用仓库内已提交的数据文件。
