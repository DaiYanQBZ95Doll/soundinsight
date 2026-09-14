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
PDF = f"{TEAM}_{NAME}_复赛作品.pdf"
DOCX = f"{TEAM}_{NAME}_复赛作品.docx"
REQUIRED = [
    (PDF, "主文档 PDF（python md_to_pdf.py 生成，内嵌中文字体）"),
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

    # 主文档：PDF 优先；若只有 DOCX（模板允许 .docx 或 .pdf）则用 DOCX 并在提示中说明
    main_doc = None
    for cand in (PDF, DOCX):
        if os.path.isfile(os.path.join(HERE, cand)):
            main_doc = cand
            break

    missing = []
    for fname, desc in REQUIRED:
        p = os.path.join(HERE, fname)
        ok = os.path.isfile(p)
        if not ok and fname == PDF and main_doc == DOCX:
            ok = True  # 用 DOCX 顶替主文档
        size = f"{os.path.getsize(p):,} B" if os.path.isfile(p) else "缺失"
        print(f"[{'OK  ' if ok else 'MISS'}] {fname:<52} {size}")
        if not ok:
            missing.append((fname, desc))
    if main_doc == DOCX:
        print(f"[INFO] 主文档使用 Word 版：{DOCX}（模板允许 .docx 或 .pdf）")

    if missing:
        print("\n还缺以下文件（放进项目根目录后重跑本脚本）：")
        for fname, desc in missing:
            print(f"  - {fname}   （{desc}）")
        if any(f.endswith(".mp4") for f, _ in missing):
            print("\n视频生成方式：按 video_script.md（200 秒 / 9 镜头）录制，"
                  f"命名为 {TEAM}_{NAME}_演示视频.mp4")
        print("\n其余已就位的文件仍会打进 复赛作品.zip（不阻塞）。")

    # 包内说明每次都按当前状态重写，避免出现"说明与包内容矛盾"
    try:
        import build_submission as bs
        readme = bs.README_SUBMISSION.encode("utf-8")
    except Exception as e:  # noqa: BLE001 - 说明模块不可用时沿用旧说明
        readme = None
        print(f"[WARN] 未能读取最新说明文本（{type(e).__name__}），沿用包内旧说明")

    # 保留已有条目（如 README_SUBMISSION.txt），并以根目录最新文件替换/追加四个提交物
    keep = {}
    if os.path.isfile(FINAL_ZIP):
        with zipfile.ZipFile(FINAL_ZIP) as z:
            for info in z.infolist():
                if info.filename == "hashes.txt":
                    continue  # 本轮重新生成，避免同名重复条目
                keep[info.filename] = z.read(info.filename)
    if readme is not None:
        keep["README_SUBMISSION.txt"] = readme

    for fname, _ in REQUIRED:
        src = os.path.join(HERE, fname)
        if os.path.isfile(src):
            keep[fname] = None  # None = 打包时从磁盘读取最新内容
    if main_doc == DOCX and not os.path.isfile(os.path.join(HERE, PDF)):
        keep[DOCX] = None  # 无 PDF 时以 Word 版作为主文档

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

    # hashes.txt：只登记"内容稳定、可被复核者解包自验"的条目。
    # 外层 zip 自身的哈希无法写进自身（自引用），因此包内版本不列它；
    # 根目录的版本额外带上外层哈希，供提交前留档。
    inner = []
    for fname, _ in REQUIRED:
        src = os.path.join(HERE, fname)
        if os.path.isfile(src):
            inner.append(f"{os.path.getsize(src):>12,} B  sha256:{sha256(src)}  {fname}")
    if main_doc == DOCX and os.path.isfile(os.path.join(HERE, DOCX)):
        p = os.path.join(HERE, DOCX)
        inner.append(f"{os.path.getsize(p):>12,} B  sha256:{sha256(p)}  {DOCX}")
    header = ("# 提交包内四项提交物的打包时刻校验值（完整 SHA256，非截断）。\n"
              "# 这些文件内容不受重新打包影响，可解包后自行复算核对。\n"
              "# 外层 zip 自身的哈希无法写入自身（自引用），以天池提交页显示为准。")
    body = header + "\n" + "\n".join(inner) + "\n"

    # 先把清单放进包里（额外条目，不影响模板要求的四项）——必须先做，
    # 否则下面报出的包大小与 SHA256 会漏掉这个条目，与磁盘上的实际文件不符。
    tmp = FINAL_ZIP + ".tmp"
    with zipfile.ZipFile(FINAL_ZIP) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            zout.writestr(info, zin.read(info.filename))
        zout.writestr("hashes.txt", body.encode("utf-8"))
    os.replace(tmp, FINAL_ZIP)

    # 此刻的包已是最终形态，再取大小与哈希
    final_size = os.path.getsize(FINAL_ZIP)
    final_hash = sha256(FINAL_ZIP)
    with open(os.path.join(HERE, "hashes.txt"), "w", encoding="utf-8") as f:
        f.write(f"{final_size:>12,} B  sha256:{final_hash}  {os.path.basename(FINAL_ZIP)}\n" + body)

    print("\n已更新提交包：")
    with zipfile.ZipFile(FINAL_ZIP) as z:
        for info in z.infolist():
            print(f"  {info.file_size:>12,} B  {info.filename}")
    print(f"\n包大小（最终，含包内 hashes.txt）: {final_size:,} B")
    print(f"SHA256（最终）: {final_hash}")
    print("已写出 hashes.txt（根目录 + 包内各一份）")

    print("\n提交前最后确认：")
    print("  1. zip 命名是否为 团队名_方案名称_复赛作品.zip（天池只接受一个 zip）")
    print("  2. 主文档是否为最终版（含团队信息、在线链接表、注意事项）")
    print("  3. 视频时长是否在 3-5 分钟区间")
    print("  4. 包内是否不再含'待放入/占位'类文件")
    print("  5. 校验值变化属预期（放入 PDF/视频后 SHA256 会与 D13 声明不同）")
    print("  6. 提交前把 hashes.txt 与 zip 一起留档（容器哈希以它为准）")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
