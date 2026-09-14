# -*- coding: utf-8 -*-
# scan_repo_hygiene.py —— 公开仓库卫生扫描：密钥 / 隐私 / 废弃 claim
#
# 用途：仓库已公开（GitHub + GitCode），且包含初赛等历史材料。本脚本回答三个问题：
#   1. 有没有把密钥、令牌、凭据写进文件（含 git 历史里出现过的）；
#   2. 有没有个人隐私信息（手机号 / 邮箱 / 本机绝对路径 / 身份证号）；
#   3. 历史材料里有没有"废弃 claim"（已被修正的旧数字与旧表述），
#      并区分"需要修正"与"作为诚信记录保留"两类。
#
# 用法：python scan_repo_hygiene.py        报告写入 docs/repo_hygiene_scan.md
# 退出码：0 = 无高危命中；1 = 有高危命中（密钥 / 明文凭据）
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_MD = os.path.join(HERE, "docs", "repo_hygiene_scan.md")

TEXT_EXT = {".md", ".txt", ".py", ".bat", ".sh", ".json", ".yml", ".yaml",
            ".srt", ".html", ".css", ".js", ".cfg", ".ini", ".toml"}
DATA_EXT = {".csv", ".jsonl", ".xlsx", ".xls"}

# ---------------------------------------------------------------- 模式定义
# 密钥 / 凭据：高危，命中即需处理（f-string 占位符 {args.token} 不算硬编码）
SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9]{16,}", "OpenAI 风格 key"),
    (r"gh[pousr]_[A-Za-z0-9]{20,}", "GitHub token"),
    (r"hf_[A-Za-z0-9]{20,}", "HuggingFace token"),
    (r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}", "Bearer 令牌"),
    (r"https://[^/\s:@]+:(?!\{)[^/\s@]{8,}@", "URL 内嵌用户名:口令（非占位符）"),
    (r"(?i)(api[_-]?key|apikey|access[_-]?token|secret[_-]?key|client[_-]?secret)"
     r"\s*[:=]\s*[\"'][A-Za-z0-9_\-]{12,}[\"']", "key/token 赋值字面量"),
    (r"(?i)(password|passwd|pwd)\s*[:=]\s*[\"'][^\"'\s]{6,}[\"']", "口令赋值字面量"),
]

# 特定令牌复查：不把任何令牌字样写进仓库（写了就等于把检测针本身公开，
# 且会让扫描器扫到自己）。需要复查某个具体令牌时用环境变量传入：
#   $env:DSH_SECRET_NEEDLES="abc123,def456"; python scan_repo_hygiene.py
EXTRA_NEEDLES = [s.strip() for s in os.environ.get("DSH_SECRET_NEEDLES", "").split(",")
                 if s.strip()]
SECRET_PATTERNS += [(re.escape(n), f"环境变量指定的令牌字样（{n[:4]}…）")
                    for n in EXTRA_NEEDLES]

# 自指文件：扫描器自身与扫描报告会引用命中项（令牌前缀、手机号片段等），
# 排除它们，否则报告永远把自己算成"高危命中"
SELF_EXEMPT = {"scan_repo_hygiene.py", "docs/repo_hygiene_scan.md"}

# 历史遗留说明（固定在报告里输出，避免"改了检测方式就查不到"的假清白）
HISTORY_NOTE = ("历史提交 57994c80 中出现过某个 GitCode 令牌的 **8 位前缀**"
                "（当时作为扫描器的检测针写入脚本，现已移出，改为环境变量传入）。"
                "完整令牌从未写入任何文件；建议在 GitCode 设置中轮换该令牌，"
                "轮换后此历史残留即失去意义。")

# 隐私：需人工判断（可能是有意公开的竞赛联系信息）
# 手机/身份证号要求两侧不是字母数字（避免命中 sha256 十六进制串里的数字段），
# 且跳过 hash 行与小数（避免命中 0.018331445050983636 这类浮点值）。
HASH_LINE = r"sha256|sha1|md5|digest|hash|checksum"
PII_PATTERNS = [
    (r"(?<![0-9A-Za-z])1[3-9]\d{9}(?![0-9A-Za-z])", "中国大陆手机号", HASH_LINE),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "邮箱地址", None),
    (r"(?<![\w.])\d{17}[\dXx](?![\w])", "身份证号样式", HASH_LINE),
    # 要求是真实路径（至少两级、且不是省略号占位），避免命中"文档里描述该模式"的句子
    (r"[Cc]:[\\/]Users[\\/][^\\/\s\"'…]{2,}", "本机用户绝对路径", None),
    # 要求是"字段名 + 冒号 + 值"的形状，避免命中"扫描类别"这类元描述
    (r"(?i)(真实姓名|身份证|家庭住址|银行卡)\s*[:：]\s*\S", "隐私字段字样", None),
]

# 废弃 claim：已被修正的旧数字 / 旧表述
# 每条 =（正则, 说明, 允许上下文, 必需上下文）；允许上下文命中即跳过，
# 必需上下文存在时才算命中（用于排除同名但不同义的词，如"读本文件约 2 分钟"）。
LEGACY_PATTERNS = [
    (r"99\.6", "旧提速口径（2 分钟/99.6%，已废弃）",
     r"概率|预测|\[99\.6|负面|正面|PASS|FAIL", r"提升|效率|提速|↓"),
    (r"2\s*分钟|2min", "旧耗时口径（应为 GPU 约 2 秒）",
     r"约\s*2\s*分钟|准备|读本文件|阅读|创建|新建|命名", r"压缩|8\s*小时|8h|耗时|时间从"),
    (r"GPT-4", "旧成本对照（未实测，已废弃）", r"[?？]|提问|对比", r"\$|0\.01|成本|单价"),
    (r"白皮书", "无出处表述（已废弃）", r"清理|删除|无出处|已废弃|不再", None),
    (r"\b98%", "旧无出处表述", r"清理|删除|无出处|已废弃|不再", None),
    (r"1297", "错误正例数（应为 1257/1280/1288 口径）",
     r"未出现|FAIL|PASS|应为|不得|审计", None),
    (r"83\.7", "教师一致性数字出现在非方法语境",
     r"不得|仅说明|仅用于|方法|附录|蒸馏|审计|FAIL|PASS|未出现|降级", None),
    (r"107[,，]?294", "旧 Demo.zip 体积（现为 109,662 B）",
     r"旧|历史|快照|曾|依次|改为", None),
    (r"105[,，]?784", "旧骨架包体积", r"旧|历史|快照|曾|依次|改为", None),
    (r"208[,，]?471", "旧主文档 PDF 体积（现为 215,103 B）",
     r"旧|历史|快照|曾|依次|改为", None),
    (r"44[,，]?432[,，]?(904|244|240|861)", "旧提交包体积（容器类，随重打变化）",
     r"旧|历史|快照|曾|依次|改为", None),
    (r"feedback_template", "已删除的未完成环节文件",
     r"已删除|清理|不再", None),
    (r"内网", "曾触发平台敏感词回滚的措辞", r"回滚|敏感词|已改|避免", None),
    (r"qwen3\.7-plus.{0,20}标注|标注.{0,20}qwen3\.7-plus", "废弃的 qwen 标注复核 claim",
     r"未参与|不用于|已废弃|曾|改为|违禁", None),
]

# 生成物：内容随打包变化，不参与"废弃 claim"判定（应重跑生成脚本而非改文件）
GENERATED_FILES = {
    "AI_HANDOFF/manifest.json", "number_audit.md", "ppt_text_dump.md",
    "hashes.txt", "docs/repo_hygiene_scan.md",
}

# 这些文件本身就是"诚信记录 / 校验脚本 / 修复脚本 / 过程日志"，
# 命中属于有意保留的历史说明或负向护栏（例如 `if "1297" in joined: FAIL`）
RECORD_FILES = {
    "AI_HANDOFF/06_pending_and_redlines.md", "docs/D13_seal_declaration.md",
    "number_audit.md", "check_doc_numbers.py", "scan_repo_hygiene.py",
    "docs/repo_hygiene_scan.md", "docs/project_full_record.md",
    "PROGRESS_SYNC.md", "docs/file_inventory.md", "docs/process_review_d10.md",
    "QWEN_HANDOFF.md", "ppt_text_dump.md", "docs/legacy_materials_notice.md",
    "audit_ppt.py", "ppt_speed_fix.py", "fix_ppt_threshold.py",
    "throughput_bench.py", "throughput_eval.md", "docs/work_summary_d7.md",
}
HISTORY_MARKERS = ("已废弃", "已修正", "曾出现", "曾出现的问题", "不再", "违禁",
                   "旧版", "修正前", "历史", "旧口径", "废弃", "回滚", "已删除",
                   "取代", "作废", "旧字符口径", "旧\"", "清理", "已改", "替换",
                   "修复", "快照", "依次", "旧表述", "修正", "清除", "硬伤")


def git(args: list[str]) -> str:
    p = subprocess.run(["git"] + args, cwd=HERE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.stdout or ""


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=HERE,
                         capture_output=True)
    raw = out.stdout.decode("utf-8", errors="replace")
    return [f for f in raw.split("\0") if f]


def scan_file(path: str, patterns, hits: list, category: str) -> None:
    """patterns 支持 (regex, desc) 与 (regex, desc, allow, require) 两种形状。"""
    try:
        with open(os.path.join(HERE, path), encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return
    for i, line in enumerate(lines, 1):
        for entry in patterns:
            pat, desc = entry[0], entry[1]
            allow = entry[2] if len(entry) > 2 else None
            require = entry[3] if len(entry) > 3 else None
            if allow and re.search(allow, line):
                continue
            if require and not re.search(require, line):
                continue
            m = re.search(pat, line)
            if m:
                hits.append({
                    "file": path, "line": i, "desc": desc, "match": m.group(0),
                    "snippet": line.strip()[:110], "category": category,
                })


def scan_history(patterns) -> list[dict]:
    """扫描 git 历史中所有文本文件的密钥模式（忽略已删除文件的历史）。"""
    commits = [c for c in git(["rev-list", "--all"]).split() if c]
    hits, seen = [], set()
    for c in commits[:400]:
        for pat, desc in patterns:
            out = git(["grep", "-I", "-n", "-E", "-m", "3", pat, c, "--"])
            for line in out.splitlines():
                if ":" not in line:
                    continue
                key = (pat, line[:160])
                if key in seen:
                    continue
                seen.add(key)
                hits.append({"commit": c[:8], "desc": desc, "line": line.strip()[:160]})
    return hits


def check_manifest() -> list[dict]:
    """核对 AI_HANDOFF/manifest.json 记录的大小/哈希与工作区实际文件。

    该文件由 make_ai_handoff.py 生成；打包或改文件后忘记重跑，记录值就会过期
    （曾发生：提交包重打后 size_bytes 仍是旧体积）。
    """
    import hashlib
    import json
    p = os.path.join(HERE, "AI_HANDOFF", "manifest.json")
    if not os.path.isfile(p):
        return []
    try:
        data = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = data.get("entries", data.get("files", data if isinstance(data, list) else []))
    if not entries:
        return [{"path": "(manifest.json 无法解析出条目列表)", "field": "structure",
                 "recorded": list(data.keys())[:6] if isinstance(data, dict) else "?",
                 "actual": "-"}]
    stale = []
    for e in entries:
        if not isinstance(e, dict) or "path" not in e:
            continue
        if e["path"] in GENERATED_FILES or e["path"] == "AI_HANDOFF/manifest.json":
            continue  # 生成物：每次重跑都会变，不参与一致性判定
        fp = os.path.join(HERE, e["path"])
        if not os.path.isfile(fp):
            continue  # 不入库的大文件会被标注为缺失，属预期
        size = os.path.getsize(fp)
        if e.get("size_bytes") and e["size_bytes"] != size:
            stale.append({"path": e["path"], "field": "size_bytes",
                          "recorded": e["size_bytes"], "actual": size})
        # 大文件（视频/权重/包）不记哈希，manifest 里留空，不能当成过期
        if e.get("sha256_16"):
            h = hashlib.sha256(open(fp, "rb").read()).hexdigest()
            if e["sha256_16"] != h:
                stale.append({"path": e["path"], "field": "sha256_16",
                              "recorded": e["sha256_16"][:16], "actual": h[:16]})
    return stale


def main() -> int:
    files = tracked_files()
    if not files:
        print("未取得文件清单（是否在 git 仓库内运行？）")
        return 2

    secret_hits, pii_hits, legacy_hits = [], [], []
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext not in TEXT_EXT and ext not in DATA_EXT:
            continue
        if f in SELF_EXEMPT:
            continue
        is_data = ext in DATA_EXT
        scan_file(f, SECRET_PATTERNS, secret_hits, "secret")
        if is_data:  # 数据集正文里的 "password" 等词不算隐私或 claim
            continue
        scan_file(f, PII_PATTERNS, pii_hits, "pii")
        if f not in GENERATED_FILES:
            scan_file(f, LEGACY_PATTERNS, legacy_hits, "legacy")

    hist_hits = scan_history(SECRET_PATTERNS)
    manifest_stale = check_manifest()

    # 分类：需修正 vs 诚信记录保留
    need_fix, documented = [], []
    for h in legacy_hits:
        keep = (h["file"] in RECORD_FILES
                or any(mk in h["snippet"] for mk in HISTORY_MARKERS))
        (documented if keep else need_fix).append(h)

    out = ["# 公开仓库卫生扫描（密钥 / 隐私 / 废弃 claim）", ""]
    out.append(f"- 扫描范围：git 跟踪文件 {len(files)} 个（文本与数据类逐行扫；"
               f"二进制仅按文件名判断）")
    out.append(f"- 生成方式：`python scan_repo_hygiene.py`（可随时重跑）")
    out.append("")
    out.append("## 一、密钥与凭据")
    if secret_hits:
        for h in secret_hits:
            out.append(f"- [高危] `{h['file']}` 行 {h['line']}：{h['desc']} → "
                       f"`{h['match']}`")
    else:
        out.append("- [PASS] 跟踪文件内未发现密钥 / 令牌 / 明文口令"
                   "（扫描器自身与扫描报告已排除，避免自指命中）")
    if EXTRA_NEEDLES:
        out.append(f"- 本轮附带复查了 {len(EXTRA_NEEDLES)} 个由环境变量 "
                   f"`DSH_SECRET_NEEDLES` 指定的令牌字样")
    else:
        out.append("- 未指定 `DSH_SECRET_NEEDLES`（需要复查某个具体令牌时再传，"
                   "以免把检测针写进仓库）")
    if hist_hits:
        out.append(f"\n历史提交中的同类命中（{len(hist_hits)} 条，需人工确认）：")
        for h in hist_hits[:20]:
            out.append(f"- [历史 {h['commit']}] {h['desc']} → {h['line']}")
    else:
        out.append("- [PASS] git 历史文本文件中未发现密钥模式")
    out.append(f"- [记录] {HISTORY_NOTE}")
    out.append("")
    out.append("## 二、隐私信息")
    if pii_hits:
        by_file = {}
        for h in pii_hits:
            by_file.setdefault(h["file"], []).append(h)
        for f, hs in sorted(by_file.items()):
            out.append(f"- `{f}`：{len(hs)} 处")
            for h in hs[:6]:
                out.append(f"  - 行 {h['line']}｜{h['desc']}｜`{h['match']}`")
    else:
        out.append("- [PASS] 未发现手机号 / 邮箱 / 本机路径")
    out.append("")
    out.append("## 三、废弃 claim（已被修正的旧数字 / 旧表述）")
    out.append(f"- 命中合计 {len(legacy_hits)} 处："
               f"其中 **{len(need_fix)} 处需确认**、{len(documented)} 处属"
               f"诚信记录 / 历史说明（有意保留）")
    out.append("")
    if need_fix:
        out.append("### 3.1 需确认（不在诚信记录文件内，且无历史标记）")
        by_file = {}
        for h in need_fix:
            by_file.setdefault(h["file"], []).append(h)
        for f, hs in sorted(by_file.items()):
            out.append(f"- `{f}`：{len(hs)} 处")
            for h in hs[:8]:
                out.append(f"  - 行 {h['line']}｜{h['desc']}｜{h['snippet']}")
    else:
        out.append("### 3.1 需确认（不在诚信记录文件内，且无历史标记）")
        out.append("- 无")
    out.append("")
    out.append("### 3.2 属历史说明 / 诚信记录（有意保留，不修改）")
    by_file = {}
    for h in documented:
        by_file.setdefault(h["file"], []).append(h)
    for f, hs in sorted(by_file.items()):
        out.append(f"- `{f}`：{len(hs)} 处（行 "
                   f"{', '.join(str(x['line']) for x in hs[:12])}）")
    out.append("")
    out.append("## 四、生成物一致性（manifest.json 记录值 vs 实际文件）")
    if manifest_stale:
        out.append(f"- [需修正] {len(manifest_stale)} 处记录值已过期"
                   f"（跑 `python make_ai_handoff.py` 重新生成）：")
        for s in manifest_stale[:20]:
            out.append(f"  - `{s['path']}` {s['field']}：记录 "
                       f"{s['recorded']} → 实际 {s['actual']}")
    else:
        out.append("- [PASS] manifest.json 记录的大小与哈希与工作区一致")
    out.append("")
    out.append("## 五、结论与建议")
    high = len(secret_hits)
    out.append(f"- 密钥：{'**需处理**' if high else '未发现'}（高危 {high} 处；"
               f"历史提交命中 {len(hist_hits)} 处）")
    out.append(f"- 隐私：{len(pii_hits)} 处，见第二节；竞赛联系信息为模板要求填写，"
               f"公开仓库如需脱敏见 `docs/legacy_materials_notice.md` §四")
    out.append(f"- 废弃 claim：当前文档需确认 {len(need_fix)} 处；"
               f"历史材料的口径指引见 `docs/legacy_materials_notice.md`")
    out.append(f"- 生成物一致性：{'需重跑生成脚本' if manifest_stale else '一致'}")

    text = "\n".join(out) + "\n"
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"扫描完成 → {os.path.relpath(OUT_MD, HERE)}")
    print(f"密钥/凭据：{len(secret_hits)}（历史 {len(hist_hits)}）｜"
          f"隐私：{len(pii_hits)}｜废弃 claim：{len(legacy_hits)}"
          f"（需确认 {len(need_fix)}）｜清单过期：{len(manifest_stale)}")
    for h in need_fix[:25]:
        print(f"  [需确认] {h['file']} 行 {h['line']}｜{h['desc']}｜{h['snippet'][:80]}")
    for h in secret_hits[:10]:
        print(f"  [高危] {h['file']} 行 {h['line']}｜{h['desc']}｜{h['match']}")
    for h in hist_hits[:10]:
        print(f"  [历史] {h['commit']}｜{h['desc']}｜{h['line'][:100]}")
    return 1 if secret_hits else 0


if __name__ == "__main__":
    sys.exit(main())
