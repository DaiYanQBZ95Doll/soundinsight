# -*- coding: utf-8 -*-
# C1 重做（P0-4 修复）：按 TOKENIZER 长度分桶（<=64 / 65-128 / >128 token），
# 检验 max_len=128 的截断暴露。旧字符口径一并保留为对照列。
# token 计数不含特殊 token；模型实际输入含 [CLS]/[SEP] 且截断至 128，
# 故 >128 token 的评论在推理时被截断。
import os
import sys

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support
from transformers import DistilBertTokenizer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
VAL = os.path.join(HERE, "val_v2.csv")
DUMP = os.path.join(HERE, "val_preds_dump.csv")
MODEL_DIR = os.path.join(HERE, "sound_model")
OUT_MD = os.path.join(HERE, "length_bucket_eval.md")

BUCKETS = [("<=64 token", 0, 64), ("65-128 token", 65, 128),
           (">128 token", 129, 10 ** 9)]


def main() -> None:
    tok = DistilBertTokenizer.from_pretrained(MODEL_DIR)
    va = pd.read_csv(VAL, encoding="utf-8", keep_default_na=False)
    dump = pd.read_csv(DUMP, encoding="utf-8", keep_default_na=False)
    assert len(va) == len(dump), f"row mismatch {len(va)} vs {len(dump)}"
    texts = va["text"].astype(str).tolist()
    print(f"tokenizing {len(texts)} texts ...")
    n_tok = []
    for b in range(0, len(texts), 500):
        n_tok += [len(x) for x in
                  tok(texts[b:b + 500], add_special_tokens=False)["input_ids"]]
    y = dump["sound_negative"].to_numpy()
    p = dump["pred"].to_numpy()
    chars = dump["len_chars"].to_numpy()

    lines = ["# 长度分桶评估报告（length_bucket_eval.md，tokenizer 口径）", "",
             "口径：冻结模型 + val_v2（20,000 条），阈值 0.9744，"
             "按 **tokenizer token 数**分桶（不含特殊 token）。"
             "模型输入含 [CLS]/[SEP] 且 max_len=128，"
             "故 >128 token 桶 = 推理时被截断的评论。"
             "本报告取代旧字符口径版本（旧版只测了 128 字符 ≈ 30 token 的分界，"
             "不能作为截断影响已评估的证据）。", ""]
    for name, lo, hi in BUCKETS:
        m = (pd.Series(n_tok) >= lo) & (pd.Series(n_tok) <= hi)
        yb, pb = y[m], p[m]
        p_, r_, f1, _ = precision_recall_fscore_support(
            yb, pb, average="binary", zero_division=0)
        tp = int(((yb == 1) & (pb == 1)).sum())
        fp = int(((yb == 0) & (pb == 1)).sum())
        fn = int(((yb == 1) & (pb == 0)).sum())
        tn = int(((yb == 0) & (pb == 0)).sum())
        acc = (tp + tn) / len(yb)
        lines += [
            f"## {name}（n={len(yb)}，正例 {int(yb.sum())}，"
            f"占比 {len(yb)/len(va)*100:.1f}%）",
            "",
            f"- Acc={acc:.4f}  Precision={p_:.4f}  Recall={r_:.4f}  F1={f1:.4f}",
            f"- TP={tp}  FP={fp}  FN={fn}  TN={tn}",
            f"- 模型判正率：{pb.mean()*100:.2f}%（真实正例率 {yb.mean()*100:.2f}%）",
            "",
        ]

    over128t = sum(1 for x in n_tok if x > 128)
    old_char_over = sum(1 for x in chars if x > 128)
    cross = sum(1 for x, c in zip(n_tok, chars) if x > 128 and c > 128)
    lines += [
        "## 旧字符口径的覆盖性对照（如实记录）",
        "",
        f"- 全量中 >128 token 的评论：{over128t}/{len(n_tok)} "
        f"（{over128t/len(n_tok)*100:.2f}%）",
        f"- 旧口径 >128 字符桶共 {old_char_over} 条，其中真正 >128 token 的仅 "
        f"{cross} 条（{cross/max(old_char_over,1)*100:.1f}%）——"
        f"字符口径把绝大部分未触及截断线的评论混进了\"长评\"桶。",
        "",
        "结论：>128 token 桶才是 max_len=128 截断的真实暴露面；"
        "其性能（见上表）即为截断风险的实测证据。", ""]
    text = "\n".join(lines)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
