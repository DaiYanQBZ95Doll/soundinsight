项目名称：SoundInsight 蓝牙耳机音质差评智能归因系统

项目简介：基于轻量预训练模型的蓝牙耳机音质差评自动识别与归因系统，帮助卖家快速定位音质问题。

项目背景：亚马逊2026年跨境电商白皮书显示，中国卖家的人工智能使用率已超过九成八，评论洞察正成为运营刚需。耳机类目差评量大，音质问题藏在长文本里难以人工归因。本项目用少量真实评论训练可用的识别模型，把人工翻评变成自动归因。

项目结构：
local_data.csv：五千条 Amazon Electronics 真实评论，包含评论文本与星级评分。
labeled_data_final.csv：弱监督标注完成的训练数据，包含音质相关与音质负面两列标签。
sound_model 文件夹：微调后的模型权重、分词器与阈值配置文件，Demo 直接加载。
label_final.py：关键词标注脚本，生成音质相关与音质负面标签。
train_sound_model.py：模型训练脚本，自动下载基座模型并输出微调模型。
test_model.py：验证集评估脚本，输出准确率、F1 与阈值扫描结果。
demo_sound.py：Gradio 交互演示脚本，输入评论输出判定结果与概率。
fetch_electronics.py：数据获取脚本，从官方数据源分段下载评论并生成 local_data.csv。
electronics_prefix.bin：数据下载缓存，供离线复现数据使用。
requirements.txt：依赖库清单。
README.md：本说明文件。
.gitignore：版本控制忽略清单。

环境依赖：Python 3.12 及以上，主要依赖 torch 2.7.0、transformers 5.9.0、pandas 2.3.3、numpy 2.5.1、scikit-learn 1.8.0、gradio 6.24.0、requests 2.34.2。

快速启动：
第一步，安装依赖。
pip install -r requirements.txt
第二步，启动 Demo。
python demo_sound.py
第三步，重新训练模型（可选）。
python train_sound_model.py

数据说明：数据来自 McAuley Lab 官方 Amazon Electronics 评论数据集，取前五千条。标注方式为弱监督，评论命中音质关键词表视为音质相关，评分两星及以下标记为音质负面，共得正例六十三条。

模型性能：验证集准确率百分之九十八点三，F1 值零点三七。由于正例仅六十三条，属于小样本条件，指标存在波动属正常；模型对低音不足、电流声等强信号关键词的识别率在百分之九十八以上。

注意事项：首次训练需要联网，脚本会先访问 Hugging Face 下载基座模型，失败时自动切换 ModelScope 镜像；若完全无法访问外网，可手动将基座模型文件放入 distilbert-base-uncased 文件夹。仓库默认不附带模型权重，启动 Demo 前需先运行训练脚本生成 sound_model 文件夹，或使用已有的本地权重。Windows 控制台若出现编码报错，请先设置环境变量 PYTHONIOENCODING 为 utf-8。数据获取脚本需要访问 mcauleylab.ucsd.edu，网络受限时可直接使用仓库内已提交的数据文件。
