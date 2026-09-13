# -*- coding: utf-8 -*-
# pack_final.py —— 最终提交包打包与自检
#
# 用法：把主文档 PDF 与演示视频放到项目根目录（文件名必须完全一致）后运行：
#   python pack_final.py
#
# 它会：
#   1. 检查四个必备提交物是否齐全、命名是否符合模板规范；
#   2. 把 PDF 与视频加入 更新世界的锋芒_SoundInsight_复赛作品.zip（保留已有条目）；
#   3. 打印最终包内清单、大小与 SHA256，供提交前核对。
import hashlib
import os
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TEAM = "更新世界的锋芒"
NAME = "SoundInsight"
FINAL_ZIP = os.path.join(HERE, f"{TEAM}_{NAME}_复赛作品.zip")
REQUIRED = [
    (f"{TEAM}_{NAME}_复赛作品.pdf", "主文档（competition_v4.md 导出）"),
    (f"{TEAM}_{NAME}_Demo.zip", "可运行 Demo 源码包"),
    (f"{TEAM}_{NAME}_演示视频.mp4", "产品演示视频（3-5 分钟）"),
    (f"{TEAM}_{NAME}_其他材料.zip", "验证报告 / 审计结果 / 图表 / 人工复核原始表"),
]


def sha256(path: str, limit: int | None = None) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    print("=" * 68)
    print("SoundInsight 最终提交包自检")
    print("=" * 68)

    missing = []
    for fname, desc in REQUIRED:
        p = os.path.join(HERE, fname)
        ok = os.path.isfile(p)
        size = f"{os.path.getsize(p):,} B" if ok else "缺失"
        print(f"[{'OK  ' if ok else 'MISS'}] {fname:<52} {size}")
        if not ok:
            missing.append((fname, desc))

    if missing:
        print("\n还缺以下文件（放进项目根目录后重跑本脚本）：")
        for fname, desc in missing:
            print(f"  - {fname}   （{desc}）")
        if any(f.endswith(".pdf") for f, _ in missing):
            print("\nPDF 生成方式：Typora 打开 competition_v4.md → 文件 → 导出 → PDF，"
                  f"另存为 {TEAM}_{NAME}_复赛作品.pdf")
        if any(f.endswith(".mp4") for f, _ in missing):
            print("\n视频生成方式：按 video_script.md（200 秒 / 9 镜头）录制，"
                  f"命名为 {TEAM}_{NAME}_演示视频.mp4")
        print("\n当前 复赛作品.zip 保持不变，未做修改。")
        return 1

    # 保留已有条目（如 README_SUBMISSION.txt），并以根目录最新文件替换/追加四个提交物
    keep = {}
    if os.path.isfile(FINAL_ZIP):
        with zipfile.ZipFile(FINAL_ZIP) as z:
            for info in z.infolist():
                keep[info.filename] = z.read(info.filename)

    for fname, _ in REQUIRED:
        src = os.path.join(HERE, fname)
        if os.path.isfile(src):
            keep[fname] = None  # None = 打包时从磁盘读取最新内容

    tmp = FINAL_ZIP + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in keep.items():
            if data is None:
                src = os.path.join(HERE, name)
                if os.path.isfile(src):
                    z.write(src, name)
            else:
                z.writestr(name, data)
    os.replace(tmp, FINAL_ZIP)

    print("\n已更新提交包：")
    with zipfile.ZipFile(FINAL_ZIP) as z:
        for info in z.infolist():
            print(f"  {info.file_size:>12,} B  {info.filename}")
    print(f"\n包大小: {os.path.getsize(FINAL_ZIP):,} B")
    print(f"SHA256: {sha256(FINAL_ZIP)}")
    print("\n提交前最后确认：")
    print("  1. zip 命名是否为 团队名_方案名称_复赛作品.zip（天池只接受一个 zip）")
    print("  2. 主文档 PDF 是否为最终版（含团队信息、在线链接表、注意事项）")
    print("  3. 视频时长是否在 3-5 分钟区间")
    print("  4. 包内是否不再含'待放入/占位'类文件")
    print("  5. 校验值变化属预期（放入 PDF/视频后 SHA256 会与 D13 声明不同）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
