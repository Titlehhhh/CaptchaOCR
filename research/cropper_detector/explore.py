"""Throwaway exploration: contact sheets of dataset frames with the label roi."""
import json, os, sys
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def sheet(types, out, n=3, scale=3):
    cells = []
    for t in types:
        d = os.path.join(ROOT, t)
        rows = [json.loads(l) for l in open(os.path.join(d, "labels.jsonl"), encoding="utf-8")]
        for r in rows[:n]:
            im = Image.open(os.path.join(d, r["file"])).convert("RGB")
            im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
            w, h = im.size
            dr = ImageDraw.Draw(im)
            roi = r.get("roi")
            if roi:
                x, y, bw, bh = roi
                dr.rectangle([x * scale, y * scale, (x + bw) * scale, (y + bh) * scale], outline=(255, 0, 0))
            else:
                dr.rectangle([0, 0, w - 1, h - 1], outline=(0, 255, 0))
            dr.text((2, 2), t.split("/")[-1] + " " + str(r.get("answer"))[:12], fill=(255, 255, 0))
            cells.append((im, t))
    cols = n
    rowsn = (len(cells) + cols - 1) // cols
    cw = max(c[0].width for c in cells)
    ch = max(c[0].height for c in cells)
    canvas = Image.new("RGB", (cols * cw, rowsn * ch), (30, 30, 30))
    for i, (im, _) in enumerate(cells):
        canvas.paste(im, ((i % cols) * cw, (i // cols) * ch))
    canvas.save(os.path.join(ROOT, out))
    print("saved", out, canvas.size)


if __name__ == "__main__":
    sheet([
        "dataset/out/haq/mapcha/map",
        "dataset/out_ru/LimboFilter/digits",
        "dataset/out_ru/CaptchaVerifyZ/map",
        "dataset/out_ru/GalleryCaptcha/ru-web",
        "dataset/out/Archy-X/Krypton/map",
        "dataset/out/just-captcha/ProstoCaptcha/map",
        "dataset/out_ru/LimboFilter/symbols",
        "dataset/out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map",
    ], "build/cropper_detector/explore_a.png", n=3, scale=3)

    sheet([
        "dataset/out/InstantlyMoist/Captcha/textcaptcha",
        "dataset/out/irootdev/AnBot/captcha",
        "dataset/out/jonesdevelopment/sonar/standard",
        "dataset/out/jonesdevelopment/sonar/legacy",
        "dataset/out/jonesdevelopment/sonar/complex",
        "dataset/out/LagBug/XProtect/code",
        "dataset/out/LagBug/XProtect/map",
        "dataset/out_ru/BotFilter/map",
        "dataset/out_ru/GalleryCaptcha/ru-symbols",
        "dataset/out_ru/GalleryCaptcha/ru-numberword",
        "dataset/out/JSH32/Minecaptcha/map",
        "dataset/out_ru/LimboFilter/map",
    ], "build/cropper_detector/explore_b.png", n=3, scale=3)
