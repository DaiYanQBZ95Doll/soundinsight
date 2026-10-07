# Demo 冷启动实测（P0④，评委首次运行路径）

> 与 `verify_demo_end_to_end.py` 的区别：那个把权重**复制**进去（跳过下载）；本测试**不复制**，
> 真跑 `download_models.py`。日期 2026-10-03。

| 步骤 | 结果 | 耗时 |
|---|---|---|
| ① 解包决赛包→Demo.zip | ✓（22 项，**自带权重 False**） | — |
| ② `download_models.py`（约 530MB） | **成功 ✓** | 231.1s |
| ③ `soundinsight_agent.py --csv sample_reviews_100.csv` | **成功 ✓** | 12.2s |

- 报告节数：**7**｜未判定（不含音频词汇）计数：**80**
- 总判定：**全通过 ✓**
- 下载后已清理权重（释放 536 MB），工作目录 `_coldstart_test/` 保留其余文件供复查。

## 结论

冷启动路径**已实测可用**——评委按 README 首次运行可在约 4 分钟内完成（含 530MB 下载）（详见 `v2/coldstart_report.json` 的逐步输出）。
