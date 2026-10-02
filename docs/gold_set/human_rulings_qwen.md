# 人工金标判定（qwen）

> 判定由**决策方**逐条作出；本文件是转写记录（一人一文件，互不覆盖）。
> 值：`1`=是（涉及耳机声音表现）｜`0`=不是｜`?`=无法判断
>
> **转写方**：红队 Qwen｜**转写工具**：`金标判定/record_judgements.py`（仓库外工作目录）
> **输入档位**：决策方以 `0/1/2` 三档给出，本文件按 `CELL2NAME` 映射为 `0/1/?`
> **编号顺序**：与 `assisted_worksheet.csv` 原始行序一致（便于三方对账）
> **本席位不写**：`assisted_worksheet.csv`、`review_notes.md`、`human_rulings_dsh.md`、
> `human_rulings_kimi.md`、`v2/gold_set_batch.json`、`agreement_report.md`、
> `v2/gold_set_agreement.json`
>
> **当前状态**：等待第一批判定（0/300）。判定到达后由本席位追加表格行。

| 编号 | 判定 | 含义 |
|---|---|---|
