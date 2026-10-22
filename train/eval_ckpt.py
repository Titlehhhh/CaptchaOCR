"""Evaluate a trained checkpoint on whole types, with an optional band correction.

    .venv-gpu\\Scripts\\python.exe train\\eval_ckpt.py --ckpt train\\run\\foldA\\ckpt\\step_*.pt \
        --types "CaptchaVerifyZ/map" "haq/mapcha/map" --out reports\\eval_foldA.json

What it adds over the trainer's own validation:

* it can evaluate **any** checkpoint on **any** type, including the types the run
  was not trained on;
* it can widen the band by N pixels (`--band-pad N`), which is how the broken band
  of `Archy-X/Krypton/map` is measured: the generator draws the glyphs with a one
  pixel gap between them and the band forgot to count those gaps, so the last
  character falls outside the rectangle;
* it can reproduce the benchmark's test set exactly (13 types x the first 8
  samples), so our model and the measured baselines are scored on the same items.
"""

import argparse
import json
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from captcha_crnn import (CHARSET, CaptchaDataset, CRNN, build_encoder, build_items, cer,
                          collate, find_types, greedy_decode, read_labels)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIRS = [os.path.join(REPO, "dataset", "out"), os.path.join(REPO, "dataset", "out_ru")]

# The test set of the benchmark harnesses: bench/bench_hf.py::TEXT_TYPES, the
# first 8 samples of each, scored against `answer`.
BENCH_TYPES = [
    "Archy-X/Krypton/map",
    "InstantlyMoist/Captcha/textcaptcha",
    "JSH32/Minecaptcha/map",
    "haq/mapcha/map",
    "LagBug/XProtect/code",
    "LagBug/XProtect/map",
    "irootdev/AnBot/captcha",
    "jonesdevelopment/sonar/standard",
    "jSdCool/minecaptcha/text",
    "just-captcha/ProstoCaptcha/map",
    "laforetbrut/are-you-sure/code",
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA/map",
    "n1zamu/NCaptcha/anvil",
]


def widen(roi, n):
    """The band, widened by n pixels on the right (and on the left for symmetry)."""
    if not roi:
        return roi
    x, y, w, h = roi
    return [max(0, x - n), y, w + 2 * n, h]


def load_model(ckpt_path, device="cuda"):
    state = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    cs = build_encoder(CHARSET)
    model = CRNN(cs.num_classes)
    model.load_state_dict(state["model"])
    model.to(device).eval()
    return model, cs, state


def evaluate(model, cs, items, device="cuda", batch_size=64):
    ds = CaptchaDataset(items, cs.encode, augment=False)
    loader = torch.utils.data.DataLoader(ds, batch_size=batch_size, shuffle=False,
                                         collate_fn=collate, num_workers=4)
    per_type = {}
    ex = 0
    n = 0
    cer_sum = 0.0
    conf_sum = 0.0
    preds_all = []
    with torch.no_grad():
        for batch in loader:
            logits, t = model(batch["images"].to(device))
            preds = greedy_decode(logits.float().cpu(), cs.decode)
            offset = 0
            for i, (pred, conf) in enumerate(preds):
                gold = batch["labels"][offset:offset + int(batch["lengths"][i])]
                gold_text = cs.decode(gold.tolist())
                typ = batch["types"][i]
                d = per_type.setdefault(typ, {"n": 0, "exact": 0, "cer": 0.0, "conf": 0.0,
                                              "samples": []})
                d["n"] += 1
                if pred == gold_text:
                    d["exact"] += 1
                c = cer(pred, gold_text)
                if c is not None:
                    d["cer"] += c
                d["conf"] += conf
                conf_sum += conf
                d["samples"].append({"file": os.path.basename(items[batch["indices"][i]]["path"]),
                                     "gold": gold_text, "pred": pred, "cer": c,
                                     "conf": round(conf, 4)})
                preds_all.append({"type": typ, "file": os.path.basename(items[batch["indices"][i]]["path"]),
                                  "gold": gold_text, "pred": pred, "cer": c,
                                  "conf": round(conf, 4)})
                offset += int(batch["lengths"][i])
                ex += int(pred == gold_text)
                cer_sum += c or 0.0
                n += 1
    for d in per_type.values():
        d["accuracy"] = d["exact"] / max(1, d["n"])
        d["cer"] = d["cer"] / max(1, d["n"])
        d["confidence"] = d["conf"] / max(1, d["n"])
    overall = {"n": n, "accuracy": ex / max(1, n), "cer": cer_sum / max(1, n),
               "confidence": conf_sum / max(1, n)}
    return {"overall": overall, "per_type": per_type}, preds_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--types", nargs="*", default=None)
    ap.add_argument("--bench-testset", action="store_true",
                    help="the 13 types x 8 samples of bench/bench_hf.py")
    ap.add_argument("--band-pad", type=int, default=0,
                    help="widen every band by N pixels on each side")
    ap.add_argument("--limit-per-type", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    wanted = args.types
    if args.bench_testset:
        wanted = BENCH_TYPES
    types = [(t, d) for t, d, _r in find_types(OUT_DIRS, wanted=wanted)]
    if not types:
        print("no types matched", file=sys.stderr)
        return 1

    model, cs, state = load_model(args.ckpt, args.device)
    print(f"checkpoint {args.ckpt} (step {state.get('step')}, epoch {state.get('epoch')})")
    print(f"types: {', '.join(t for t, _ in types)}")

    items = build_items(types, limit_per_type=args.limit_per_type)
    if args.band_pad:
        for it in items:
            it["roi"] = widen(it["roi"], args.band_pad)
    report, preds = evaluate(model, cs, items, device=args.device)
    for typ, d in sorted(report["per_type"].items()):
        print(f"  {typ:52s} acc {d['accuracy']:.3f}  cer {d['cer']:.3f}  n={d['n']}")
    o = report["overall"]
    print(f"  OVERALL n={o['n']} acc {o['accuracy']:.3f} cer {o['cer']:.3f}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"checkpoint": args.ckpt, "step": state.get("step"),
                       "band_pad": args.band_pad, "report": report, "preds": preds},
                      f, ensure_ascii=False, indent=1)
        print(f"written {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
