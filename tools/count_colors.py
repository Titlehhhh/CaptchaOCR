"""Count the distinct colours of every sample of a dataset, per type.

    python tools/count_colors.py dataset/out_ru [typeSubstring ...]

The reference composites of the reconstructed number-word families were measured at
1372..23291 distinct colours and 2582..12308; a palette-quantised render would sit at a
handful, so the count is the cheapest check that a composite really is a rescaled
picture and not a palette image.
"""

import os
import sys

from PIL import Image


def colors_of(path):
    with Image.open(path) as im:
        return len(im.convert("RGB").getcolors(maxcolors=1 << 22))


def main():
    root = sys.argv[1]
    wanted = sys.argv[2:]

    types = []
    for dirpath, dirnames, filenames in os.walk(root):
        if "real_shots" in os.path.relpath(dirpath, root).split(os.sep):
            continue
        pngs = sorted(f for f in filenames if f.lower().endswith(".png"))
        if pngs:
            types.append((os.path.relpath(dirpath, root).replace(os.sep, "/"), dirpath, pngs))

    print(f"{'type':<40} {'n':>4} {'min':>7} {'median':>7} {'max':>7}")
    print("-" * 72)
    for rel, d, pngs in sorted(types):
        if wanted and not any(w in rel for w in wanted):
            continue
        counts = sorted(colors_of(os.path.join(d, p)) for p in pngs)
        med = counts[len(counts) // 2]
        print(f"{rel:<40} {len(counts):>4} {counts[0]:>7} {med:>7} {counts[-1]:>7}")


if __name__ == "__main__":
    main()
