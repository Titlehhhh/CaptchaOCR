"""Build a contact sheet: generated samples of a type next to a reference image.

    python tools/contact_sheet.py <typeDir> <reference.png> <out.png> [count]

The sheet is a row of generated samples followed by the reference image, each cell
labelled with the file name and the number of distinct colours, so that the two can be
compared side by side.
"""

import os
import sys

from PIL import Image, ImageDraw

CELL = 250
LABEL_H = 26
GAP = 6


def colors_of(im):
    return len(im.convert("RGB").getcolors(maxcolors=1 << 22))


def main():
    type_dir = sys.argv[1]
    reference = sys.argv[2]
    out = sys.argv[3]
    count = int(sys.argv[4]) if len(sys.argv) > 4 else 6

    items = []
    for i in range(1, count + 1):
        p = os.path.join(type_dir, "%03d.png" % i)
        if os.path.exists(p):
            items.append((os.path.basename(p), p))
    items.append(("REFERENCE " + os.path.basename(reference), reference))

    cells = []
    for label, path in items:
        im = Image.open(path).convert("RGB")
        cells.append((label, im, colors_of(im)))

    row_h = max(c[1].height for c in cells) + LABEL_H
    width = sum(c[1].width + GAP for c in cells)
    sheet = Image.new("RGB", (width, row_h), (18, 20, 26))
    d = ImageDraw.Draw(sheet)

    x = 0
    for label, im, n in cells:
        sheet.paste(im, (x, 0))
        d.text((x + 3, im.height + 4), f"{label}  [{n} colours]", fill=(220, 220, 220))
        x += im.width + GAP

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out)
    print("wrote", out, sheet.size)
    for label, im, n in cells:
        print(f"   {label:<28} {im.width}x{im.height}  {n} distinct colours")


if __name__ == "__main__":
    main()
