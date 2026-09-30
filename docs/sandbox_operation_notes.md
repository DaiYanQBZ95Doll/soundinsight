# 无批准窗口下的作业说明（沙箱 workspace-write）

> 起因：决策方 2026-09-30 22:5x 告知"约一个半小时后将无法批准行动"，并要求安排**不需要批准**的工作。
> 本文件记录实测边界与应对，确保批准停止后仍能推进到可交付状态。

---

## 一、实测边界（workspace-write，不升级）

| 操作 | 是否可用 | 实测依据 |
|---|---|---|
| 读/写工作区内文件（含新建、覆盖、删除） | ✅ 可用 | 本轮全部编辑与脚本执行 |
| `python check_doc_numbers.py` | ✅ 可用 | 审计 0 FAIL / 186 PASS |
| `python scan_repo_hygiene.py` | ✅ 可用 | 输出 `docs/repo_hygiene_scan.md` |
| `python make_ai_handoff.py` | ✅ 可用 | 刷新 `AI_HANDOFF/manifest.json` |
| `python test_audit_checks.py` | ✅ 可用（**已修**） | 原用 `tempfile.TemporaryDirectory()` → 其 `chmod` 被沙箱拒绝；改为工作区内 `makedirs/rmtree` 后 15/15 通过 |
| 本地 `git add/commit` | ✅ 可用 | 本轮已产生多个本地提交 |
| **`git push`（GitCode/GitHub）** | ❌ **不可用** | `schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS` —— 沙箱禁止访问 Windows 凭据库 |
| GPU 训练/推理 | ✅ 可用 | 5 折 CV、W1/W2/W5 评估均在沙箱内完成 |
| 访问工作区之外的路径 | ❌ 不可用 | 需批准 |

## 二、推送的替代路径（择一）

1. **决策方手动执行**（最简单）：
   ```
   cd C:\deepseek-harness-master\soundinsight
   git push gitcode main && git push origin main
   ```
   当前待推送提交数见 `git rev-list --count gitcode/main..HEAD`（本轮结束时为 3 个）。
2. **批准恢复后由执行方推送**：一次性执行 `git push gitcode main && git push origin main`。
3. **不推送也不影响交付**：本地仓库是事实源；决赛包由本地构建，与远端同步与否无关。

> 注意：远端最后一次成功同步是 `e9d92ba`（第 9 轮）；此后为本地提交。恢复推送前，
> 远端与本地存在差异属**预期**，不是仓库损坏。

## 三、批准停止后我仍能完成的工作（按优先级）

1. **M0 换代**：按 `v2/m0_switch_report.json` 的 81 行清单，把 v1 数字标注为 `[v1]` 并补 v2 数字（纯文本编辑）；
2. **M1 主文档**：按冻结清单 §八 映射表填充决赛模板九节（含局限章节、勘误节、置信度三档表）；
3. **M1 附属**：在线链接表、附件命名规范、注意事项（照抄 + 更新命名）；
4. **材料齐备性自检**：审计（含决赛模板合规检查，M1 生成后由 SKIP 转 PASS）、卫生、清单三件套；
5. **W5 收尾**：5 折 CV 结果落盘（后台运行中）+ 冻结清单勾选；
6. **不可做**：推送、部署重建与线上复测（M3）、视频重录（M2）——后两项本属**人侧节点**，需决策方本人操作。

## 四、如果批准窗口内还有余量，最值得批准的两件事

1. 一次远端推送（备份 3 个本地提交）；
2. 设定 `DEEPSEEK_API_KEY`（若愿意用方案 A）——这是 **W4 复核段**唯一的阻塞点。
