from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "img"
FONT_DIR = Path("C:/Windows/Fonts")

WHITE = (255, 255, 255)
TEXT = (36, 41, 47)
MUTED = (87, 96, 106)
LINE = (140, 149, 159)
BORDER = (208, 215, 222)
PANEL = (246, 248, 250)
ACCENT = (176, 76, 16)
ACCENT_SOFT = (253, 240, 228)

HERO_SOURCES = [
    "dataset/out/Archy-X/Krypton/map/001.png",
    "dataset/out/haq/mapcha/map/001.png",
    "dataset/out/jonesdevelopment/sonar/standard/001.png",
    "dataset/out/just-captcha/ProstoCaptcha/map/001.png",
    "dataset/out_ru/LimboFilter/symbols/001.png",
]

PIPELINE_SOURCE = "dataset/out/haq/mapcha/map/001.png"

HERO_SIZE = (1392, 304)
PIPELINE_SIZE = (1200, 360)


def load_font(name, size):
    return ImageFont.truetype(str(FONT_DIR / name), size)


def save_png(image, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, format="PNG", optimize=True)


def centered(draw, box, text, font, fill):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    x = box[0] + (box[2] - box[0] - (right - left)) / 2 - left
    y = box[1] + (box[3] - box[1] - (bottom - top)) / 2 - top
    draw.text((x, y), text, font=font, fill=fill)


def content_box(image, margin=0.1, min_side=0.5):
    background = image.getpixel((0, 0))
    difference = ImageChops.difference(image, Image.new("RGB", image.size, background))
    mask = difference.convert("L").point(lambda value: 255 if value > 16 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return (0, 0, image.width, image.height)
    left, top, right, bottom = bbox
    pad = round(max(right - left, bottom - top) * margin)
    left, top = max(0, left - pad), max(0, top - pad)
    right, bottom = min(image.width, right + pad), min(image.height, bottom + pad)
    side = min(max(right - left, bottom - top, image.width * min_side), min(image.width, image.height))
    centre_x = (left + right) / 2
    centre_y = (top + bottom) / 2
    x0 = min(max(centre_x - side / 2, 0), image.width - side)
    y0 = min(max(centre_y - side / 2, 0), image.height - side)
    return (round(x0), round(y0), round(x0 + side), round(y0 + side))


def framed_tile(source, side):
    image = Image.open(source).convert("RGB")
    image = image.crop(content_box(image))
    image = image.resize((side, side), Image.NEAREST)
    framed = Image.new("RGB", (side, side), WHITE)
    framed.paste(image, (0, 0))
    ImageDraw.Draw(framed).rectangle([0, 0, side - 1, side - 1], outline=BORDER)
    return framed


def make_hero():
    margin, gap, side = 24, 16, 256
    width, height = HERO_SIZE
    canvas = Image.new("RGB", (width, height), WHITE)
    for index, source in enumerate(HERO_SOURCES):
        x = margin + index * (side + gap)
        canvas.paste(framed_tile(ROOT / source, side), (x, margin))
    save_png(canvas, OUT_DIR / "hero.png")


def horizontal_arrow(draw, start, end, y):
    draw.line([(start, y), (end - 11, y)], fill=LINE, width=2)
    draw.polygon([(end, y), (end - 12, y - 5), (end - 12, y + 5)], fill=LINE)


def vertical_line(draw, x, top, bottom):
    draw.line([(x, top), (x, bottom)], fill=LINE, width=2)


def branch_box(draw, x, y, width, height, label, font):
    draw.rounded_rectangle(
        [x, y, x + width, y + height], radius=8, fill=PANEL, outline=BORDER, width=1
    )
    centered(draw, (x, y, x + width, y + height), label, font, TEXT)


def make_pipeline():
    width, height = PIPELINE_SIZE
    canvas = Image.new("RGB", (width, height), WHITE)
    draw = ImageDraw.Draw(canvas)

    label_font = load_font("arial.ttf", 20)
    small_font = load_font("arial.ttf", 16)
    model_font = load_font("arialbd.ttf", 30)
    head_font = load_font("arialbd.ttf", 24)

    image_x, image_y, image_side = 40, 52, 256
    canvas.paste(framed_tile(ROOT / PIPELINE_SOURCE, image_side), (image_x, image_y))
    centered(draw, (image_x, 314, image_x + image_side, 338), "кадр", small_font, MUTED)

    box_x, box_width, box_height = 344, 252, 44
    centers = [100, 180, 260]
    labels = ["строка из разметки", "выбор автоматически", "целиком"]

    source_x = image_x + image_side
    first_trunk = 322
    draw.line([(source_x, 180), (first_trunk, 180)], fill=LINE, width=2)
    vertical_line(draw, first_trunk, centers[0], centers[-1])
    for center in centers:
        horizontal_arrow(draw, first_trunk, box_x, center)

    for center, label in zip(centers, labels):
        branch_box(draw, box_x, center - box_height // 2, box_width, box_height, label, label_font)

    second_trunk = 626
    box_right = box_x + box_width
    for center in centers:
        draw.line([(box_right, center), (second_trunk, center)], fill=LINE, width=2)
    vertical_line(draw, second_trunk, centers[0], centers[-1])

    model_x, model_width = 664, 228
    model_y, model_height = 130, 100
    horizontal_arrow(draw, second_trunk, model_x, 180)
    draw.rounded_rectangle(
        [model_x, model_y, model_x + model_width, model_y + model_height],
        radius=10,
        fill=WHITE,
        outline=BORDER,
        width=2,
    )
    centered(draw, (model_x, model_y + 6, model_x + model_width, model_y + 62), "PP-OCRv6", model_font, TEXT)
    centered(draw, (model_x, model_y + 56, model_x + model_width, model_y + 92), "CTC", small_font, MUTED)

    answer_x, answer_width = 940, 216
    answer_y, answer_height = 152, 56
    horizontal_arrow(draw, model_x + model_width, answer_x, 180)
    draw.rounded_rectangle(
        [answer_x, answer_y, answer_x + answer_width, answer_y + answer_height],
        radius=10,
        fill=ACCENT_SOFT,
        outline=ACCENT,
        width=2,
    )
    centered(
        draw,
        (answer_x, answer_y, answer_x + answer_width, answer_y + answer_height),
        "ответ",
        head_font,
        ACCENT,
    )

    save_png(canvas, OUT_DIR / "pipeline.png")


def main():
    make_hero()
    make_pipeline()


if __name__ == "__main__":
    main()
