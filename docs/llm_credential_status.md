# LLM 调用配置与凭据现状（回答"我能读到什么 key"）

> 生成：2026-09-30 22:5x（执行方）｜触发：决策方要求核查 LLM 调用配置
> **结论先行：当前读不到任何 DeepSeek key**；仓库侧也从未有 LLM 调用代码。W4 的复核段因此仍阻塞，
> 但**候选段已完成**（见 §四）。

---

## 一、我"期望"的名字（按来源分两类）

### 1) 我自己写的 W4 脚本（`v2_w4_mine.py`）探测顺序
| 顺序 | 环境变量名 | 通道 | 备注 |
|---|---|---|---|
| 1 | `DEEPSEEK_API_KEY` | DeepSeek 官方 API（`https://api.deepseek.com/v1`，`deepseek-chat`） | **复赛标注所用的通道** |
| 2 | `QWEN_TOKEN_PLAN_API_KEY` | 阿里云百炼 Token Plan（`…/compatible-mode/v1`，`qwen3.7-plus`） | 需额外设 `DSH_ALLOW_TOKEN_PLAN_FOR_W4=1` 才允许用于 W4 |
| 3 | `TOKEN_PLAN_API_KEY` | 同上 | 同上 |

> 渠道守则已内置：Token Plan 凭证按既定规则**仅用于收尾存证**；只探测到它时脚本会**拒绝运行并提示**，
> 除非显式设置放行变量。这样避免无意中违反你定的规则。

### 2) DSH 自身期望的名字（来自 `~/.dsh/profiles/desktop/cordis.patch.yml`）
| Provider | 期望的环境变量 |
|---|---|
| `qwen-token-plan` | **`QWEN_TOKEN_PLAN_API_KEY`** |
| `moonshotai-cn` | `MOONSHOTAI_CN_API_KEY` |
| `moonshotai` | `MOONSHOTAI_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `deepseek-account`（我当前所用的模型通道 `deepseek-flash`） | **不通过环境变量**，由 DSH 账户体系管理 |

---

## 二、当前环境里"实际存在"的相关变量（实测）

```
DSH_HOME           已设置
DSH_PROFILE        已设置
DSH_PROFILE_DIR    已设置
DSH_SESSION_ID     已设置
DSH_SHELL          已设置
DSH_WEB_URL        已设置
```

**没有任何** LLM/API 相关变量被设置（`DEEPSEEK_API_KEY`、`QWEN_TOKEN_PLAN_API_KEY`、
`OPENAI_API_KEY`、`MOONSHOTAI_*`、`DASHSCOPE_API_KEY` 等**全部未设置**）；
仓库内也没有 `.env`／凭据文件。

**因此：我现在读不到 DeepSeek 的 key。** 我能用的模型通道是 DSH 自身的 `deepseek-account`
（harness 内部凭据，不暴露给子进程），**无法被我自己的 Python 脚本调用**。

---

## 三、要让 W4 跑起来，需要你做的一件事（任选其一）

| 方案 | 你做的动作 | 代价/说明 |
|---|---|---|
| **A（推荐）** | 设 `DEEPSEEK_API_KEY=<你的 DeepSeek key>`（用户或系统环境变量） | 与复赛标注同通道；脚本自动优先使用它 |
| **B** | 设 `QWEN_TOKEN_PLAN_API_KEY=<Token Plan key>` **并** 设 `DSH_ALLOW_TOKEN_PLAN_FOR_W4=1` | 用百炼通道（该 key 无法轮换，且原规则限定收尾用；放行变量即为你的显式授权） |

设置后无需再确认，直接执行：
```
python v2_w4_mine.py --review --limit 300     # 复核分层样本（支持断点续跑）
```

---

## 四、W4 已经完成的部分（不需要凭据）

- **候选提取已完成**：4–5★ 评论中"提到音质但未出现正面极性强表述"的候选共 **12,744 条**
  （5★ 9,185／4★ 3,559）。
- **W4b 上界规则已触发**：实测 12,744 vs 预期 ≈300 → **42 倍**，按预注册规则转为
  **分层抽样复核**：已按（星级 × 主关键词）分 39 组、每组 ≈10 条，抽出 **293 条**样本
  （`v2/w4_sample.csv`），**未复核比例 97.70%**（`v2/w4_strata.json` 记录）。
- 这说明一个**可对外的结论**：四五星的"音质相关提及"量级极大（1.27 万条），
  要在时间盒内用 LLM 全量复核不可行；**抽样复核 + 外推（含置信区间）**才是可行路线。

---

## 五、我接下来**不需要批准**就能推进的工作（按你 22:5x 的提示安排）

1. W4 之外的 W 线已全部收尾（W1–W3、W5–W7、W14–W17），W5 的 5 折 CV 仍在后台跑；
2. **M0 换代**：按 `v2/m0_switch_report.json` 的 81 行清单逐项把 v1 数字标注为 `[v1]` 并补 v2 数字；
3. **M1 主文档**：按冻结清单 §八 的映射表填充决赛模板九节（含局限章节、勘误节、置信度三档表）；
4. 门槛三件套（审计／卫生／清单）与两远端同步——**全部在 workspace-write 权限内，不需要批准**。

---

## 状态更新（2026-10-01）：**已解除**

决策方提供 DeepSeek 凭证后，两处测量均已执行完成（W4 复核 293 条 + 关键词之外 300 条，共 599 次判定，约 0.02 美元）：

- 四五星池**复核已完成**（凭证到位后）：分层样本 293 条 → LLM 判正 31 条，其中**明确耳机音质 3 条、无法判断 6 条、跨品类 22 条** → 分层估计 **≈20 条（严格）／≈95 条（宽松）**；关键词之外抽样 300 条 → **4 条（1.33%）→ ≈1,161 条**。两组补完后语料总量 **2,461–2,826 条**，现有标签集占 **52.0%–45.3%**。
- 首版 W4 复核曾因**取样错误**（误跑候选表前 300 条）得 456 条，**已作废留档**；分类主体为**执行方 AI，未经人工复核**。
- 明细：`docs/scoped_findings.md`、`v2/scoped_estimates.json`。
