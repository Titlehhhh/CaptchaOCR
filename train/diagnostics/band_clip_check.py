import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from captcha_crnn import find_types, read_labels

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIRS = [os.path.join(REPO, "dataset", "out"), os.path.join(REPO, "dataset", "out_ru")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--types", nargs="*", default=None)
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--pad", type=int, default=8)
    args = ap.parse_args()
    for type_id, directory, _root in find_types(OUT_DIRS, wanted=args.types):
        rows = [r for r in read_labels(directory) if r.get("roi")]
        print(f"=== {type_id}")
        for r in rows[:args.samples]:
            x, y, w, h = r["roi"]
            a = np.asarray(Image.open(os.path.join(directory, r["file"])).convert("L"))
            lo = max(0, x - args.pad)
            hi = min(a.shape[1], x + w + args.pad)
            print(f"  gold {r['text']!r} roi {r['roi']}  (band x {x}..{x + w - 1}, "
                  f"window {lo}..{hi - 1})")
            header = "        " + "".join("|" if lo + i == x else
                                           ("+" if lo + i == x + w else " ") for i in range(hi - lo))
            print(header)
            for rr in range(max(0, y - 1), min(a.shape[0], y + h + 1)):
                cells = "".join("#" if a[rr, c] < 128 else "." for c in range(lo, hi))
                print(f"  row {rr:3d} {cells}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
