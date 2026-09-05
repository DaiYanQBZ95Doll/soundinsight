# -*- coding: utf-8 -*-
"""llm_eval_metrics.py — merge LLM verdict files, score against ground truth.

Ground truth labels live in llm_eval_input.jsonl (id/text/label).
Small-model predictions (threshold 0.9744) live in llm_eval_small_preds.jsonl.
LLM verdict files: llm_eval_out_<mode>_*.jsonl  ({id, verdict}).
"""
import json, glob, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))

def load_jsonl(path):
    out = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            out[o['id']] = o
    return out

def load_preds(path):
    out = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            out[o['id']] = o.get('pred')
    return out

def merge_verdicts(files):
    out = {}
    dup = 0
    for path in files:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                i = o['id']
                if i in out:
                    dup += 1
                out[i] = o['verdict']
    return out, dup

def score(labels, verdicts, ids):
    tp = fp = tn = fn = 0
    for i in ids:
        y = labels[i]['label']
        v = verdicts.get(i)
        if v is None:
            continue
        if y == 1 and v == 1: tp += 1
        elif y == 1 and v == 0: fn += 1
        elif y == 0 and v == 1: fp += 1
        else: tn += 1
    n = tp + fp + tn + fn
    acc = (tp + tn) / n if n else 0.0
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return dict(n=n, tp=tp, fp=fp, tn=tn, fn=fn, acc=acc, p=p, r=r, f1=f1)

def main():
    labels = load_jsonl(os.path.join(ROOT, 'llm_eval_input.jsonl'))
    ids = sorted(labels.keys())
    n_pos = sum(1 for i in ids if labels[i]['label'] == 1)
    print(f"total={len(ids)} pos={n_pos} neg={len(ids)-n_pos}")

    small = load_preds(os.path.join(ROOT, 'llm_eval_small_preds.jsonl'))
    assert len(small) == len(ids), f"small preds {len(small)} != {len(ids)}"

    modes = {
        'zero': ['llm_eval_out_zero_0.jsonl', 'llm_eval_out_zero_1.jsonl',
                 'llm_eval_out_zero_2r.jsonl', 'llm_eval_out_zero_3.jsonl'],
        '5shot': ['llm_eval_out_5shot_0.jsonl', 'llm_eval_out_5shot_1.jsonl',
                  'llm_eval_out_5shot_2.jsonl', 'llm_eval_out_5shot_3.jsonl'],
        'review': ['llm_eval_out_review_0.jsonl', 'llm_eval_out_review_1.jsonl',
                   'llm_eval_out_review_2.jsonl', 'llm_eval_out_review_3.jsonl'],
    }
    # token totals recorded from dev_stage_call results (successful calls);
    # one failed zero-shot batch (~50 samples) is not included (see notes in llm_baseline.md)
    tokens = {'zero': 81388, '5shot': 83196, 'review': 85119}

    print("\nsmall model baseline:")
    s = score(labels, small, ids)
    print(f"  n={s['n']} tp={s['tp']} fp={s['fp']} fn={s['fn']} tn={s['tn']} "
          f"acc={s['acc']:.4f} P={s['p']:.4f} R={s['r']:.4f} F1={s['f1']:.4f}")

    results = {}
    for mode, files in modes.items():
        v, dup = merge_verdicts([os.path.join(ROOT, f) for f in files])
        covered = sum(1 for i in ids if i in v)
        assert dup == 0, f"{mode}: {dup} duplicate ids"
        assert covered == len(ids), f"{mode}: covered {covered}/{len(ids)}"
        r = score(labels, v, ids)
        changes = sum(1 for i in ids if v.get(i) != small.get(i))
        results[mode] = (r, changes)
        print(f"\n{mode} (tokens={tokens[mode]}):")
        print(f"  n={r['n']} tp={r['tp']} fp={r['fp']} fn={r['fn']} tn={r['tn']} "
              f"acc={r['acc']:.4f} P={r['p']:.4f} R={r['r']:.4f} F1={r['f1']:.4f} "
              f"changed_vs_small={changes} ({changes/len(ids)*100:.1f}%)")

    with open(os.path.join(ROOT, 'llm_eval_metrics.json'), 'w', encoding='utf-8') as f:
        json.dump({
            'n': len(ids), 'n_pos': n_pos,
            'small': s,
            'zero': dict(r=results['zero'][0], changes=results['zero'][1], tokens=tokens['zero']),
            '5shot': dict(r=results['5shot'][0], changes=results['5shot'][1], tokens=tokens['5shot']),
            'review': dict(r=results['review'][0], changes=results['review'][1], tokens=tokens['review']),
        }, f, ensure_ascii=False, indent=2)
    print("\nsaved llm_eval_metrics.json")

if __name__ == '__main__':
    sys.exit(main())
