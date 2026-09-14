# 05 代码导览（模块职责 · 入口 · 运行方式）

> 全部脚本位于项目根目录（除特别注明）。运行前建议：`chcp 65001` + `set PYTHONIOENCODING=utf-8`。
> 本机环境：Windows / Python 3.12.6 / torch 2.7.1+cu118 / transformers 5.9.0 / gradio 6.24.0 / RTX 4060 Laptop 8GB。

## 一、产品侧（交付给用户的四个入口）

| 文件 | 职责 | 运行方式 |
|---|---|---|
| `soundinsight_agent.py` | 一键洞察 Agent：六节报告；`--format md\|excel`；`--lang zh\|en`；非英文评论跳过计数；成本对照行；校准提示 | `python soundinsight_agent.py --csv 评论.csv --format excel --lang zh` |
| `demo_sound_v2.py` | Gradio 三页 Demo（单条判定 / 批量分析 / 边界案例），端口 7860；**已内置"本地环回绕过系统代理"**（否则 gradio 自检 502 退出） | 双击 `启动Demo.bat`，或 `python demo_sound_v2.py` |
| `predict_core.py` | 共享推理核心：模型加载缓存 + 批量推理 + 五类归因 + 非英文显式拒绝（`is_unsupported`，实现见 `text_utils.py`） | 被 agent/api/基准脚本 import |
| `report_builder.py` | **报告生成共享模块**（六节报告 + 优先级规则 + 结论判定 + 成本对照 + 中置信提示），Agent / 本地 Demo / 在线版三方共用同一口径 | 被 agent、demo、deployment/app.py import |
| `text_utils.py` | 文本层共享工具：非英文显式拒绝判定（唯一实现处） | 被 predict_core / demo / 在线版引用 |
| `api_server.py` | FastAPI：`GET /health`、`POST /predict`（body `{"texts":[...]}`） | `python api_server.py` → 127.0.0.1:7860 |
| `config.json` | 集中配置：模型目录、阈值文件、max_len=128、batch_size=64、服务端口 | 被上述脚本读取 |
| `install.bat` | Windows 一键安装（venv + 依赖 + 模型下载 + 自检） | 双击 |
| `download_models.py` / `verify_download_urls.py` | 从 ModelScope 下载权重（URL 含目录前缀）/ 校验下载链路 | `python download_models.py` |

## 二、数据与标注（RLCA 管线）

| 文件 | 职责 |
|---|---|
| `fetch_electronics.py` | HTTP Range 分段拉取官方数据前缀 → `local_data.csv`（前 5,000 条） |
| `extend_data.py` | 续拉前缀并解析 → `electronics_expanded.csv`（10 万条） |
| `restore_timestamps.py` | 重建含 `timestamp` 的 10 万条数据（文本精确匹配校验） |
| `label_v3.py` / `label_final.py` | 规则初筛（关键词边界匹配 + 星级阈值） |
| `prep_review_input.py` → `merge_review.py` | 抽正例给 LLM 复核 → 合并并算弱标注精度（51.8%） |
| `prep_three_star.py` → `merge_three_star.py` | 三星评论召回补漏（1,271→479） |
| `retier_conf.py` / `prep_human_review.py` | 置信度分层 / 生成人工复核表 |
| `a4_mid_remove.py` / `apply_mid_demotion.py` | 中置信剔除与备份（1,288→1,280） |
| `make_samples.py` | 生成演示样例集 `sample_reviews_100.csv`（含 rating/期望标签） |

## 三、训练（冻结脚本，勿改）

| 文件 | 用途 |
|---|---|
| `train_final.py` | 最终二分类模型（1:10 欠采样 + 交叉熵 + 阈值扫描） |
| `train_multilabel.py` | 五类多标签归因（独立 sigmoid 头） |
| `distilbert_cv.py` | 5 折交叉验证（支持自定义标签列） |
| `ablation_train.py` | 三组消融（无采样 / class_weight / Focal Loss） |
| `learning_curve.py` | 学习曲线（1257 点为无泄漏 bootstrap 口径） |
| `train_sound_model.py` / `train_roberta_quick.py` | 早期版本 / RoBERTa 快速探测（保留用于复现） |
| `prep_quick_split.py` | 生成 RoBERTa 探测用小训练集 |

## 四、评估与验证

| 文件 | 产出 |
|---|---|
| `test_model.py` | 验证集指标、阈值扫描、混淆矩阵 |
| `baseline_cv.py` | 三基线（dummy / LR / SVM）交叉验证 |
| `svm_ttest.py` | Welch t 检验（p=0.000932） |
| `pr_curve.py` / `finalize_curve.py` | PR 曲线与图件收尾 |
| `distilbert_vs_llm.py` | 教师一致性（83.7%，仅说明蒸馏可行性） |
| `val_pred_dump.py` | val_v2 全量推理快照 → `val_preds_dump.csv`（C1/C3/C4 公共输入） |
| `calibration_eval.py` / `length_bucket_eval.py` / `edge_case_benchmark.py` | 校准 ECE / tokenizer 长度分桶 / 边界探针 |
| `prep_err_taxonomy.py` + `taxonomy_agg.py` | 错误分类学（FP/FN 抽取 + 类别聚合 + 抽查抽样） |
| `throughput_bench.py` | GPU/CPU 吞吐实测 |
| `year_split_eval.py` / `trend_over_time.py` | 年份分桶验证 / 月度趋势图 |
| `prep_llm_eval.py` + `llm_eval_metrics.py` + `llm_qwen_metrics.py` | LLM 对照子集准备与两侧指标计算 |
| `results_summary.py` | 从训练日志汇总冻结数字（兼容 UTF-16 日志） |

## 五、审计、打包与文档

| 文件 | 用途 |
|---|---|
| `check_doc_numbers.py` | 数字审计（143 项）+ 官方模板九章格式对照 → `number_audit.md` |
| `audit_ppt.py` | 抽取 PPT 文本（`ppt_text_dump.md`）并核对页数/数字 |
| `deploy_check.py` / `batch_check.py` | 在线 Demo 单条 / 批量自动验收（需公网 URL） |
| `md_to_pdf.py` / `md_to_docx.py` / `verify_docx.py` | 主文档 Markdown → PDF（内嵌宋体/黑体）/ Word / 完整性校验 |
| `pack_final.py` / `hashes.py` | 提交包打包与四项自检 / 打印校验值 |
| `build_submission.py` | 生成三个 zip（Demo / 其他材料 / 复赛作品容器） |
| `make_ai_handoff.py` | 生成本导览包（`AI_HANDOFF/manifest.json` 与文件地图） |
| `make_video_assets.py` | 生成 8 张 1920×1080 视频素材图（`视频素材/`） |
| `extract_template.py` | 抽取官方模板 docx 的章节结构（格式对照用） |
| `启动Demo.bat` / `打包提交包.bat` | 双击式入口（纯英文提示，避免 cmd 码页问题） |

## 六、运行注意事项（踩过的坑）

1. **系统代理**：本机开了系统代理（127.0.0.1:7890）时，gradio 启动自检会 502 退出 → Demo 内已内置 `NO_PROXY` 绕过；其他脚本若访问 localhost 也需注意。
2. **PowerShell 假退出码**：Python 写 stderr（transformers 进度条）时 pwsh 会报 `[exit code: 1]`，实际进程退出码为 0；判断成败要看输出而非该标记。
3. **编码**：`.bat` 必须纯 ASCII（cmd 按 GBK 解析，中文会读歪）；Python 脚本统一 `PYTHONIOENCODING=utf-8`。
4. **数据读取**：评论文本含 `n/a`、`None` 等，读 CSV 时必须 `keep_default_na=False`。
5. **GPU 串行**：8GB 显存，训练/推理脚本不要并行跑。
6. **沙箱网络**：Hugging Face 官方源不可达（401）→ 基座走 ModelScope 镜像；GitHub 推送需 `-c http.sslBackend=openssl`。
