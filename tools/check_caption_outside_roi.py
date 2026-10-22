"""Check that the caption's ink is never inside the text band of a composite.

    python tools/check_caption_outside_roi.py dataset/out_ru/GalleryCaptcha/ru-numberword-caption

The caption is a *different* string from the answer, so a recogniser that is handed the
text band must never see it. The band of a composite is the band of the map, cut off at
the first row the caption's ink is on - this checks that the cut really works, by
looking for the caption's own fill colour inside the band.
"""

import json
import os
import sys

from PIL import Image

ORANGE = (216, 127, 51)
WHITE = (255, 255, 255)


def caption_pixels(path):
    """The rows that carry the caption: the ones with a long run of a caption colour."""
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        px = rgb.load()
        rows = {}
        for y in range(rgb.height):
            n_orange = n_white = 0
            for x in range(rgb.width):
                p = px[x, y]
                if p == ORANGE:
                    n_orange += 1
                elif p == WHITE:
                    n_white += 1
            if n_orange > 20:
                rows[y] = "orange"
            elif n_white > 40:
                rows[y] = "white"
        return rows


def main():
    d = sys.argv[1]
    rows = [json.loads(l) for l in open(os.path.join(d, "labels.jsonl"), encoding="utf-8")]
    bad = 0
    checked = 0
    for r in rows:
        path = os.path.join(d, r["file"])
        cap = caption_pixels(path)
        if not cap:
            continue
        checked += 1
        roi = r.get("roi")
        if not roi:
            print(f"!! {r['file']}: no roi")
            bad += 1
            continue
        x, y, w, h = roi
        inside = [ry for ry in cap if y <= ry < y + h]
        if inside:
            bad += 1
            print(f"!! {r['file']}: caption ink on rows {inside} inside the band {roi}")
    print(f"{checked} samples with a detectable caption, {bad} with caption ink inside the band")
    print("RESULT:", "OK" if bad == 0 else "<-- CHECK")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
