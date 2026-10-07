---
# 详细文档见https://modelscope.cn/docs/%E5%88%9B%E7%A9%BA%E9%97%B4%E5%8D%A1%E7%89%87
domain: #领域：cv/nlp/audio/multi-modal/AutoML
# - cv
tags: #自定义标签
-
datasets: #关联数据集
  evaluation:
  #- iic/ICDAR13_HCTR_Dataset
  test:
  #- iic/MTWI
  train:
  #- iic/SIBR
models: #关联模型
#- iic/ofa_ocr-recognition_general_base_zh

## 启动文件(若SDK为Gradio/Streamlit，默认为app.py, 若为Static HTML, 默认为index.html)
# deployspec:
#   entry_file: app.py
license: Apache License 2.0
---
#### Clone with HTTP
```bash
 git clone https://www.modelscope.cn/studios/DaiYanQBZ95Doll/SoundInsight.git
```

---

## SoundInsight —— 蓝牙耳机音质差评智能分诊（在线体验）

- **出厂权重**：**判别器**（底座 v2 ＋ 硬负例；2026-10-05 起）——本空间加载的即该权重。
- **性能口径（人工盲判，两张独立样本各 50 条）**：优先处理档**精确率 75–78%、召回 68.3%（95% CI 46–100%）**；
  历史世代（v1）数字仅作沿革记录，**两套口径不可混用**。
- **适用范围**：只对**提到声音**的评论判定（约占语料 12.9%）；范围外一律标「未判定」并按 13 类给出差评原因
  ——**未判定 ≠ 正常**。它是**分诊工具**，最终判断由人做。
- **隐私**：推理 100% 本地、单条边际成本 0、卖家数据不出境。
- 完整证据与边界见仓库主文档与附录 C。
