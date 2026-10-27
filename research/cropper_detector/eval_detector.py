"""Measure a band detector against the label `roi` and against the served model.

    .venv-gpu\\Scripts\\python.exe build\\cropper_detector\\eval_detector.py --method classical --n 20 --seed 1234
    .venv-gpu\\Scripts\\python.exe build\\cropper_detector\\eval_detector.py --method learned   --n 20 --seed 1234
    .venv-gpu\\Scripts\\python.exe build\\cropper_detector\\eval_detector.py --all             --n 30 --seed 1234

Three columns are measured on the SAME samples with the SAME served model
(`webapp/app.py::PPOCRBackend` + `app.ppocr_prepare`, both imported read-only):

  * oracle   - the label `roi` (the band the model was trained on);
  * detector- the box the detector returns;
  * ink      - the current cropper: `ink_bbox` of the whole frame
                (`app.ppocr_prepare(img, None)` does exactly that).

For a sample whose `roi` is null the frame IS the text, so the "oracle" is the
ink box of the frame (that is what `app.ppocr_prepare(img, None)` crops to) and
the oracle column equals the ink column - the project itself trains and
evaluates those types on the ink crop.
"""

import argparse
import json
import os
import random
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "webapp"))
sys.path.insert(0, HERE)

import app as webapp                      # the web app's own backend (read-only)
from detector import (box_contains, box_iou, classical_detect, ink_bbox,
                      load_json)

DATA_ROOTS = [os.path.join(ROOT, "dataset", "out"),
              os.path.join(ROOT, "dataset", "out_ru")]
SHOT_DIR = os.path.join(ROOT, "test")


# --------------------------------------------------------------------------- #
# dataset
# --------------------------------------------------------------------------- #
def find_types(roots):
    found = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        tag = os.path.basename(os.path.normpath(root))
        for dirpath, _dirs, files in os.walk(root):
            if "labels.jsonl" not in files:
                continue
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            found.append((f"{tag}/{rel}", dirpath))
    return sorted(found)


def read_labels(directory):
    rows = []
    with open(os.path.join(directory, "labels.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def sample_rows(rows, n, rng):
    """A seeded random sample of at most n rows (the rows keep their order)."""
    if n >= len(rows):
        return list(range(len(rows)))
    idx = sorted(rng.sample(range(len(rows)), n))
    return idx


# --------------------------------------------------------------------------- #
# the measurement
# --------------------------------------------------------------------------- #
class Measurer:
    def __init__(self, device="cuda", checkpoint=None):
        ck = checkpoint or webapp.DEFAULT_CHECKPOINT
        self.backend = webapp.PPOCRBackend(webapp._ck(ck), device)
        self.device = device

    def predict(self, img, roi):
        """The served model on one crop; `roi = None` -> the ink crop."""
        try:
            return self.backend.predict(img, roi)
        except RuntimeError as exc:
            if "out of memory" not in str(exc).lower():
                raise
            print("[warn] CUDA OOM -> CPU", file=sys.stderr)
            import torch
            torch.cuda.empty_cache()
            self.backend.device = "cpu"
            self.backend.model.to("cpu")
            self.device = "cpu"
            return self.backend.predict(img, roi)


def norm(s):
    """The project's normalisation (letters, digits, arithmetic operators)."""
    if s is None:
        return ""
    return "".join(ch for ch in str(s) if ch.isalnum() or ch in "+-*/=")


def evaluate_type(tid, directory, n, seed, measurer, methods, rows=None):
    """Measure one type; returns a dict of metrics."""
    all_rows = read_labels(directory)
    rng = random.Random(f"{seed}:{tid}")
    idx = sample_rows(all_rows, n, rng)

    per = {"type": tid, "n": len(idx), "n_roi": 0}
    ious = {m: [] for m in methods}
    contains = {m: [] for m in methods}
    ex = {"oracle": 0, "ink": 0}
    ex_txt = {"oracle": 0, "ink": 0}
    ex_ans = {"oracle": 0, "ink": 0}
    fallbacks = {m: 0 for m in methods}
    dt = {m: [] for m in methods}

    for i in idx:
        r = all_rows[i]
        path = os.path.join(directory, r["file"])
        img = Image.open(path).convert("RGB")
        roi = r.get("roi")
        if roi:
            per["n_roi"] += 1
        ref = roi if roi else ink_bbox(img)     # the ground-truth band

        for m in methods:
            t0 = time.perf_counter()
            box = m["fn"](img)
            dt[m].append((time.perf_counter() - t0) * 1000.0)
            if box is None:
                fallbacks[m] += 1
                box = ink_bbox(img)              # fall back to the current cropper
            ious[m].append(box_iou(box, ref))
            contains[m].append(box_contains(box, ref))

        # --- the three model columns -------------------------------------
        oracle_roi = roi if roi else None
        p_or = measurer.predict(img, oracle_roi)
        p_ink = measurer.predict(img, None)
        ex["oracle"] += int(norm(p_or["text"]) == norm(r.get("answer") or r.get("text")))
        ex_txt["oracle"] += int(norm(p_or["text"]) == norm(r.get("text")))
        ex_ans["oracle"] += int(norm(p_or["text"]) == norm(r.get("answer")))
        ex["ink"] += int(norm(p_ink["text"]) == norm(r.get("answer") or r.get("text")))
        ex_txt["ink"] += int(norm(p_ink["text"]) == norm(r.get("text")))
        ex_ans["ink"] += int(norm(p_ink["text"]) == norm(r.get("answer")))

        for m in methods:
            box = m["fn"](img)
            if box is None:
                box = ink_bbox(img)
            p = measurer.predict(img, box)
            key = m["key"]
            ex[key] = ex.get(key, 0) + int(norm(p["text"]) == norm(r.get("answer") or r.get("text")))
            ex_txt[key] = ex_txt.get(key, 0) + int(norm(p["text"]) == norm(r.get("text")))
            ex_ans[key] = ex_ans.get(key, 0) + int(norm(p["text"]) == norm(r.get("answer")))

    per["iou"] = {m: (float(np.mean(ious[m])), float(np.median(ious[m]))) for m in methods}
    per["contains"] = {m: float(np.mean(contains[m])) for m in methods}
    per["exact"] = {k: (v / max(1, len(idx))) for k, v in ex.items()}
    per["exact_vs_text"] = {k: (v / max(1, len(idx))) for k, v in ex_txt.items()}
    per["exact_vs_answer"] = {k: (v / max(1, len(idx))) for k, v in ex_ans.items()}
    per["fallback"] = fallbacks
    per["ms"] = {m: float(np.median(dt[m])) for m in methods}
    return per


# --------------------------------------------------------------------------- #
# the real screenshots
# --------------------------------------------------------------------------- #
def eval_shots(methods):
    """The 6 owner screenshots: the predicted box and the crop."""
    if not os.path.isdir(SHOT_DIR):
        return []
    out = []
    for name in sorted(os.listdir(SHOT_DIR)):
        if not name.lower().endswith(".png"):
            continue
        code = os.path.splitext(name)[0]
        img = Image.open(os.path.join(SHOT_DIR, name)).convert("RGB")
        row = {"file": name, "code": code, "size": img.size}
        for m in methods:
            box = m["fn"](img)
            row[m["key"]] = box
        out.append(row)
    return out


def make_contact_sheet(methods, path):
    """`crops.png`: the frames with the predicted boxes + the crops."""
    names = sorted(n for n in os.listdir(SHOT_DIR) if n.lower().endswith(".png"))
    rows = []
    for name in names:
        img = Image.open(os.path.join(SHOT_DIR, name)).convert("RGB")
        cells = []
        for m in methods:
            ann = img.copy()
            box = m["fn"](img)
            if box:
                from PIL import ImageDraw
                d = ImageDraw.Draw(ann)
                d.rectangle([box[0], box[1], box[0] + box[2] - 1, box[1] + box[3] - 1],
                            outline=(255, 0, 0), width=3)
            crop = ann.crop(box) if box else ann
            cells.append((ann, crop))
        rows.append((name, cells))
    if not rows:
        return
    cw = max(c[0].width for _, cells in rows for c in cells)
    ch = max(c[0].height for _, cells in rows for c in cells)
    ncol = 1 + 2 * len(methods)
    canvas = Image.new("RGB", (ncol * cw, len(rows) * ch), (25, 25, 25))
    for r, (name, cells) in enumerate(rows):
        for c, (ann, crop) in enumerate(cells):
            canvas.paste(ann, (c * cw, r * ch))
            canvas.paste(crop.resize((cw, ch)), ((1 + 2 * c) * cw, r * ch))
    canvas.save(path)
    print("contact sheet:", path)


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="classical",
                    choices=["classical", "learned", "ink"])
    ap.add_argument("--all", action="store_true",
                    help="measure both detectors")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--types", default="", help="substring filter on the type id")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--shots", action="store_true", help="also run the 6 screenshots")
    ap.add_argument("--out", default=os.path.join(HERE, "eval_result.json"))
    args = ap.parse_args()

    wanted = []
    if args.all:
        wanted = ["classical", "learned"]
    else:
        wanted = [args.method]

    from detector import make_detector
    methods = []
    for name in wanted:
        fn = make_detector(name)
        methods.append({"key": name, "fn": fn, "name": name})

    types = find_types(DATA_ROOTS)
    if args.types:
        types = [t for t in types if args.types in t[0]]

    print(f"types: {len(types)}   methods: {[m['key'] for m in methods]}   n={args.n}  seed={args.seed}")
    measurer = Measurer(device=args.device)

    results = []
    for tid, directory in types:
        t0 = time.time()
        per = evaluate_type(tid, directory, args.n, args.seed, measurer, methods)
        per["seconds"] = round(time.time() - t0, 1)
        results.append(per)
        line = (f"{per['type']:52s} n={per['n']:3d} roi={per['n_roi']:3d} |")
        for m in methods:
            i = per["iou"][m["key"]]
            c = per["contains"][m["key"]]
            e = per["exact"].get(m["key"], 0.0)
            line += (f" {m['key']}: IoU {i[0]:.3f}/{i[1]:.3f} cont {c:.2f} "
                     f"exact {e:.3f} ({per['ms'][m['key']]:.1f}ms) |")
        line += (f" oracle exact {per['exact']['oracle']:.3f}  "
                 f"ink exact {per['exact']['ink']:.3f}")
        print(line, flush=True)

    # ---- totals ----------------------------------------------------------
    print("\n" + "=" * 100)
    print(f"{'TOTAL':52s} n={sum(p['n'] for p in results):4d} roi={sum(p['n_roi'] for p in results):4d}")
    all_ious = {m["key"]: [] for m in methods}
    all_cont = {m["key"]: [] for m in methods}
    tot_exact = {}
    for p in results:
        for m in methods:
            all_ious[m["key"]].append(p["iou"][m["key"]])
            all_cont[m["key"]].append(p["contains"][m["key"]])
    # the exact-match totals have to be re-aggregated over the raw counts
    tot = {}
    for p in results:
        for k, v in p["exact"].items():
            tot[k] = tot.get(k, 0) + v * p["n"]
    ntot = sum(p["n"] for p in results)
    for m in methods:
        mi = float(np.mean([x[0] for x in all_ious[m["key"]]]))
        mmed = float(np.median([x[1] for x in all_ious[m["key"]]]))
        mc = float(np.mean(all_cont[m["key"]]))
        print(f"  {m['key']:10s} band IoU mean {mi:.4f}  median-of-medians {mmed:.4f}  "
              f"contains {mc:.4f}  exact {tot.get(m['key'], 0)/ntot:.4f}")
    print(f"  {'oracle':10s} exact {tot.get('oracle', 0)/ntot:.4f}")
    print(f"  {'ink':10s} exact {tot.get('ink', 0)/ntot:.4f}")

    if args.shots:
        print("\n--- the 6 owner screenshots ---")
        shots = eval_shots(methods)
        for s in shots:
            print(f"  {s['file']:12s} {s['size']} code={s['code']} " +
                  "  ".join(f"{m['key']}={s.get(m['key'])}" for m in methods))
        make_contact_sheet(methods, os.path.join(HERE, "crops.png"))
        results_out = {"types": results, "shots": shots}
    else:
        results_out = {"types": results}

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"args": vars(args), "results": results_out}, f, indent=1, ensure_ascii=False)
    print("\nwritten:", args.out)


if __name__ == "__main__":
    main()
