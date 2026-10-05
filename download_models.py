# -*- coding: utf-8 -*-
# 本脚本用于从 ModelScope 模型仓库下载 SoundInsight 权重并校验文件大小。
# 用法：python download_models.py --repo 你的用户名/SoundInsight_models
# 或在 config.json 中填写 model_repo_id 后直接运行。
import argparse
import json
import os
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://modelscope.cn/api/v1/models/{repo}/repo?FilePath={fname}"

FILES = [
    ("sound_model", "config.json", 500),
    ("sound_model", "tokenizer.json", 500_000),
    ("sound_model", "tokenizer_config.json", 200),
    ("sound_model", "threshold.json", 10),
    ("sound_model", "model.safetensors", 200_000_000),
    ("multi_label_model", "config.json", 500),
    ("multi_label_model", "tokenizer.json", 500_000),
    ("multi_label_model", "tokenizer_config.json", 200),
    ("multi_label_model", "issue_labels.json", 100),
    ("multi_label_model", "model.safetensors", 200_000_000),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=str, default="")
    args = ap.parse_args()
    repo = args.repo
    if not repo:
        cfg_path = os.path.join(HERE, "config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, encoding="utf-8") as f:
                repo = json.load(f).get("model_repo_id", "")
    if not repo:
        raise SystemExit("请提供模型仓库地址：python download_models.py "
                         "--repo 你的用户名/SoundInsight_models")

    for dname, fname, min_size in FILES:
        dst = os.path.join(HERE, dname, fname)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst) and os.path.getsize(dst) >= min_size:
            print(f"跳过（已存在）: {dname}/{fname}")
            continue
        url = API.format(repo=repo, fname=f"{dname}/{fname}")
        r = requests.get(url, timeout=900, stream=True)
        if r.status_code != 200:
            raise SystemExit(f"下载失败 {fname}: HTTP {r.status_code}")
        with open(dst, "wb") as fp:
            for chunk in r.iter_content(1 << 20):
                fp.write(chunk)
        size = os.path.getsize(dst)
        if size < min_size:
            raise SystemExit(f"文件大小异常 {fname}: {size} < {min_size}")
        print(f"完成 {dname}/{fname} ({size / 1e6:.1f} MB)")
    # 权重哈希校验：与登记值不符即报错（防止仓库仍是旧权重、Demo 静默跑错模型）
    hp = os.path.join(HERE, "model_hashes.json")
    if os.path.isfile(hp):
        import hashlib
        want = json.load(open(hp, encoding="utf-8"))
        for rel, exp in want.items():
            if rel == "note":
                continue
            fp = os.path.join(HERE, rel)
            if not os.path.isfile(fp):
                continue
            h = hashlib.sha256()
            with open(fp, "rb") as fh:
                for c in iter(lambda: fh.read(1 << 20), b""):
                    h.update(c)
            got = h.hexdigest()
            if got != exp:
                raise SystemExit(
                    f"权重哈希不符：{rel}\n  期望 {exp[:16]}…\n  实际 {got[:16]}…\n"
                    "→ 模型仓库尚未更新为出厂版本，请先上传或改用包内权重。")
            print(f"哈希校验通过：{rel}")
    print("全部模型文件下载并校验完成。")


if __name__ == "__main__":
    main()
