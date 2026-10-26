"""Our model against the measured baselines, per type, on the benchmark's own items.

    .venv-gpu\\Scripts\\python.exe train\\bench_per_type.py --runs train\\run\\foldA train\\run\\foldB ...

The benchmark test set is 13 types x the first 8 samples. For every type the
model is scored with the checkpoint of the fold in which that type was **held
out** - so the model has never seen the type it is scored on, which is the only
honest way to compare it with a zero-shot baseline. The baselines are re-scored
from their saved predictions, on exactly the same items.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from captcha_crnn import build_items, find_types
from compare_baselines import BENCH_TYPES, BAND_TYPES, load_baselines, rescore
from eval_ckpt import evaluate, load_model

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIRS = [os.path.join(REPO, "dataset", "out"), os.path.join(REPO, "dataset", "out_ru")]


def newest_ckpt(run_dir):
    ck = os.path.join(run_dir, "ckpt")
    if not os.path.isdir(ck):
        return None
    files = sorted(f for f in os.listdir(ck) if f.startswith("step_") and f.endswith(".pt"))
    return os.path.join(ck, files[-1]) if files else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    held = {}
    ckpts = {}
    for run in args.runs:
        path = newest_ckpt(run)
        if not path:
            print(f"[skip] no checkpoint in {run}")
            continue
        import torch
        state = torch.load(path, map_location="cpu", weights_only=False)
        val = state.get("args", {}).get("val_types") or []
        ckpts[run] = path
        for t in val:
            held[t] = run
    print("held out per run:")
    for t, r in sorted(held.items()):
        print(f"  {t:52s} {r}")

    baselines = load_baselines()
    rows = []
    ours = {}
    for t in BENCH_TYPES:
        if t not in BAND_TYPES:
            continue
        run = held.get(t)
        if not run:
            print(f"[skip] {t}: no run held it out")
            continue
        model, cs, _ = load_model(ckpts[run])
        types = [(t, d) for t2, d, _r in find_types(OUT_DIRS, wanted=[t])]
        items = build_items(types, limit_per_type=8)
        report, preds = evaluate(model, cs, items)
        v = report["per_type"][t]
        scored = rescore([{"type": p["type"], "pred": p["pred"], "gold": p["gold"]} for p in preds])
        ours[t] = {"run": run, "acc": scored["accuracy"], "cer": scored["cer"], "n": scored["n"],
                   "per_type_acc": v["accuracy"], "per_type_cer": v["cer"]}
        print(f"  ours {t:50s} acc {scored['accuracy']:.3f} cer {scored['cer']:.3f} n={scored['n']}")

    print("\nper type, the same 8 items, every model:")
    head = f"{'type':50s} {'ours':>6s} {'cer':>6s} |"
    for mid in baselines:
        head += f" {mid.split('/')[-1][:14]:>15s}"
    print(head)
    table = []
    for t in BAND_TYPES:
        if t not in ours:
            continue
        line = f"{t:50s} {ours[t]['acc']:6.3f} {ours[t]['cer']:6.3f} |"
        row = {"type": t, "ours": ours[t]}
        for mid, rec in baselines.items():
            sub = rescore([p for p in rec["preds"] if p["type"] == t])
            line += f" {sub['accuracy']:6.3f}/{sub['cer']:5.3f}"
            row[mid] = sub
        print(line)
        table.append(row)

    all_ours = {"type": "__all__", "pred": None, "gold": None}
    ours_rows = []
    for t, o in ours.items():
        ours_rows.append({"type": t, "acc": o["acc"], "cer": o["cer"], "n": o["n"]})
    n = sum(o["n"] for o in ours_rows)
    acc = sum(o["acc"] * o["n"] for o in ours_rows) / max(1, n)
    cer = sum(o["cer"] * o["n"] for o in ours_rows) / max(1, n)
    print(f"\nOURS  band items n={n}  acc {acc:.3f}  cer {cer:.3f}")
    for mid, rec in baselines.items():
        s = rescore(rec["preds"], set(BAND_TYPES))
        print(f"  {mid:52s} n={s['n']} acc {s['accuracy']:.3f} cer {s['cer']:.3f}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"ours": ours, "per_type": table,
                       "ours_total": {"n": n, "accuracy": acc, "cer": cer}}, f,
                      ensure_ascii=False, indent=1)
        print(f"written {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
