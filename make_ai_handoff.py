# -*- coding: utf-8 -*-
# make_ai_handoff.py —— 生成"给其他 AI 助手读"的项目导览包
#
# 产物（AI_HANDOFF/ 目录，全部为小体积文本，便于 AI 直接读取）：
#   manifest.json        —— 全项目文件索引（路径/类别/大小/用途，机器可读）
#   02_repo_map.md       —— 人类可读的文件地图（由本脚本自动生成）
# 其余说明文件为手写文档，本脚本不覆盖。
#
# 用法：python make_ai_handoff.py
import hashlib
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "AI_HANDOFF")

EXCLUDE_DIRS = {".git", "__pycache__", ".ms_upload_tmp", "AI_HANDOFF",
                ".venv", "venv", "sound_model", "multi_label_model",
                "distilbert-base-uncased", "roberta-base"}
# 大文件：不复制、可登记（体积原因）
LARGE_HINT = {
    "sound_model": "冻结的二分类模型权重（约 256MB），不入 git",
    "multi_label_model": "冻结的多标签归因模型权重（约 256MB），不入 git",
    "distilbert-base-uncased": "基座模型缓存（HF/ModelScope）",
    "roberta-base": "RoBERTa 探测用基座缓存",
}
HASH_LIMIT = 8 * 1024 * 1024  # 8MB 以上只记大小，不做哈希

KEY_PURPOSE = {
    "results_summary.md": "冻结数字唯一权威源（含 ±1 混淆矩阵调和行）",
    "number_audit.md": "数字一致性审计结果（含官方模板格式对照节）",
    "MODEL_CARD.md": "模型卡：任务/基座/指标/六条局限",
    "llm_baseline.md": "LLM 对照报告（deepseek + qwen3.7-plus，含循环性红利声明）",
    "error_taxonomy.md": "错误分类学：FP/FN 构成 + 标注噪声人工终审",
    "calibration_eval.md": "校准评估：ECE 0.0122 与决策区间过度自信",
    "length_bucket_eval.md": "tokenizer 长度分桶（>128 token 截断桶 F1 0.565）",
    "edge_case_benchmark.md": "六类边界场景定向探针",
    "throughput_eval.md": "GPU/CPU 吞吐实测",
    "stats_validation.md": "统计验证（PR 曲线 / 学习曲线）",
    "ablation_summary.md": "消融实验 3 组结论",
    "significance_test.md": "Welch t 检验（p=0.000932）",
    "confidence_tiered.md": "三星补漏置信度分层与中置信剔除记录",
    "qna_preparation.md": "答辩 Q&A（10 问，含口径警示）",
    "competition_v4.md": "主文档（13 章，含模板九章 + 合规披露 + 局限）",
    "competition_v3.txt": "官方模板九章版主文档",
    "competition_v2.md": "初赛版文档",
    "hackathon-复赛作品提交模板-天池版.docx": "官方复赛模板原文（格式对照基准）",
    "video_script.md": "演示视频脚本（200 秒 / 9 镜头）",
    "video_script_silent.md": "无口播拍摄卡（操作步骤 + 画面要点）",
    "video_script.srt": "字幕文件（28 条 / 0:00-3:20 / UTF-8）",
    "human_review_noise16.csv": "标注噪声 16 条人工终审表（15/16 确认）",
    "human_review_conf30.csv": "中置信 8 条人工复核表（3/8 通过→全剔除）",
    "human_review_50.csv": "标注人工抽查 50 条（78% 通过）",
    "val_preds_dump.csv": "val_v2 全量推理快照（prob/pred/长度/标签）",
    "llm_eval_input.jsonl": "LLM 对照子集（1000 条 = val_v2 正例全集 + 749 负例）",
    "val_v2.csv": "固定验证集（20000 条 / 251 正例），红线冻结",
    "electronics_expanded.csv": "主数据集（10 万条，含 timeStamp 恢复）",
    "labeled_llm.csv": "LLM 复核后标签（当前工作集正例 1280）",
    "labeled_llm_before_treble.csv": "高音补捞前备份（冻结实验口径 1257）",
    "demo_sound_v2.py": "本地 Gradio Demo（三页；已内置代理绕过）",
    "soundinsight_agent.py": "一键洞察 Agent（md/excel、zh/en、非英文跳过）",
    "predict_core.py": "共享推理核心（含非英文显式拒绝）",
    "api_server.py": "FastAPI 服务（/health、/predict）",
    "启动Demo.bat": "双击启动本地 Demo",
    "打包提交包.bat": "双击执行最终打包与自检",
    "pack_final.py": "提交包打包与四项自检",
    "check_doc_numbers.py": "数字审计 + 模板格式对照脚本",
    "deploy_check.py": "在线 Demo 单条验收脚本",
    "batch_check.py": "在线 Demo 批量验收脚本",
    "md_to_pdf.py": "主文档 Markdown → PDF（内嵌中文字体）",
    "md_to_docx.py": "主文档 Markdown → Word",
    "docs/D13_seal_declaration.md": "D13 封包声明（提交技术质检终审）",
    "docs/D14_resume_checklist.md": "收尾四步清单（录视频/打包/上传/补推送）",
    "docs/project_full_record.md": "初赛→复赛全流程记录",
    "docs/file_inventory.md": "项目文件总索引",
    "docs/dataset_audit.md": "数据集字段考古",
    "docs/drift_plan.md": "数据漂移监控方案",
    "docs/year_split_output.txt": "年份分桶脚本输出原文",
}

CATEGORY_RULES = [
    ("提交物", ("_复赛作品.zip", "_Demo.zip", "_其他材料.zip",
                "_复赛作品.pdf", "_复赛作品.docx")),
    ("主文档与模板", ("competition_v", "hackathon-", "README.md",
                      "REPO_INTRO", "DEPLOY_GUIDE")),
    ("历史材料·初赛", ("创意方案",)),
    ("参考材料", (".html",)),
    ("部署包", ("deployment/",)),
    ("生成产物·日志", (".log", "batch_report", "insight_report",
                       "training_output", "summary_log", "capture_log")),
    ("验证报告", ("llm_baseline", "length_bucket_eval", "edge_case_benchmark",
                  "calibration_eval", "error_taxonomy", "throughput_eval",
                  "stats_validation", "ablation_summary", "significance_test",
                  "confidence_tiered", "number_audit", "qna_preparation",
                  "edge_cases", "user_scenarios", "action_report_template",
                  "MODEL_CARD", "results_summary")),
    ("证据·标注流程", ("review_input", "review_result", "three_star_",
                       "neg_review_", "conf_review_", "treble_",
                       "human_review_")),
    ("证据·对照与错误分析", ("llm_eval_", "llm_qwen_", "llm_err_",
                             "spot_check", "val_preds_dump",
                             "learning_curve_results")),
    ("过程与交接文档", ("PROGRESS_SYNC", "QWEN_HANDOFF", "PROJECT_BRIEF",
                        "AI_INDUCTION", "docs/")),
    ("数据", (".csv", "electronics_prefix.bin")),
    ("图表", (".png",)),
    ("演示材料", (".pptx", "ppt_text_dump", "video_script", "视频素材")),
    ("代码", (".py", ".bat", "config.json", "requirements.txt")),
    ("实验归档", ("exp0",)),
]


def categorize(rel: str) -> str:
    rel_l = rel.replace("\\", "/")
    for name, keys in CATEGORY_RULES:
        for k in keys:
            if k.startswith("."):
                if rel_l.lower().endswith(k):
                    return name
            elif k in rel_l:
                return name
    return "其他"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect():
    entries = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fn in sorted(files):
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, HERE).replace("\\", "/")
            size = os.path.getsize(full)
            item = {
                "path": rel,
                "category": categorize(rel),
                "size_bytes": size,
                "purpose": KEY_PURPOSE.get(rel, ""),
                "sha256_16": sha256(full) if size <= HASH_LIMIT else "",
            }
            entries.append(item)
    # 大文件目录：登记但不遍历
    for d, desc in LARGE_HINT.items():
        p = os.path.join(HERE, d)
        if os.path.isdir(p):
            total = sum(os.path.getsize(os.path.join(r, f))
                        for r, _, fs in os.walk(p) for f in fs)
            entries.append({"path": d + "/", "category": "大文件·不入库",
                            "size_bytes": total, "purpose": desc,
                            "sha256_16": ""})
    return entries


def write_repo_map(entries):
    order = ["提交物", "主文档与模板", "验证报告", "过程与交接文档",
             "演示材料", "图表", "证据·标注流程", "证据·对照与错误分析",
             "数据", "代码", "部署包", "实验归档", "历史材料·初赛",
             "参考材料", "生成产物·日志", "大文件·不入库", "其他"]
    lines = ["# 文件地图（由 make_ai_handoff.py 自动生成，勿手改）", "",
             f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M')}；"
             f"共 {len(entries)} 个条目；体积单位 KB/MB。", ""]
    for cat in order:
        rows = [e for e in entries if e["category"] == cat]
        if not rows:
            continue
        total = sum(e["size_bytes"] for e in rows)
        lines.append(f"## {cat}（{len(rows)} 项，"
                     f"{total / 1024 / 1024:.1f} MB）")
        lines.append("")
        lines.append("| 文件 | 大小 | 用途 |")
        lines.append("|---|---|---|")
        for e in sorted(rows, key=lambda x: -x["size_bytes"]):
            size = e["size_bytes"]
            shown = (f"{size / 1024 / 1024:.1f} MB" if size >= 1024 * 1024
                     else f"{size / 1024:.1f} KB")
            lines.append(f"| `{e['path']}` | {shown} | {e['purpose']} |")
        lines.append("")
    text = "\n".join(lines)
    path = os.path.join(OUT, "02_repo_map.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  02_repo_map.md（{len(text)} 字符）")


def main():
    os.makedirs(OUT, exist_ok=True)
    entries = collect()
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": time.strftime("%Y-%m-%d %H:%M"),
                   "root": HERE, "count": len(entries),
                   "entries": entries}, f, ensure_ascii=False, indent=1)
    print(f"  manifest.json（{len(entries)} 条目）")
    write_repo_map(entries)
    cats = {}
    for e in entries:
        cats[e["category"]] = cats.get(e["category"], 0) + 1
    print("  分类统计：" + "，".join(f"{k} {v}" for k, v in cats.items()))


if __name__ == "__main__":
    main()
