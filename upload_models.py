# -*- coding: utf-8 -*-
# 本脚本用于将本地模型权重上传到 ModelScope 模型仓库。
#
# 用户需先手动完成 3 步网页操作：
#   1. 注册并登录 modelscope.cn（约 3 分钟）
#   2. 新建一个模型仓库（建议命名 SoundInsight_models，约 2 分钟）
#   3. 在「个人中心-访问令牌」创建 token（约 2 分钟）
# 完成后运行：
#   python upload_models.py --repo <你的命名空间>/SoundInsight_models \
#       --token <你的token>
# 脚本会把 sound_model/ 与 multi_label_model/ 的文件按目录结构推送到该仓库。
import argparse
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIRS = [
    ("sound_model", "sound_model"),
    ("multi_label_model", "multi_label_model"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="ModelScope 仓库路径，如 用户名/SoundInsight_models")
    ap.add_argument("--token", required=True, help="ModelScope 访问令牌")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印将上传的文件清单，不执行 git 操作")
    args = ap.parse_args()

    tmp = os.path.join(HERE, ".ms_upload_tmp")
    if os.path.isdir(tmp):
        shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    total_size = 0
    total_files = 0
    for src, dst in SRC_DIRS:
        src_path = os.path.join(HERE, src)
        if not os.path.isdir(src_path):
            raise SystemExit(
                f"错误：{src} 目录不存在。请在项目根目录运行本脚本，"
                f"并确认 {src} 权重已存在。")
        copied = shutil.copytree(src_path, os.path.join(tmp, dst),
                                 dirs_exist_ok=True)
        for root, _, files in os.walk(copied):
            for fn in files:
                fp = os.path.join(root, fn)
                total_size += os.path.getsize(fp)
                total_files += 1
                rel = os.path.relpath(fp, tmp)
                print(f"  {rel} ({os.path.getsize(fp) / 1e6:.1f} MB)")

    print(f"文件总数：{total_files}")
    print(f"总大小：{total_size / 1e6:.0f} MB")
    if args.dry_run:
        print("dry-run 模式：不执行 git 推送")
        return

    remote = f"https://oauth2:{args.token}@www.modelscope.cn/{args.repo}.git"
    cmds = [
        ["git", "init"],
        ["git", "lfs", "install", "--local"],
        ["git", "lfs", "track", "*.safetensors"],
        ["git", "config", "user.name", "SoundInsight"],
        ["git", "config", "user.email",
         "soundinsight@users.noreply.github.com"],
        ["git", "add", "."],
        ["git", "commit", "-m", "upload SoundInsight models"],
        ["git", "branch", "-M", "master"],
        ["git", "remote", "add", "origin", remote],
    ]
    for c in cmds:
        r = subprocess.run(c, cwd=tmp, capture_output=True, text=True,
                           shell=False)
        print(f"> {' '.join(c)}")
        if r.returncode != 0 and c[1] != "init":
            print(r.stderr[-800:])
            raise SystemExit(f"命令失败：{' '.join(c)}")
    # 远程仓库自带 README 提交，用合并式拉取集成后推送
    pull = subprocess.run(
        ["git", "pull", "--no-rebase", "--allow-unrelated-histories",
         "origin", "master"], cwd=tmp, capture_output=True, text=True)
    print("> git pull --no-rebase --allow-unrelated-histories origin master")
    if pull.returncode != 0:
        print(pull.stderr[-400:])
        print("合并拉取失败，尝试强制推送（仅覆盖自动生成的 README）")
        push = subprocess.run(["git", "push", "-f", "-u", "origin",
                               "master"], cwd=tmp, capture_output=True,
                              text=True)
        print("> git push -f -u origin master")
        if push.returncode != 0:
            print(push.stderr[-800:])
            raise SystemExit("强制推送也失败")
        print(f"上传完成 -> https://modelscope.cn/models/{args.repo}")
        return
    push = subprocess.run(["git", "push", "-u", "origin", "master"],
                          cwd=tmp, capture_output=True, text=True)
    print("> git push -u origin master")
    if push.returncode != 0:
        print(push.stderr[-800:])
        raise SystemExit("推送失败：git push -u origin master")
    print(f"上传完成 -> https://modelscope.cn/models/{args.repo}")
    print(f"请把 {args.repo} 填入 deployment/config.json 的 model_repo_id")


if __name__ == "__main__":
    main()
