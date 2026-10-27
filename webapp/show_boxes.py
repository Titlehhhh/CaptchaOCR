#!/usr/bin/env python
"""Draw the cropper's rectangle on the frames it was given.

    .venv-gpu\\Scripts\\python.exe webapp\\show_boxes.py --out reports\\cropper\\boxes.png

Left: the frame as it arrived, with the band the cropper chose drawn on it.
Right: that band, cropped and enlarged - what the recogniser actually reads.

The rectangle that is drawn is the **winning proposal** - the band the
recogniser was most confident about, after the cropper proposed its candidates
and the model voted.  That is what the web app does; the purely geometric box
of `cropper.crop()` is a different thing and is not always the right one.

The frames are the owner's six real screenshots (`test/*.png`, the file name is
the code) and a few samples of the dataset types.
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".hf-cache"))
os.environ.setdefault("HF_HUB_CACHE", os.path.join(ROOT, ".hf-cache", "hub"))

import cropper                                          # noqa: E402
import app as webapp                                    # noqa: E402

TEST_DIR = os.path.join(ROOT, "test")
DATASET = os.path.join(ROOT, "dataset", "out_ru", "LimboFilter", "digits")


def draw(img, box, colour=(255, 0, 0), width=4):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    if box:
        x, y, w, h = box
        d.rectangle([x, y, x + w, y + h], outline=colour, width=width)
    return img


def tile(img, box, title, crop_w=440):
    from PIL import Image, ImageDraw
    left = img.copy()
    draw(left, box)
    th = int(crop_w * left.height / left.width)
    left = left.resize((crop_w, th), Image.LANCZOS)
    if box:
        x, y, w, h = box
        band = img.crop((x, y, x + w, y + h))
    else:
        band = img
    bh = int(crop_w * band.height / max(1, band.width))
    band = band.resize((crop_w, max(1, bh)), Image.LANCZOS)
    row = Image.new("RGB", (crop_w * 2 + 12, max(th, band.height) + 22), (16, 16, 18))
    d = ImageDraw.Draw(row)
    d.text((4, 5), title, fill=(255, 220, 90))
    row.paste(left, (0, 20))
    row.paste(band, (crop_w + 12, 20))
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "reports", "cropper", "boxes.png"))
    ap.add_argument("--dataset-n", type=int, default=4)
    args = ap.parse_args()

    from PIL import Image, ImageDraw

    # the same model and the same vote as the web app
    path, kind = webapp.resolve_checkpoint()
    backend = webapp.PPOCRBackend(path, "cuda")
    print("model: %s (%d classes)" % (backend.name, backend.info.get("classes", 0)))

    rows = []
    for p in sorted(glob.glob(os.path.join(TEST_DIR, "*.png"))):
        name = os.path.basename(p)
        img = Image.open(p).convert("RGB")
        res, meta = webapp.App._vote_standalone(backend, img) if hasattr(webapp.App, "_vote_standalone") \
            else (None, None)
        if res is None:
            res, meta = vote_with_backend(backend, img)
        rows.append(tile(img, meta["crop_box"],
                         "%s  ->  %s   box=%s   method=%s   conf=%s"
                         % (name, res["text"], meta["crop_box"], meta["crop_method"],
                            res["confidence"])))

    for p in sorted(glob.glob(os.path.join(DATASET, "*.png")))[:args.dataset_n]:
        name = "dataset/LimboFilter/digits/" + os.path.basename(p)
        img = Image.open(p).convert("RGB")
        res, meta = vote_with_backend(backend, img)
        rows.append(tile(img, meta["crop_box"],
                         "%s   box=%s   method=%s   ->  %s"
                         % (name, meta["crop_box"], meta["crop_method"], res["text"])))

    W = max(r.width for r in rows)
    H = sum(r.height for r in rows)
    sheet = Image.new("RGB", (W, H), (10, 10, 12))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    sheet.save(args.out)
    print("written %s  (%dx%d)" % (args.out, sheet.width, sheet.height))
    return 0


def vote_with_backend(backend, img):
    """The app's rule: the cropper proposes, the recogniser votes."""
    from PIL import Image
    cands = cropper.candidates(img, limit=32)
    votes, tried = {}, []
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
                                            "method": c.method, "box": c.box, "result": res})
        v["votes"] += 1
        if res["confidence"] > v["confidence"]:
            v["confidence"] = res["confidence"]
            v["method"] = c.method
            v["box"] = c.box
            v["result"] = res
    best = max(votes.values(), key=lambda v: (v["confidence"], v["votes"]))
    meta = {"crop_method": best["method"], "crop_box": best["box"],
            "crop_votes": best["votes"], "crop_candidates": len(tried)}
    return best["result"], meta


if __name__ == "__main__":
    sys.exit(main())
