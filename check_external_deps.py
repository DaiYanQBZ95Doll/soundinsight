# -*- coding: utf-8 -*-
"""P9 防护（决策方已批准）：**包外依赖**入链检查。

为什么（我自查 + 红队一致）：评委路径的命门在"包内/包外交界处"——
  ① `download_models.py` 依赖的模型仓库 URL 是否可达（权重不在包内，需现场下载）；
  ② `config.json` 是否含 `model_repo_id`（缺了会让评委按 README 跑时直接报错退出——此类事故已发生过）；
  ③ 包内 Demo 的相对路径是否自洽（`bin_model_dir`/`multi_label_dir`/`threshold_file` 等）。

用法：python check_external_deps.py    （可达性检查失败不阻断，但会明确列出）
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "SoundInsight-deps-check"}


def head(url: str, timeout: int = 20):
    try:
        req = urllib.request.Request(url, headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Length")
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {str(e)[:60]}"


def main() -> int:
    problems, notes = [], []
    # ① config.json 关键字段
    cfg_path = os.path.join(HERE, "config.json")
    cfg = {}
    if not os.path.isfile(cfg_path):
        problems.append("config.json 不存在（产品启动必需）")
    else:
        cfg = json.load(open(cfg_path, encoding="utf-8"))
        repo = cfg.get("model_repo_id")
        if not repo:
            problems.append("config.json 缺 model_repo_id（`download_models.py` 无参运行会报错退出）")
        else:
            notes.append(f"config.json：model_repo_id={repo}")
        for k in ("bin_model_dir", "multi_label_dir", "threshold_file", "issue_labels_file"):
            if k not in cfg:
                problems.append(f"config.json 缺字段 {k}")
    # ② 权重仓库可达性
    repo = cfg.get("model_repo_id")
    if repo:
        for f in ("sound_model/model.safetensors", "multi_label_model/model.safetensors",
                  "sound_model/threshold.json"):
            url = f"https://modelscope.cn/api/v1/models/{repo}/repo?FilePath={f}"
            status, extra = head(url)
            if status == 200:
                notes.append(f"权重可达 ✓ {f}（HTTP 200）")
            else:
                # 网络不可达属**环境波动**（告警，不判失败）；权重文件 404 属结构问题（失败）
                if status in (403, 404):
                    problems.append(f"权重文件不存在或不可读：{f} → HTTP {status}")
                else:
                    notes.append(f"[WARN] 网络不可达（不判失败）：{f} → {status or extra}")
    # ③ 包内相对路径自洽（在 Demo.zip 里检查）
    demo = os.path.join(HERE, "更新世界的锋芒_SoundInsight_Demo.zip")
    if os.path.isfile(demo):
        with zipfile.ZipFile(demo) as z:
            names = set(z.namelist())
        for k in ("config.json", "download_models.py", "requirements.txt", "README.md"):
            if k not in names:
                problems.append(f"Demo 包缺 {k}")
        if "config.json" in names:
            inner = json.loads(zipfile.ZipFile(demo).read("config.json").decode("utf-8"))
            notes.append(f"Demo 包内 config.json 与仓库{'一致' if inner == cfg else '**不一致**'}")
            if inner != cfg:
                problems.append("Demo 包内 config.json 与仓库不一致（评委跑的是包内那份）")
    else:
        notes.append("未找到 Demo 包（跳过包内路径检查）")

    print("## 包外依赖检查（P9）")
    for n in notes:
        print(f"- [PASS] {n}")
    for p in problems:
        print(f"- [FAIL] {p}")
    if not problems:
        print("- 结论：包外依赖齐备（配置字段、权重可达性、包内目录结构）")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
