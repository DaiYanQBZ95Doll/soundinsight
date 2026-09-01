# -*- coding: utf-8 -*-
# 本脚本是最终验收链：在最终模型训练完成后执行，依次重跑验证集评估、
# 重绘混淆矩阵与 Demo 概率图，刷新提交用的全部截图与文本产物。
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(script, log):
    print(f"=== 运行 {script} ===")
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run([PY, os.path.join(HERE, script)],
                           cwd=HERE, stdout=f, stderr=subprocess.STDOUT)
    print(f"exit={r.returncode} | 日志: {log}")


def main() -> None:
    run("test_model.py", os.path.join(HERE, "training_output.txt"))
    run("capture_demo_output.py", os.path.join(HERE, "capture_log.txt"))
    run("results_summary.py", os.path.join(HERE, "summary_log.txt"))
    print("验收链完成：training_output.txt、confusion_matrix.png、"
          "demo_output.png、results_summary.md 已全部刷新")


if __name__ == "__main__":
    main()
