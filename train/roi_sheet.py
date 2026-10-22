"""Contact sheets of the text bands.

    .venv-gpu\\Scripts\\python.exe train\\roi_sheet.py --mode bands --out reports\\roi_bands_minimal.png \
        --types "Archy-X/Krypton/map" "JSH32/Minecaptcha/map" ...

Three modes:

* ``bands``  - every sample of every type, cropped by its ``roi`` and scaled the way
  the trainer scales it (the glyph to 32 px), with the gold text under each cell.
  This is exactly what the recogniser is shown.
* ``frames`` - the whole frame with the band rectangle drawn on it, so it can be
  checked that the rectangle is where the answer is and not somewhere else.
* ``noband`` - the whole frame for the types that have no band at all, which is
  what the model would be shown if the band filter were switched off.
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from captcha_crnn import CaptchaDataset, find_types, read_labels

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIRS = [os.path.join(REPO, "dataset", "out"), os.path.join(REPO, "dataset", "out_ru")]

BG = (24, 24, 28)
FG = (235, 235, 235)
GOLD = (255, 205, 90)
BAND = (255, 90, 90)


def font(size=13):
    for name in ("consola.ttf", "arial.ttf", "segoeui.ttf"):
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def text_size(draw, s, f):
    box = draw.textbbox((0, 0), s, font=f)
    return box[2] - box[0], box[3] - box[1]


def make_sheet(entries, mode, out_path, cols=10, cell_w=150, crop_h=32, label_h=16,
               per_type=None, title="", zoom_factor=4):
    """entries: list of (type_id, directory)."""
    f_type = font(15)
    f_cell = font(11)
    f_title = font(19)

    # First pass: how tall is every block?
    blocks = []
    for type_id, directory in entries:
        rows = read_labels(directory)
        if per_type:
            rows = rows[:per_type]
        blocks.append((type_id, directory, rows))

    # Frame mode: a sample of frames, scaled to a common cell.
    frame_cell_w = 220
    frame_cell_h = 220
    # Zoom mode: the band crop at 4x, nearest neighbour.
    zoom_w = 300
    zoom_n = 4
    zoom_h = 200

    width = cols * cell_w + 20
    if mode == "frames":
        width = 5 * frame_cell_w + 20
    elif mode == "zoom":
        width = zoom_n * zoom_w + 20

    heights = []
    for type_id, directory, rows in blocks:
        if mode == "bands":
            heights.append(26 + 16 + ((len(rows) + cols - 1) // cols) * (crop_h + label_h + 6))
        elif mode == "zoom":
            heights.append(26 + 16 + zoom_h + 16)
        else:
            heights.append(26 + 16 + frame_cell_h)
    total = sum(heights) + 40
    if title:
        total += 34

    img = Image.new("RGB", (width, int(total)), BG)
    draw = ImageDraw.Draw(img)

    y = 12
    if title:
        draw.text((12, y), title, font=f_title, fill=GOLD)
        y += 30

    for (type_id, directory, rows), bh in zip(blocks, heights):
        draw.text((12, y), type_id, font=f_type, fill=FG)
        y += 26
        if mode == "bands":
            ds = CaptchaDataset(
                [{"path": os.path.join(directory, r["file"]), "roi": r.get("roi"),
                  "text": r.get("text") or ""} for r in rows],
                lambda s: [], augment=False)
            for i, r in enumerate(rows):
                col, row = i % cols, i // cols
                x = 10 + col * cell_w
                yy = y + row * (crop_h + label_h + 6)
                crop = ds._load(os.path.join(directory, r["file"]), r.get("roi"))
                line = ds._line_height(crop)
                scale = 32 / max(1, line)
                w = max(1, int(round(crop.width * scale)))
                crop = crop.resize((w, crop_h), Image.BILINEAR)
                # A crop wider than the cell would be clipped by the sheet and look
                # like a broken band, so it is scaled down to fit instead.
                if w > cell_w - 6:
                    f = (cell_w - 6) / w
                    crop = crop.resize((max(1, int(w * f)), max(1, int(crop_h * f))),
                                       Image.BILINEAR)
                cell = Image.new("L", (cell_w - 6, crop_h), 0)
                cell.paste(crop, ((cell_w - 6 - crop.width) // 2, 0))
                img.paste(cell.convert("RGB"), (x, yy))
                draw.rectangle([x, yy, x + cell_w - 6, yy + crop_h - 1], outline=(70, 70, 80))
                gold = r.get("text") or ""
                draw.text((x + 1, yy + crop_h + 1), gold[:22], font=f_cell, fill=GOLD)
            y += ((len(rows) + cols - 1) // cols) * (crop_h + label_h + 6)
        elif mode == "zoom":
            # The band crop at 4x, nearest neighbour: what the pixels really are.
            ds = CaptchaDataset(
                [{"path": os.path.join(directory, r["file"]), "roi": r.get("roi"),
                  "text": r.get("text") or ""} for r in rows],
                lambda s: [], augment=False)
            x = 10
            for i, r in enumerate(rows[:zoom_n]):
                crop = ds._load(os.path.join(directory, r["file"]), r.get("roi"))
                f = zoom_factor
                crop = crop.resize((crop.width * f, crop.height * f), Image.NEAREST)
                if crop.width > zoom_w - 8:
                    ff = (zoom_w - 8) / crop.width
                    crop = crop.resize((int(crop.width * ff), max(1, int(crop.height * ff))),
                                       Image.NEAREST)
                img.paste(crop.convert("RGB"), (x, y))
                draw.rectangle([x, y, x + crop.width, y + crop.height], outline=(90, 90, 100))
                draw.text((x + 1, y + crop.height + 2),
                          (r.get("text") or "")[:24] + f"  [{r.get('roi')}]", font=f_cell, fill=GOLD)
                x += zoom_w
            y += zoom_h
        else:
            for i, r in enumerate(rows[:5]):
                x = 10 + i * frame_cell_w
                frame = Image.open(os.path.join(directory, r["file"])).convert("RGB")
                roi = r.get("roi")
                if roi:
                    d2 = ImageDraw.Draw(frame)
                    x0, y0, w, h = roi
                    d2.rectangle([x0, y0, x0 + w, y0 + h], outline=(255, 60, 60), width=2)
                scale = min((frame_cell_w - 10) / frame.width, (frame_cell_h - 24) / frame.height)
                frame = frame.resize((max(1, int(frame.width * scale)), max(1, int(frame.height * scale))))
                img.paste(frame, (x, y))
                draw.text((x + 1, y + frame.height + 3),
                          (r.get("text") or "")[:24], font=f_cell, fill=GOLD)
            y += frame_cell_h

    img.save(out_path)
    print(f"{out_path}  {img.size[0]}x{img.size[1]}")
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["bands", "frames", "noband", "zoom"], default="bands")
    ap.add_argument("--out", required=True)
    ap.add_argument("--types", nargs="*", default=None)
    ap.add_argument("--cols", type=int, default=10)
    ap.add_argument("--per-type", type=int, default=100)
    ap.add_argument("--title", default="")
    ap.add_argument("--zoom-factor", type=int, default=4)
    args = ap.parse_args()

    wanted = args.types
    entries = []
    for type_id, directory, root in find_types(OUT_DIRS, wanted=wanted):
        if args.mode == "noband":
            rows = read_labels(directory)
            if any(r.get("roi") for r in rows):
                continue
        entries.append((type_id, directory))
    if not entries:
        print("no types matched", file=sys.stderr)
        return 1
    make_sheet(entries, args.mode, args.out, cols=args.cols, per_type=args.per_type,
               title=args.title or f"{args.mode} - {len(entries)} types",
               zoom_factor=args.zoom_factor)
    return 0


if __name__ == "__main__":
    sys.exit(main())
