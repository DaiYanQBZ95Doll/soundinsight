# -*- coding: utf-8 -*-
# qwen 对照指标计算：合并 llm_qwen_out_*.jsonl，与 ground truth 打分，
# 与 deepseek 结果并排输出，供 llm_baseline.md 更新使用。
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))


def load_jsonl(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            out[o["id"]] = o
    return out


def merge(files):
    out = {}
    for p in files:
        out.update(load_jsonl(os.path.join(HERE, p)))
    return out


def score(labels, verdicts, ids):
    tp = fp = tn = fn = 0
    for i in ids:
        y = labels[i]["label"]
        v = verdicts.get(i, {}).get("verdict")
        if v is None:
            continue
        if y == 1 and v == 1:
            tp += 1
        elif y == 1 and v == 0:
            fn += 1
        elif y == 0 and v == 1:
            fp += 1
        else:
            tn += 1
    n = tp + fp + tn + fn
    acc = (tp + tn) / n if n else 0.0
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return dict(n=n, tp=tp, fp=fp, tn=tn, fn=fn, acc=acc, p=p, r=r, f1=f1)


def main() -> None:
    labels = load_jsonl(os.path.join(HERE, "llm_eval_input.jsonl"))
    ids = sorted(labels.keys())
    modes = {
        "zero": ["llm_qwen_out_zero_0.jsonl", "llm_qwen_out_zero_1.jsonl",
                 "llm_qwen_out_zero_2.jsonl", "llm_qwen_out_zero_3.jsonl"],
        "5shot": ["llm_qwen_out_5shot_0.jsonl", "llm_qwen_out_5shot_1.jsonl",
                  "llm_qwen_out_5shot_2.jsonl", "llm_qwen_out_5shot_3.jsonl"],
        "review": ["llm_qwen_out_review_0.jsonl", "llm_qwen_out_review_1.jsonl",
                   "llm_qwen_out_review_2.jsonl", "llm_qwen_out_review_3.jsonl"],
    }
    tokens = {"zero": 155514, "5shot": 171146, "review": 164087}
    small = {}
    with open(os.path.join(HERE, "llm_eval_small_preds.jsonl"),
              encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            small[o["id"]] = o["pred"]
    out = {"small": score(labels, {i: {"verdict": v} for i, v in
                                   small.items()}, ids)}
    for mode, files in modes.items():
        v = merge(files)
        assert len(v) == len(ids), f"{mode}: {len(v)}/{len(ids)}"
        r = score(labels, v, ids)
        changes = sum(1 for i in ids if v[i]["verdict"] != small[i])
        out[mode] = dict(r=r, changes=changes, tokens=tokens[mode])
        print(f"{mode}: n={r['n']} tp={r['tp']} fp={r['fp']} fn={r['fn']} "
              f"tn={r['tn']} acc={r['acc']:.4f} P={r['p']:.4f} "
              f"R={r['r']:.4f} F1={r['f1']:.4f} "
              f"changed_vs_small={changes} ({changes/len(ids)*100:.1f}%) "
              f"tokens={tokens[mode]}")
    with open(os.path.join(HERE, "llm_qwen_metrics.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("saved llm_qwen_metrics.json")


if __name__ == "__main__":
    main()
