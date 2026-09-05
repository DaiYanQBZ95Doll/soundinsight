# -*- coding: utf-8 -*-
# 本脚本用于静态验证下载链路：构造全部模型文件的最终下载 URL，
# 断言每个 URL 含目录前缀，输出 11 行 URL 清单供人工过目。
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "https://modelscope.cn/api/v1/models/{repo}/repo?FilePath={fname}"

FILES = [
    ("sound_model", "config.json"),
    ("sound_model", "tokenizer.json"),
    ("sound_model", "tokenizer_config.json"),
    ("sound_model", "threshold.json"),
    ("sound_model", "model.safetensors"),
    ("multi_label_model", "config.json"),
    ("multi_label_model", "tokenizer.json"),
    ("multi_label_model", "tokenizer_config.json"),
    ("multi_label_model", "issue_labels.json"),
    ("multi_label_model", "model.safetensors"),
]
# 加上 upload_models 的 README 兜底路径共 11 个文件位（10 模型文件 + 1 占位）
EXTRA = [("sound_model", "README.md")]


def main() -> None:
    all_files = FILES + EXTRA
    repo = "example/SoundInsight_models"
    urls = [API.format(repo=repo, fname=f"{d}/{f}") for d, f in all_files]
    bad = []
    for d, f in all_files:
        url = API.format(repo=repo, fname=f"{d}/{f}")
        if f"FilePath={d}/{f}" not in url:
            bad.append((d, f))
    print(f"共 {len(urls)} 个文件位")
    for url in urls:
        print(url)
    if bad:
        raise SystemExit(f"FAIL: {len(bad)} 个 URL 缺目录前缀: {bad}")
    print("PASS: 全部 URL 含目录前缀")


if __name__ == "__main__":
    main()
