"""Contact sheet of the augmented training samples (HANDOVER.md M1).

    .venv-gpu\\Scripts\\python.exe train\\aug_sheet.py --out reports\\augmented_minimal.png

An augmentation that cannot be seen cannot be checked. The sheet shows 200
samples of the minimal latin scope after the full augmentation chain
(JPEG/WebP/brightness/contrast and, with --affine, the geometric jitter), so
that a reviewer can see what the model is actually trained on - and whether the
augmentation destroys a small type (the 5x7 pixel font of `Archy-X/Krypton/map`
is 8 px tall in the source, so a rotation of 7 degrees is not a small change
there).
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from captcha_crnn import CaptchaDataset, build_encoder, build_items, find_types, CHARSET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIRS = [os.path.join(REPO, "dataset", "out"), os.path.join(REPO, "dataset", "out_ru")]

SCOPE = ["Archy-X/Krypton/map", "GalleryCaptcha/ru-web", "CaptchaVerifyZ/map", "JSH32/Minecaptcha/map",
         "haq/mapcha/map", "jSdCool/minecaptcha/text", "just-captcha/ProstoCaptcha/map",
         "laforetbrut/are-you-sure/code", "n1zamu/NCaptcha/anvil",
         "ringoame196-s-mcPlugin/ReproductionCAPTCHA/map"]


def font(size=12):
    for name in ("consola.ttf", "arial.ttf", "segoeui.ttf"):
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-type", type=int, default=20)
    ap.add_argument("--cols", type=int, default=10)
    ap.add_argument("--affine", action="store_true")
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    cs = build_encoder(CHARSET)
    types = [(t, d) for t, d, _r in find_types(OUT_DIRS, wanted=SCOPE)]
    items = build_items(types)
    # the same number of samples per type, in order
    picked = []
    per = {}
    for it in items:
        if per.get(it["type"], 0) < args.per_type:
            per[it["type"]] = per.get(it["type"], 0) + 1
            picked.append(it)

    ds = CaptchaDataset(picked, cs.encode, augment=True, seed=args.seed, affine=args.affine)
    cell_w, cell_h = 170, 56
    cols = args.cols
    rows = (len(picked) + cols - 1) // cols
    img = Image.new("RGB", (cols * cell_w + 10, rows * cell_h + 40), (24, 24, 28))
    draw = ImageDraw.Draw(img)
    f = font(11)
    draw.text((8, 8), f"augmented samples (affine={args.affine}), {len(picked)} items, "
                     f"seed {args.seed}", font=font(14), fill=(255, 205, 90))
    for i in range(len(picked)):
        item = ds[i]
        a = item["image"][0].numpy()
        arr = ((a * 0.5 + 0.5) * 255).clip(0, 255).astype("uint8")
        pic = Image.fromarray(arr, mode="L")
        if pic.width > cell_w - 6:
            f2 = (cell_w - 6) / pic.width
            pic = pic.resize((max(1, int(pic.width * f2)), max(1, int(pic.height * f2))))
        x = 6 + (i % cols) * cell_w
        y = 34 + (i // cols) * cell_h
        img.paste(pic.convert("RGB"), (x, y))
        draw.text((x + 1, y + pic.height + 1), picked[i]["text"][:20], font=f, fill=(255, 205, 90))
    img.save(args.out)
    print(f"{args.out}  {img.size[0]}x{img.size[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
