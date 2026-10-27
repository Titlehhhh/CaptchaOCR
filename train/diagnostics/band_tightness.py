import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from captcha_crnn import find_types, read_labels

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIRS = [os.path.join(REPO, "dataset", "out"), os.path.join(REPO, "dataset", "out_ru")]


def ink_mask(img):
    a = np.asarray(img, dtype=np.float32)
    if a.ndim == 3:
        a = a.mean(axis=2)
    bg = np.bincount(a.astype(np.uint8).ravel(), minlength=256)
    bg_val = int(np.argmax(bg))
    m = np.abs(a - bg_val) > 18
    return m


def margins(m):
    cols = np.where(m.any(axis=0))[0]
    rows = np.where(m.any(axis=1))[0]
    if len(cols) == 0 or len(rows) == 0:
        return None
    return (int(cols[0]), int(m.shape[1] - 1 - cols[-1]),
            int(rows[0]), int(m.shape[0] - 1 - rows[-1]))


def outside_ink(img, roi, pad=2):
    x, y, w, h = roi
    x = max(0, min(x, img.width - 1))
    y = max(0, min(y, img.height - 1))
    w = max(1, min(w, img.width - x))
    h = max(1, min(h, img.height - y))
    m = ink_mask(img)
    left = bool(m[y:y + h, max(0, x - pad):x].any()) if x > 0 else False
    right = bool(m[y:y + h, x + w:min(img.width, x + w + pad)].any()) if x + w < img.width else False
    top = bool(m[max(0, y - pad):y, x:x + w].any()) if y > 0 else False
    bottom = bool(m[y + h:min(img.height, y + h + pad), x:x + w].any()) if y + h < img.height else False
    return left, right, top, bottom


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--types", nargs="*", default=None)
    args = ap.parse_args()
    print(f"{'type':50s} {'n':>4s} {'touchL':>7s} {'touchR':>7s} {'touchT':>7s} "
          f"{'touchB':>7s} {'medL':>5s} {'medR':>5s} {'medH':>5s} | "
          f"{'outL':>5s} {'outR':>5s} {'outT':>5s} {'outB':>5s}")
    for type_id, directory, _root in find_types(OUT_DIRS, wanted=args.types):
        rows = [r for r in read_labels(directory) if r.get("roi")]
        if not rows:
            print(f"{type_id:50s}    -  (no band)")
            continue
        tl = tr = tt = tb = 0
        ol = orr = ot = ob = 0
        ml, mr, mh = [], [], []
        for r in rows:
            x, y, w, h = r["roi"]
            img = Image.open(os.path.join(directory, r["file"])).convert("L")
            x = max(0, min(x, img.width - 1))
            y = max(0, min(y, img.height - 1))
            w = max(1, min(w, img.width - x))
            h = max(1, min(h, img.height - y))
            m = ink_mask(img.crop((x, y, x + w, y + h)))
            mg = margins(m)
            if mg is None:
                continue
            l, rr, t, b = mg
            tl += l == 0
            tr += rr == 0
            tt += t == 0
            tb += b == 0
            ml.append(l)
            mr.append(rr)
            mh.append(h)
            o = outside_ink(img, (x, y, w, h))
            ol += o[0]
            orr += o[1]
            ot += o[2]
            ob += o[3]
        n = len(ml)
        if not n:
            print(f"{type_id:50s}    -  (no ink found)")
            continue
        print(f"{type_id:50s} {n:4d} {tl / n:6.0%} {tr / n:6.0%} {tt / n:6.0%} {tb / n:6.0%} "
              f"{int(np.median(ml)):5d} {int(np.median(mr)):5d} {int(np.median(mh)):5d} | "
              f"{ol / n:4.0%} {orr / n:4.0%} {ot / n:4.0%} {ob / n:4.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
