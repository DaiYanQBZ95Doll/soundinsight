# 公开仓库卫生扫描（密钥 / 隐私 / 废弃 claim）

- 扫描范围：git 跟踪文件 272 个（文本与数据类逐行扫；二进制仅按文件名判断）
- 生成方式：`python scan_repo_hygiene.py`（可随时重跑）

## 一、密钥与凭据
- [PASS] 跟踪文件内未发现密钥 / 令牌 / 明文口令（扫描器自身与扫描报告已排除，避免自指命中）
- 未指定 `DSH_SECRET_NEEDLES`（需要复查某个具体令牌时再传，以免把检测针写进仓库）
- [PASS] git 历史文本文件中未发现密钥模式
- [记录] 历史提交 57994c80 中出现过某个 GitCode 令牌的 **8 位前缀**（当时作为扫描器的检测针写入脚本，现已移出，改为环境变量传入）。完整令牌从未写入任何文件；建议在 GitCode 设置中轮换该令牌，轮换后此历史残留即失去意义。

## 二、隐私信息
- `competition_v3.txt`：4 处
  - 行 9｜中国大陆手机号｜`19195907942`
  - 行 11｜邮箱地址｜`2799920054@qq.com`
  - 行 17｜中国大陆手机号｜`19195907942`
  - 行 17｜邮箱地址｜`2799920054@qq.com`
- `competition_v4.md`：4 处
  - 行 9｜中国大陆手机号｜`19195907942`
  - 行 11｜邮箱地址｜`2799920054@qq.com`
  - 行 17｜中国大陆手机号｜`19195907942`
  - 行 17｜邮箱地址｜`2799920054@qq.com`
- `docs/D13_seal_declaration.md`：2 处
  - 行 25｜中国大陆手机号｜`19195907942`
  - 行 25｜邮箱地址｜`2799920054@qq.com`
- `docs/project_full_record.md`：2 处
  - 行 5｜中国大陆手机号｜`19195907942`
  - 行 5｜邮箱地址｜`2799920054@qq.com`
- `upload_models.py`：1 处
  - 行 81｜邮箱地址｜`soundinsight@users.noreply.github.com`

## 三、废弃 claim（已被修正的旧数字 / 旧表述）
- 命中合计 29 处：其中 **0 处需确认**、29 处属诚信记录 / 历史说明（有意保留）

### 3.1 需确认（不在诚信记录文件内，且无历史标记）
- 无

### 3.2 属历史说明 / 诚信记录（有意保留，不修改）
- `AI_HANDOFF/03_metrics_and_caveats.md`：2 处（行 47, 47）
- `AI_HANDOFF/06_pending_and_redlines.md`：1 处（行 44）
- `PROGRESS_SYNC.md`：1 处（行 68）
- `audit_ppt.py`：2 处（行 65, 69）
- `check_doc_numbers.py`：2 处（行 34, 63）
- `docs/legacy_materials_notice.md`：6 处（行 52, 53, 56, 60, 60, 60）
- `docs/process_review_d10.md`：2 处（行 60, 60）
- `docs/project_full_record.md`：3 处（行 174, 174, 225）
- `docs/work_summary_d7.md`：2 处（行 13, 55）
- `ppt_speed_fix.py`：8 处（行 2, 3, 17, 20, 21, 22, 23, 24）

## 四、生成物一致性（manifest.json 记录值 vs 实际文件）
- [PASS] manifest.json 记录的大小与哈希与工作区一致

## 五、结论与建议
- 密钥：未发现（高危 0 处；历史提交命中 0 处）
- 隐私：13 处，见第二节；竞赛联系信息为模板要求填写，公开仓库如需脱敏见 `docs/legacy_materials_notice.md` §四
- 废弃 claim：当前文档需确认 0 处；历史材料的口径指引见 `docs/legacy_materials_notice.md`
- 生成物一致性：一致
