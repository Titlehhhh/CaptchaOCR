#!/usr/bin/env python
"""Measure the cropper: the band it finds, and what the model reads with it.

    .venv-gpu\\Scripts\\python.exe webapp\\eval_cropper.py --selftest
    .venv-gpu\\Scripts\\python.exe webapp\\eval_cropper.py --demo-sweep
    .venv-gpu\\Scripts\\python.exe webapp\\eval_cropper.py --out reports\\cropper\\eval_cropper.json

Three measurements, all with the same model and the same preprocessing as the
web app (`webapp/app.py`):

  (A) the owner's six real screenshots (`test/*.png`).  The file name **is**
      the code inside the picture, so the gold label is the file name.  The
      cropper runs on the whole frame; the model reads the band it proposes.

  (B) the dataset: a seeded random sample from `dataset/out` and
      `dataset/out_ru`.  Three inputs are compared on the same samples:
        * `oracle` - the band of `labels.jsonl` (the ceiling of the model);
        * `cropper`- the band the cropper finds in the whole frame;
        * `frame`  - the whole frame (the old `ink_bbox` fallback).
      The predictions are compared against **both** `answer` and `text`: they
      differ in 9 of the 46 types (arithmetic, Russian number words, the
      reversed string), and for those a recogniser that reads `text` cannot
      match `answer` by construction - that is the solver's step, not the
      cropper's failure.

  (C) the demo sweep - the 10 demo types x 3 pictures of the web app, read
      with the band of `labels.jsonl`.  It must stay at 30/30: that is the
      path that already worked, and the cropper must not break it.
"""

import argparse
import glob
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".hf-cache"))
os.environ.setdefault("HF_HUB_CACHE", os.path.join(ROOT, ".hf-cache", "hub"))

import app as webapp                                     # noqa: E402
import cropper                                          # noqa: E402

TEST_DIR = os.path.join(ROOT, "test")
DATA_ROOTS = [os.path.join(ROOT, "dataset", "out"),
              os.path.join(ROOT, "dataset", "out_ru")]


def norm(s):
    """The comparison form of a string (letters, digits, arithmetic signs)."""
    if s is None:
        return ""
    return "".join(ch for ch in str(s) if ch.isalnum() or ch in "+-*/=")


def load_model(device="cuda"):
    path, kind = webapp.resolve_checkpoint()
    if not path:
        raise SystemExit("no checkpoint at %s" % webapp.DEFAULT_CHECKPOINT)
    if kind == "ppocr":
        return webapp.PPOCRBackend(path, device)
    return webapp.CRNNBackend(path, device)


# --------------------------------------------------------------------------- #
# (A) the owner's real screenshots
# --------------------------------------------------------------------------- #
def run_screenshots(backend, verbose=True):
    rows = []
    files = sorted(glob.glob(os.path.join(TEST_DIR, "*.png")))
    for path in files:
        name = os.path.basename(path)
        gold = os.path.splitext(name)[0]
        from PIL import Image
        img = Image.open(path).convert("RGB")
        t0 = time.perf_counter()
        cands = cropper.candidates(img, limit=32)
        res, meta = vote(backend, img, cands)
        dt = (time.perf_counter() - t0) * 1000
        row = {"file": name, "gold": gold, "pred": res["text"],
               "confidence": res["confidence"], "exact": norm(res["text"]) == norm(gold),
               "method": meta["crop_method"], "box": meta["crop_box"],
               "votes": meta["crop_votes"], "candidates": meta["crop_candidates"],
               "size": list(img.size), "ms": round(dt, 1)}
        rows.append(row)
        if verbose:
            print("  %-12s gold=%-6s pred=%-8s conf=%.3f  %-28s %s  (%d votes, %d cands, %.0fms)"
                  % (name, gold, row["pred"], row["confidence"], row["method"],
                     "OK " if row["exact"] else "MISS", row["votes"],
                     row["candidates"], row["ms"]))
    n_ok = sum(1 for r in rows if r["exact"])
    print("  screenshots: %d/%d exact" % (n_ok, len(rows)))
    return rows


# --------------------------------------------------------------------------- #
# the vote (the same rule as the web app)
# --------------------------------------------------------------------------- #
def vote(backend, img, cands):
    from PIL import Image
    votes = {}
    tried = []
    for c in cands:
        if c.image is not None:
            view = Image.fromarray(c.image)
            res = backend.predict(view, [0, 0, view.width, view.height])
        elif c.box:
            res = backend.predict(img, c.box)
        else:
            res = backend.predict(img, None)
        tried.append({"method": c.method, "box": c.box, "text": res["text"],
                      "confidence": res["confidence"]})
        v = votes.setdefault(res["text"], {"votes": 0, "confidence": 0.0,
                                            "method": c.method, "box": c.box,
                                            "result": res})
        v["votes"] += 1
        if res["confidence"] > v["confidence"]:
            v["confidence"] = res["confidence"]
            v["method"] = c.method
            v["box"] = c.box
            v["result"] = res
    best = max(votes.values(), key=lambda v: (v["confidence"], v["votes"]))
    meta = {"crop_method": best["method"], "crop_box": best["box"],
            "crop_votes": best["votes"], "crop_candidates": len(tried),
            "crop_tried": tried, "crop_alternatives": len(votes)}
    return best["result"], meta


# --------------------------------------------------------------------------- #
# (B) the dataset
# --------------------------------------------------------------------------- #
def read_types():
    """Every type of the two trees, with its rows."""
    out = []
    for root in DATA_ROOTS:
        if not os.path.isdir(root):
            continue
        tree = os.path.basename(os.path.normpath(root))
        for dirpath, _dirs, files in os.walk(root):
            if "labels.jsonl" not in files:
                continue
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            type_id = "%s/%s" % (tree, rel)
            rows = []
            with open(os.path.join(dirpath, "labels.jsonl"), encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    r["_abs"] = os.path.abspath(os.path.join(dirpath, r["file"]))
                    rows.append(r)
            out.append((type_id, dirpath, rows))
    out.sort()
    return out


def learn_type_bands(ds):
    """The relative band of every type that has one (the median band of the
    type, normalised by the frame) - the same table the web app builds."""
    import statistics

    bands = {}
    for t in ds.types:
        rel = []
        for r in ds.by_type.get(t["id"]) or []:
            roi = r.get("roi")
            w = r.get("width") or 0
            h = r.get("height") or 0
            if not roi or not w or not h:
                continue
            x, y, bw, bh = [float(v) for v in roi]
            rel.append((x / w, y / h, bw / w, bh / h))
        if rel:
            bands[t["id"]] = [round(statistics.median(v), 6) for v in zip(*rel)]
    return bands


def run_dataset(backend, n_per_type=40, seed=1234, limit_types=None, verbose=True,
                learned=False):
    from PIL import Image
    rng = random.Random(seed)
    ds = webapp.Dataset(DATA_ROOTS)
    cropper.set_type_bands(learn_type_bands(ds) if learned else {})
    per_type = {}
    for type_id, dirpath, rows in read_types():
        if limit_types and not any(t in type_id for t in limit_types):
            continue
        sample = rows if len(rows) <= n_per_type else rng.sample(rows, n_per_type)
        stat = {"n": 0, "n_roi": 0,
                "oracle_answer": 0, "cropper_answer": 0, "frame_answer": 0,
                "oracle_text": 0, "cropper_text": 0, "frame_text": 0,
                "text_ne_answer": 0, "methods": {}}
        for r in sample:
            img = Image.open(r["_abs"]).convert("RGB")
            answer = r.get("answer") or ""
            text = r.get("text") or ""
            stat["n"] += 1
            stat["n_roi"] += 1 if r.get("roi") else 0
            if norm(text) != norm(answer):
                stat["text_ne_answer"] += 1
            # oracle: the band of labels.jsonl
            if r.get("roi"):
                o = backend.predict(img, r["roi"])
            else:
                o = backend.predict(img, None)     # no band -> the whole frame
            # cropper
            cands = cropper.candidates(img, type_id=type_id, limit=32)
            cres, meta = vote(backend, img, cands)
            # the old fallback: the whole frame
            f = backend.predict(img, None)
            stat["oracle_answer"] += norm(o["text"]) == norm(answer)
            stat["cropper_answer"] += norm(cres["text"]) == norm(answer)
            stat["frame_answer"] += norm(f["text"]) == norm(answer)
            stat["oracle_text"] += norm(o["text"]) == norm(text)
            stat["cropper_text"] += norm(cres["text"]) == norm(text)
            stat["frame_text"] += norm(f["text"]) == norm(text)
            m = meta["crop_method"].split(":")[0]
            stat["methods"][m] = stat["methods"].get(m, 0) + 1
        per_type[type_id] = stat
        if verbose:
            print("  %-52s n=%-4d oracle %.3f  cropper %.3f  frame %.3f   (answer)"
                  % (type_id, stat["n"], stat["oracle_answer"] / max(1, stat["n"]),
                     stat["cropper_answer"] / max(1, stat["n"]),
                     stat["frame_answer"] / max(1, stat["n"])))
    return per_type


def aggregate(per_type, key):
    """Per tree and overall, against `answer` and against `text`."""
    out = {}
    for tree in ("out", "out_ru"):
        rows = [v for k, v in per_type.items() if k.startswith(tree + "/")]
        if not rows:
            continue
        n = sum(r["n"] for r in rows)
        out[tree] = {
            "types": len(rows), "n": n,
            "oracle": sum(r["oracle_" + key] for r in rows) / max(1, n),
            "cropper": sum(r["cropper_" + key] for r in rows) / max(1, n),
            "frame": sum(r["frame_" + key] for r in rows) / max(1, n),
            "median_oracle": median([r["oracle_" + key] / max(1, r["n"]) for r in rows]),
            "median_cropper": median([r["cropper_" + key] / max(1, r["n"]) for r in rows]),
            "median_frame": median([r["frame_" + key] / max(1, r["n"]) for r in rows]),
        }
    allrows = list(per_type.values())
    n = sum(r["n"] for r in allrows)
    out["all"] = {
        "types": len(allrows), "n": n,
        "oracle": sum(r["oracle_" + key] for r in allrows) / max(1, n),
        "cropper": sum(r["cropper_" + key] for r in allrows) / max(1, n),
        "frame": sum(r["frame_" + key] for r in allrows) / max(1, n),
        "median_oracle": median([r["oracle_" + key] / max(1, r["n"]) for r in allrows]),
        "median_cropper": median([r["cropper_" + key] / max(1, r["n"]) for r in allrows]),
        "median_frame": median([r["frame_" + key] / max(1, r["n"]) for r in allrows]),
    }
    return out


def median(values):
    values = sorted(values)
    if not values:
        return 0.0
    n = len(values)
    return values[n // 2] if n % 2 else 0.5 * (values[n // 2 - 1] + values[n // 2])


# --------------------------------------------------------------------------- #
# (C) the demo sweep - the path that already worked must not break
# --------------------------------------------------------------------------- #
def run_demo_sweep(backend, verbose=True):
    ds = webapp.Dataset(DATA_ROOTS)
    types = ds.demo_types(10)
    ok = 0
    n = 0
    misses = []
    for type_id in types:
        for row in ds.by_type[type_id][:3]:
            from PIL import Image
            img = Image.open(row["_abs"]).convert("RGB")
            roi = row.get("roi")
            res = backend.predict(img, roi)
            n += 1
            if norm(res["text"]) == norm(row.get("text")):
                ok += 1
            else:
                misses.append((type_id, row["file"], row.get("text"), res["text"]))
    print("  demo sweep: %d/%d exact match" % (ok, n))
    for m in misses:
        print("    MISS %s %s gold=%r pred=%r" % m)
    return {"types": types, "n": n, "exact": ok, "misses": misses}


# --------------------------------------------------------------------------- #
# the cropper alone, without the model
# --------------------------------------------------------------------------- #
def run_selftest(verbose=True):
    from PIL import Image
    rows = []
    for path in sorted(glob.glob(os.path.join(TEST_DIR, "*.png"))):
        img = Image.open(path).convert("RGB")
        t0 = time.perf_counter()
        cands = cropper.candidates(img, limit=32)
        dt = (time.perf_counter() - t0) * 1000
        gold = os.path.splitext(os.path.basename(path))[0]
        rows.append({"file": os.path.basename(path), "gold": gold,
                     "candidates": len(cands),
                     "first": {"box": cands[0].box, "method": cands[0].method},
                     "ms": round(dt, 1)})
        if verbose:
            print("  %-12s %d candidates, first=%s box=%s  (%.0fms)"
                  % (os.path.basename(path), len(cands), cands[0].method,
                     cands[0].box, dt))
    return rows


def main():
    ap = argparse.ArgumentParser(description="measure the cropper")
    ap.add_argument("--selftest", action="store_true", help="the cropper alone, no model")
    ap.add_argument("--demo-sweep", action="store_true", help="the 30-picture regression")
    ap.add_argument("--out", default=None, help="write the measurement as JSON")
    ap.add_argument("--n", type=int, default=40, help="samples per type")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--types", nargs="*", default=None, help="only these types")
    ap.add_argument("--learned-n", type=int, default=10,
                    help="a second sweep with the band learned per type (0 = skip)")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    report = {"checkpoint": webapp.DEFAULT_CHECKPOINT, "seed": args.seed,
              "n_per_type": args.n}

    if args.selftest:
        print("selftest - the cropper alone")
        report["selftest"] = run_selftest()
        if not args.out:
            return 0

    print("loading the model ...")
    backend = load_model(args.device)
    print("  %s, %d classes, device %s" % (backend.name, backend.info.get("classes", 0),
                                            backend.device))

    if args.demo_sweep:
        print("demo sweep (the band of labels.jsonl - must stay 30/30)")
        report["demo_sweep"] = run_demo_sweep(backend)

    print("the owner's screenshots (the file name is the gold)")
    report["screenshots"] = run_screenshots(backend)

    print("the dataset (oracle band / cropper / whole frame)")
    per_type = run_dataset(backend, n_per_type=args.n, seed=args.seed,
                            limit_types=args.types, learned=False)
    report["per_type"] = per_type
    report["answer"] = aggregate(per_type, "answer")
    report["text"] = aggregate(per_type, "text")
    for key in ("answer", "text"):
        print("  --- against `%s` ---" % key)
        for tree, agg in report[key].items():
            print("    %-8s types=%-3d n=%-6d  oracle %.4f  cropper %.4f  frame %.4f"
                  "   | median: oracle %.4f  cropper %.4f  frame %.4f"
                  % (tree, agg["types"], agg["n"], agg["oracle"], agg["cropper"], agg["frame"],
                     agg["median_oracle"], agg["median_cropper"], agg["median_frame"]))

    if args.learned_n:
        print("the dataset again, with the band LEARNED from labels.jsonl per type")
        learned = run_dataset(backend, n_per_type=args.learned_n, seed=args.seed,
                              limit_types=args.types, learned=True, verbose=False)
        report["per_type_learned"] = learned
        report["answer_learned"] = aggregate(learned, "answer")
        for tree, agg in report["answer_learned"].items():
            print("    %-8s types=%-3d n=%-6d  oracle %.4f  cropper %.4f  frame %.4f"
                  % (tree, agg["types"], agg["n"], agg["oracle"], agg["cropper"], agg["frame"]))

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print("written %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

