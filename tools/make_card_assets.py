import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dataset"
OUT = ROOT / "build" / "hf_assets"
GALLERY_OUT = OUT / "gallery"

BG = (247, 248, 250)
CARD = (255, 255, 255)
LINE = (223, 228, 235)
INK = (90, 99, 112)
ACCENT = (198, 138, 22)

GALLERY_TYPES = [
    "out/Archy-X/Krypton/map",
    "out/haq/mapcha/map",
    "out/LagBug/XProtect/code",
    "out_ru/LimboFilter/symbols",
    "out_ru/GalleryCaptcha/ru-web",
    "out_ru/CaptchaVerifyZ/map",
]

MODEL_TYPE = "out/haq/mapcha/map"
FILE_NAME = "001.png"

FONT_REGULAR = Path("C:/Windows/Fonts/arial.ttf")
FONT_MONO = Path("C:/Windows/Fonts/consola.ttf")

HERO_W, HERO_H = 1600, 520
GALLERY_SIDE = 256
MODEL_W, MODEL_H = 1600, 600


def read_labels(type_id):
    path = DATA / type_id / "labels.jsonl"
    rows = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rows[row["file"]] = row
    return rows


def sample(type_id, file_name=FILE_NAME):
    row = read_labels(type_id)[file_name]
    image = Image.open(DATA / type_id / file_name).convert("RGB")
    return {
        "type_id": type_id,
        "file": file_name,
        "image": image,
        "answer": row["answer"],
        "text": row["text"],
        "roi": row["roi"],
        "width": row["width"],
        "height": row["height"],
    }


def content_crop(image, margin=0.35, min_side=0.5):
    background = image.getpixel((0, 0))
    difference = ImageChops.difference(image, Image.new("RGB", image.size, background))
    bbox = difference.convert("L").point(lambda value: 255 if value > 16 else 0).getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    pad = round(max(right - left, bottom - top) * margin)
    left, top = max(0, left - pad), max(0, top - pad)
    right, bottom = min(image.width, right + pad), min(image.height, bottom + pad)
    width = min(max(right - left, image.width * min_side), image.width)
    height = min(max(bottom - top, image.height * min_side), image.height)
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    x0 = min(max(center_x - width / 2, 0), image.width - width)
    y0 = min(max(center_y - height / 2, 0), image.height - height)
    return image.crop((round(x0), round(y0), round(x0 + width), round(y0 + height)))


def fit(image, box_w, box_h, resample=Image.LANCZOS):
    scale = min(box_w / image.width, box_h / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    if size == image.size:
        return image.copy()
    return image.resize(size, resample)


def card(image, pad=14, size=None):
    if size is None:
        canvas = Image.new("RGB", (image.width + 2 * pad, image.height + 2 * pad), CARD)
        canvas.paste(image, (pad, pad))
        ImageDraw.Draw(canvas).rectangle([0, 0, canvas.width - 1, canvas.height - 1], outline=LINE)
        return canvas
    canvas = Image.new("RGB", size, CARD)
    offset = ((size[0] - image.width) // 2, (size[1] - image.height) // 2)
    canvas.paste(image, offset)
    ImageDraw.Draw(canvas).rectangle([0, 0, size[0] - 1, size[1] - 1], outline=LINE)
    return canvas, offset


def font(path, size):
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return None


def gallery_tile(item):
    canvas = Image.new("RGB", (GALLERY_SIDE, GALLERY_SIDE), BG)
    inner = GALLERY_SIDE - 20
    image = fit(content_crop(item["image"]), inner, inner)
    offset = ((GALLERY_SIDE - image.width) // 2, (GALLERY_SIDE - image.height) // 2)
    canvas.paste(image, offset)
    ImageDraw.Draw(canvas).rectangle(
        [offset[0] - 1, offset[1] - 1, offset[0] + image.width, offset[1] + image.height],
        outline=LINE,
    )
    return canvas


def hero(items):
    canvas = Image.new("RGB", (HERO_W, HERO_H), BG)
    draw = ImageDraw.Draw(canvas)
    margin = 20
    gap = 10
    cell = (HERO_W - 2 * margin - gap * (len(items) - 1)) // len(items)
    inner = cell - 28
    top = (HERO_H - cell) // 2
    for index, item in enumerate(items):
        x = margin + index * (cell + gap)
        tile = card(fit(content_crop(item["image"]), inner, inner), 14, (cell, cell))[0]
        canvas.paste(tile, (x, top))
        if index:
            line_x = x - gap // 2
            draw.line([(line_x, top + 40), (line_x, top + cell - 40)], fill=LINE, width=2)
    return canvas


def arrow(draw, x0, x1, y):
    draw.line([(x0, y), (x1 - 16, y)], fill=INK, width=4)
    draw.polygon([(x1, y), (x1 - 20, y - 12), (x1 - 20, y + 12)], fill=INK)


def model_hero():
    item = sample(MODEL_TYPE)
    canvas = Image.new("RGB", (MODEL_W, MODEL_H), BG)
    draw = ImageDraw.Draw(canvas)

    frame_card = (400, 430)
    band_card = (380, 430)
    text_card = (600, 430)
    top = 36
    xs = [40, 510, 960]

    frame = fit(item["image"], 344, 344)
    frame_panel, offset = card(frame, 14, frame_card)
    if item["roi"]:
        x, y, w, h = item["roi"]
        scale = frame.width / item["image"].width
        box = [
            offset[0] + round(x * scale) - 2,
            offset[1] + round(y * scale) - 2,
            offset[0] + round((x + w) * scale) + 1,
            offset[1] + round((y + h) * scale) + 1,
        ]
        ImageDraw.Draw(frame_panel).rectangle(box, outline=ACCENT, width=3)
    canvas.paste(frame_panel, (xs[0], top))

    band_source = item["image"]
    if item["roi"]:
        x, y, w, h = item["roi"]
        band_source = item["image"].crop((x, y, x + w, y + h))
    band = fit(band_source, 316, 300, Image.NEAREST)
    band_panel = card(band, 14, band_card)[0]
    canvas.paste(band_panel, (xs[1], top))

    text_panel = Image.new("RGB", text_card, CARD)
    ImageDraw.Draw(text_panel).rectangle([0, 0, text_card[0] - 1, text_card[1] - 1], outline=LINE)
    canvas.paste(text_panel, (xs[2], top))

    mono = font(FONT_MONO, 176)
    if mono is not None:
        ImageDraw.Draw(canvas).text(
            (xs[2] + text_card[0] // 2, top + text_card[1] // 2),
            item["text"],
            font=mono,
            fill=ACCENT,
            anchor="mm",
        )

    label = font(FONT_REGULAR, 26)
    if label is not None:
        for key, x, width in (
            ("frame", xs[0], frame_card[0]),
            ("answer band", xs[1], band_card[0]),
            ("decoded", xs[2], text_card[0]),
        ):
            draw.text((x + width // 2, top + frame_card[1] + 26), key, font=label, fill=INK, anchor="mm")

    arrow(draw, xs[0] + frame_card[0] + 8, xs[1] - 8, top + frame_card[1] // 2)
    arrow(draw, xs[1] + band_card[0] + 8, xs[2] - 8, top + frame_card[1] // 2)
    return canvas, item


def record(path, role, item=None, **extra):
    payload = {
        "role": role,
        "path": path.relative_to(ROOT).as_posix(),
        "width": None,
        "height": None,
        "bytes": path.stat().st_size,
    }
    if item is not None:
        payload.update(
            type_id=item["type_id"],
            file=item["file"],
            answer=item["answer"],
            text=item["text"],
            roi=item["roi"],
            source_size=[item["width"], item["height"]],
        )
    payload.update(extra)
    with Image.open(path) as handle:
        payload["width"], payload["height"] = handle.size
    return payload


def main():
    GALLERY_OUT.mkdir(parents=True, exist_ok=True)
    items = [sample(type_id) for type_id in GALLERY_TYPES]

    gallery_records = []
    for index, item in enumerate(items, start=1):
        path = GALLERY_OUT / f"{index:02d}.png"
        gallery_tile(item).save(path, optimize=True)
        gallery_records.append(record(path, "gallery", item))

    hero_path = OUT / "hero.png"
    hero(items).save(hero_path, optimize=True)

    model_path = OUT / "model_hero.png"
    model_image, model_item = model_hero()
    model_image.save(model_path, optimize=True)

    manifest = {
        "generated_by": "tools/make_card_assets.py",
        "background": "#f7f8fa",
        "fonts": {
            "labels": FONT_REGULAR.as_posix() if FONT_REGULAR.exists() else None,
            "decoded": FONT_MONO.as_posix() if FONT_MONO.exists() else None,
            "labels_drawn": FONT_REGULAR.exists(),
        },
        "assets": [
            record(hero_path, "hero", samples=[item["type_id"] for item in items],
                   answers=[item["answer"] for item in items]),
            record(model_path, "model_hero", model_item,
                   panels=["frame", "answer band", "decoded"]),
            *gallery_records,
        ],
    }
    with (OUT / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    for entry in manifest["assets"]:
        print(entry["role"], entry["path"], entry["width"], entry["height"], entry["bytes"])


if __name__ == "__main__":
    main()
