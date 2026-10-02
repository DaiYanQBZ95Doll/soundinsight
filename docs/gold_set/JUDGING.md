# 人工金标 · 判定协议（极简输入版）

> **你只需要回数字。** 每条一个数字：**`1` = 是｜`0` = 不是｜`2` = 无法判断**（产品是不是耳机／说不准）
> 其它符号：`.` 或 `-` = 跳过（留空，不计入）；`#` 起头是注释。

---

## 一、三个选项（固定，不可扩展）

| 数字 | 含义 | 写入什么 |
|---|---|---|
| **1** | **是**——该评论在描述/提及**耳机或耳塞的声音表现**（低音／清晰度／杂音／音量／高音） | CSV 填 `1` |
| **0** | **不是**——不涉及耳机声音表现（别的产品、别的方面、纯好评等） | CSV 填 `0` |
| **2** | **无法判断**——产品是否为耳机不确定，或文本太短/太模糊 | CSV 填 `?`（单列统计，不计入一致率分母） |

> 判据仍以**你自己**的读法为准；翻译与解析只是为了让你读得快。

## 一·五、**首选回法：绝对编号 G###**（三方一致，不会错位）

`G001` = `assisted_worksheet.csv` 的**第 1 行**，`G300` = 第 300 行（与批次窗口无关）。
例：`G001=1 G002=0 G003=2` 或区间 `G001..G025 = 1,0,2,1,…`。

**为什么首选它**（红队 Qwen 实测指出）：三方批次大小不同（Kimi 10／DSH 可调／Qwen 25），若用裸数字串群发，从第二批起会按各自窗口切分而**错位且不报错**；G 编号是绝对坐标，天然免疫。

## 二、四种回复格式（任选，越短越好）

| 格式 | 例子 | 说明 |
|---|---|---|
| **① 按顺序一串** | `1 0 2 1 1 0 0 1` | 按"**本席位最近一次 --batch**"的顺序对应；⚠️ 跨方群发时**不要用**（批次大小不同会错位） |
| ② 带编号（**推荐**） | `G001=1 G002=0` 或 `S1-001=1` | 绝对对应，适合跳着判；`2` 亦接受（映射为 `?`） |
| ③ 只报例外 | `除 S1-007=0 外，本批其余全 1` | 适合绝大多数同类的情形 |
| ④ 区间 | `S1-001..S1-020 = 1,0,2,...` | 批量粘贴用 |

## 二·五、答题卡流程（**决策方选定的方式**）

**你手填一张答题卡 → 群发一句「答题卡已交」→ 三方各自接收。**

| 项 | 说明 |
|---|---|
| 我方答题卡 | **`docs/gold_set/answer_sheet.md`**（300 条，30 批×10；格式 `S2-037:_`，把 `_` 换成 `1`/`0`/`2`） |
| 其它可填的卡 | `answer_sheet_kimi.md`（Kimi 侧，同款格式）、`answer_sheet_qwen.md`（Qwen 侧）；**填哪张都能被接收** |
| 填写者可写 | 只有**决策方**；**三方只读不写**答题卡 |
| 接收命令（执行方） | `python apply_human_rulings.py --from-answer-sheet --author dsh`（自动找卡；落库到共享 CSV + 本席位） |
| 部分填写 | 完全支持：填多少收多少，剩余 `_` 静默跳过 |
| 接收后 | 执行方回报条数与进度；`--reconcile` 做三方对账 |

> 已实测：我方格式与 Kimi 格式**各 6 条均正确解析**，未填 `_` 不计入、表头文字不报错。

## 三、工作循环（每轮约 2–4 分钟）

1. 我说「**下一批：S1-001 … S1-020**」并给出这 20 条的翻译与解析；
2. 你回 20 个数字（格式①即可）；
3. 我把它写入 **`docs/gold_set/human_rulings_dsh.md`** 与 `assisted_worksheet.csv`，回报进度与剩余；
4. 重复。**全程可随时中断**（已判的不会丢）。

## 三·五、机制保障（2026-10-01 由红队 Qwen 指出后加固）

| 风险 | 旧版行为 | 现机制 |
|---|---|---|
| 他方跑脚本会写共享 CSV | `save_rows()` **无条件**执行，`--author` 不影响它 | **闸门**：默认仅 `--author dsh` 写 CSV；他人须显式 `--write-csv`（不加则只写自己席位） |
| 批次状态互相覆盖 | 共用 `v2/gold_set_batch.json` | **按席位隔离**：`v2/gold_set_batch_<author>.json` |
| 裸数字串错位 | 依赖"当前批次"，三方批次大小不同 | **首选 G 绝对编号**（见 §一·五） |
| 缺席时对账静默降级 | `reconcile()` 读了共享 CSV 却从未使用（死代码） | 共享 CSV **作为一方参与对账**；缺失席位**显式列出** |

## 四、三方各一份（并发规则）

决策方会**同时群发**给三方，故：

| 文件 | 归属 | 规则 |
|---|---|---|
| `docs/gold_set/human_rulings_dsh.md` | 执行方（DSH） | 我写；不碰别人的 |
| `docs/gold_set/human_rulings_kimi.md` | 红队 Kimi | 我不改 |
| `docs/gold_set/human_rulings_qwen.md` | 红队 Qwen | 我不改 |

三份是**同一批判定的三次转写**（先后可能不同）。做完后我会跑
`python apply_human_rulings.py --reconcile` 做**三份对账**：任何不一致都说明**转写错误**，
需要你确认以哪份为准——这本身是一道免费的质检。

## 五、落库与出结论

```
python apply_human_rulings.py --batch 20                 # 打印下一批（含翻译解析）
python apply_human_rulings.py --text "1 0 2 1 1"         # 按顺序写入（当前批次）
python apply_human_rulings.py --text "S1-007=0"          # 带编号写入
python apply_human_rulings.py --progress                 # 查看进度
python apply_human_rulings.py --reconcile                # 三方对账
python score_gold_set.py --sheet assisted                # 出 κ 与一致率（判完足够多之后）
```

---

## 六、接收通道（执行方按卡的**性质**分流，避免互相覆盖）

| 你填的卡 | 性质 | 执行方接收命令 | 落到哪里 |
|---|---|---|---|
| `answer_sheet.md`（我方主卡，S1/S2/S3） | **第一遍判定**（真值） | `--from-answer-sheet docs/gold_set/answer_sheet.md --author dsh` | 共享表 `assisted_worksheet.csv` + `human_rulings_dsh.md` |
| `answer_sheet_s1_add100.md`（S4 追加 100） | **新样本** | `--from-answer-sheet docs/gold_set/answer_sheet_s1_add100.md --author dsh --csv docs/gold_set/s1_add100.csv` | `s1_add100.csv` + 同席位文件（S4 并入统计） |
| `answer_sheet_decision.md`（Kimi 卡，同一批 300） | **第二遍判定**（稳定性检验） | `--from-answer-sheet docs/gold_set/answer_sheet_decision.md --author dsh2` | `human_rulings_dsh2.md`（**不写共享表**） |
| `bias_probe_sheet.md`（40 条只看原文） | 锚定探针 | `python score_bias_probe.py` | 只出报告，不落判定库 |

**比较工具**：`python compare_passes.py --a csv --b <另一来源>` → 一致率、κ、分歧清单、方向性。
- 我方卡 vs Kimi 卡 = **你的判定稳定性**（同一批题、不同呈现）；
- 主卡 vs 探针卡 = **执行方材料的锚定影响**（Kimi 主导分析）。
