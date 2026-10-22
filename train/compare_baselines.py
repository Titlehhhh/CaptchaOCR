"""Compare a measured baseline with our model on the same items.

    .venv-gpu\\Scripts\\python.exe train\\compare_baselines.py --ckpt train\\run\\foldA\\ckpt\\step_*.pt

The baselines are not re-run: their predictions are already saved in
`reports/bench_results*.json`, so the same items can be re-scored here.

Two things have to be kept apart, and this script keeps them apart:

* **the input**: `bench/bench_others.py` and `bench/bench_onnx.py` crop by the
  `roi` band, `bench/bench_hf.py` does NOT (it calls `load_image(path)` without
  the band, `bench/bench_hf.py:136` called from `:174`). A model measured on the
  band and a model measured on the whole frame are not comparable;
* **the item set**: the benchmark test set is 13 types x 8 samples, and 5 of
  those 13 types have no band at all - for them "cropped" and "uncropped" are
  the same thing.

The script therefore prints the numbers for the whole test set and for the band
types alone, for every measured baseline, and then our model on exactly the same
items.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from captcha_crnn import find_types, read_labels
from eval_ckpt import BENCH_TYPES, evaluate, load_model

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(REPO, "reports")

BAND_TYPES = [t for t in BENCH_TYPES if t not in (
    "InstantlyMoist/Captcha/textcaptcha", "LagBug/XProtect/code", "LagBug/XProtect/map",
    "irootdev/AnBot/captcha", "jonesdevelopment/sonar/standard")]


def norm(s):
    if s is None:
        return ""
    s = str(s).strip()
    return re.sub(r"[^A-Za-z0-9+\-*]", "", s)


def lev(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def score(pred, gold):
    p, g = norm(pred), norm(gold)
    if not g:
        return None
    return lev(p, g) / len(g)


def load_baselines():
    out = {}
    for name in ("bench_results.json", "bench_results_others.json", "bench_results_onnx.json"):
        path = os.path.join(REPORTS, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for mid, rec in data.items():
            if not isinstance(rec, dict) or not rec.get("ok"):
                continue
            out[mid] = {"file": name, "preds": rec.get("preds", []),
                        "accuracy": rec.get("accuracy"), "mean_cer": rec.get("mean_cer"),
                        "n": rec.get("n")}
    return out


def rescore(preds, types=None):
    ex = 0
    n = 0
    cer = 0.0
    for p in preds:
        if types is not None and p["type"] not in types:
            continue
        c = score(p.get("pred"), p.get("gold"))
        if c is None:
            continue
        n += 1
        cer += c
        ex += int(norm(p.get("pred")) == norm(p.get("gold")))
    return {"n": n, "accuracy": ex / max(1, n), "cer": cer / max(1, n)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = []
    for mid, rec in load_baselines().items():
        full = rescore(rec["preds"])
        band = rescore(rec["preds"], set(BAND_TYPES))
        rows.append({"model": mid, "source": rec["file"], "input": "band" if "others" in rec["file"]
                     or "onnx" in rec["file"] else "whole frame",
                     "n_all": full["n"], "acc_all": full["accuracy"], "cer_all": full["cer"],
                     "n_band": band["n"], "acc_band": band["accuracy"], "cer_band": band["cer"],
                     "as_measured_acc": rec["accuracy"], "as_measured_cer": rec["mean_cer"]})
    rows.sort(key=lambda r: -r["acc_band"])
    print(f"{'model':52s} {'input':11s} {'all104':>8s} {'acc':>6s} {'cer':>6s} | "
          f"{'band64':>7s} {'acc':>6s} {'cer':>6s}")
    for r in rows:
        print(f"{r['model']:52s} {r['input']:11s} {r['n_all']:8d} {r['acc_all']:6.3f} "
              f"{r['cer_all']:6.3f} | {r['n_band']:7d} {r['acc_band']:6.3f} {r['cer_band']:6.3f}")

    if args.ckpt:
        model, cs, state = load_model(args.ckpt)
        roots = [os.path.join(REPO, "dataset", "out"), os.path.join(REPO, "dataset", "out_ru")]
        from captcha_crnn import build_items
        types = [(t, d) for t, d, _r in find_types(roots, wanted=BENCH_TYPES)]
        items = build_items(types, limit_per_type=8)
        report, preds = evaluate(model, cs, items)
        ours = rescore([{"type": p["type"], "pred": p["pred"], "gold": p["gold"]} for p in preds])
        ours_band = rescore([{"type": p["type"], "pred": p["pred"], "gold": p["gold"]}
                              for p in preds], set(BAND_TYPES))
        print(f"\nours ({os.path.basename(args.ckpt)}):")
        print(f"  all {ours['n']:3d} items: acc {ours['accuracy']:.3f}  cer {ours['cer']:.3f}")
        print(f"  band types {ours_band['n']:3d} items: acc {ours_band['accuracy']:.3f}  "
              f"cer {ours_band['cer']:.3f}")
        for t, d in sorted(report["per_type"].items()):
            print(f"      {t:46s} acc {d['accuracy']:.3f}  cer {d['cer']:.3f}  n={d['n']}")
        rows.append({"model": "OURS " + os.path.basename(args.ckpt), "source": "this run",
                     "input": "band (glyph 32px)", "n_all": ours["n"], "acc_all": ours["accuracy"],
                     "cer_all": ours["cer"], "n_band": ours_band["n"], "acc_band": ours_band["accuracy"],
                     "cer_band": ours_band["cer"]})
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print(f"\nwritten {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
