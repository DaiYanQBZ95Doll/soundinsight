# -*- coding: utf-8 -*-
# 本脚本用于 PPT 文本审计：用标准库 zipfile 解压 pptx，提取每页文本，
# 输出 ppt_text_dump.md 并核对页数与数字口径。
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_MD = os.path.join(HERE, "ppt_text_dump.md")


def find_pptx():
    for f in os.listdir(HERE):
        if f.endswith(".pptx") and not f.startswith("~$"):
            return os.path.join(HERE, f)
    return None


def main() -> None:
    path = find_pptx()
    if path is None:
        with open(OUT_MD, "w", encoding="utf-8") as f:
            f.write("# PPT 文本审计\n\n未找到 pptx 文件：SKIP\n")
        print("未找到 pptx 文件")
        return

    z = zipfile.ZipFile(path)
    slides = sorted(
        [n for n in z.namelist()
         if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)],
        key=lambda n: int(re.search(r"slide(\d+)", n).group(1)))
    out = [f"# PPT 文本审计：{os.path.basename(path)}", "",
           f"总页数：{len(slides)}", ""]
    all_text = []
    for n in slides:
        xml = z.read(n).decode("utf-8", errors="replace")
        texts = re.findall(r"<a:t>([^<]*)</a:t>", xml)
        page_text = " ".join(t for t in texts if t.strip())
        all_text.append(page_text)
        num = re.search(r"slide(\d+)", n).group(1)
        out.append(f"## 第 {int(num)} 页")
        out.append(page_text if page_text else "（无文本）")
        out.append("")

    # 数字口径核对
    joined = "\n".join(all_text)
    out.append("## 自动核对")
    out.append(f"- 页数 {len(slides)} 是否在 8-12 之间: "
               f"{'PASS' if 8 <= len(slides) <= 12 else 'FAIL'}")
    checks = [
        ("0.687", "F1 0.687"),
        ("0.6234", "CV 0.6234"),
        ("0.97", "阈值 0.97"),
        ("89.6", "召回率 89.6%"),
        ("0.7191", "AUC-PR"),
        ("41.5", "三星漏检 41.5%"),
        ("51.8", "弱标注精度 51.8%"),
        ("1257", "正例 1257"),
    ]
    for pat, desc in checks:
        out.append(f"- {desc}: {'PASS' if pat in joined else 'FAIL（未出现）'}")
    if "83.7" in joined:
        out.append("- [FAIL] 教师一致性 83.7 出现在 PPT 中（应仅在附录/方法说明）")
    else:
        out.append("- [PASS] 83.7 未出现")
    if "1297" in joined:
        out.append("- [FAIL] 错误正例数 1297 出现")
    else:
        out.append("- [PASS] 1297 未出现")
    # 混淆矩阵阈值匹配
    if "19504" in joined:
        out.append("- 混淆矩阵含 [[19504,245],[26,225]]：属 thr=0.5 口径"
                   "（若页面标注为 0.9744 则为 FAIL，需人工确认）")
    if "19658" in joined:
        out.append("- 混淆矩阵含 TN=19658/FP=91/FN=72/TP=179：属 thr=0.9744 口径"
                   "（与阈值 0.97 一致）")

    text = "\n".join(out)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"保存 -> {OUT_MD}")
    print(text)


if __name__ == "__main__":
    main()
