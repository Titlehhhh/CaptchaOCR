"""Measure the glyph heights and the text bands of the generated maps.

    python tools/measure_glyphs.py dataset/out_ru/LimboFilter/map [n]
    python tools/measure_glyphs.py dataset/out_ru/LimboFilter/symbols [n]

This is what the H=32 scaling plan needs: how high a letter really is in the map, how
high the band around it is, and how many lines the band carries.  The text is found by
its saturated colours - the upstream paints it with the gradient, which runs over red,
green, blue, olive, magenta and cyan, while the backdrop is a blend of two muted
palette colours and the curves are black.
"""

import json
import os
import sys

from PIL import Image


def row_profile(path):
    """The rows that carry ink, found by the hard edges of the glyphs.

    The backdrop is a smooth field, so a row of the text is a row with many colour
    jumps; the curves are one pixel wide and contribute almost nothing.
    """
    im = Image.open(path).convert("RGB")
    px = im.load()
    w, h = im.size
    rows = []
    for y in range(h):
        n = 0
        for x in range(w - 1):
            p = px[x, y]
            q = px[x + 1, y]
            if max(abs(p[i] - q[i]) for i in range(3)) > 45:
                n += 1
        rows.append(n)
    return rows, w, h


def bands(rows, threshold=2):
    out = []
    start = None
    for y, n in enumerate(rows):
        if n > threshold and start is None:
            start = y
        elif n <= threshold and start is not None:
            out.append((start, y - 1))
            start = None
    if start is not None:
        out.append((start, len(rows) - 1))
    return out


def main():
    d = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    rows = [json.loads(l) for l in open(os.path.join(d, "labels.jsonl"), encoding="utf-8")]

    band_h = []
    band_w = []
    line_h = []
    lines = []
    gap = []
    advance = []
    for r in rows[:n]:
        prof, w, h = row_profile(os.path.join(d, r["file"]))
        bs = bands(prof)
        roi = r.get("roi")
        if roi:
            band_h.append(roi[3])
            band_w.append(roi[2])
        # the gaps between the line bands: that is the line advance
        for a, b in bs:
            line_h.append(b - a + 1)
        lines.append(len(bs))
        for (a, b), (c, d2) in zip(bs, bs[1:]):
            gap.append(c - b - 1)
            advance.append(c - a)

    def stat(name, values):
        if not values:
            print(f"  {name}: -")
            return
        values = sorted(values)
        print(f"  {name}: min {values[0]}  median {values[len(values) // 2]}  max {values[-1]}")

    print(f"{d}  ({n} samples)")
    stat("band height (map px)", band_h)
    stat("ink band height (map px)", line_h)
    stat("number of ink bands", lines)
    stat("gap between the bands (map px)", gap)
    stat("band width (map px)", band_w)
    stat("advance between two bands (map px)", advance)


if __name__ == "__main__":
    main()
