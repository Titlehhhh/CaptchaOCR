"""Explore: how far is ink_bbox from the label roi? What does a frame look like?"""
import json, os, random, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "train"))
from ppocr_data import PPOCRDataset  # noqa: E402

TYPES = [
    "dataset/out/Archy-X/Krypton/map",
    "dataset/out/haq/mapcha/map",
    "dataset/out/InstantlyMoist/Captcha/textcaptcha",
    "dataset/out/irootdev/AnBot/captcha",
    "dataset/out/jonesdevelopment/sonar/complex",
    "dataset/out/jonesdevelopment/sonar/legacy",
    "dataset/out/jonesdevelopment/sonar/standard",
    "dataset/out/JSH32/Minecaptcha/map",
    "dataset/out/just-captcha/ProstoCaptcha/map",
    "dataset/out/LagBug/XProtect/code",
    "dataset/out/LagBug/XProtect/map",
    "dataset/out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map",
    "dataset/out_ru/BotFilter/map",
    "dataset/out_ru/CaptchaVerifyZ/map",
    "dataset/out_ru/GalleryCaptcha/ru-symbols",
    "dataset/out_ru/GalleryCaptcha/ru-web",
    "dataset/out_ru/LimboFilter/digits",
    "dataset/out_ru/LimboFilter/map",
    "dataset/out_ru/LimboFilter/symbols",
]


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    return inter / (aw * ah + bw * bh - inter)


def contains(outer, inner):
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    return ix >= ox and iy >= oy and ix + iw <= ox + ow and iy + ih <= oy + oh


rng = random.Random(1234)
print(f"{'type':52s} {'n':>4s} {'inkIoU':>7s} {'cnt':>4s} {'roiW':>5s} {'roiH':>5s} {'inkW':>5s} {'inkH':>5s} {'inh':>5s}")
for t in TYPES:
    d = os.path.join(ROOT, t)
    rows = [json.loads(l) for l in open(os.path.join(d, "labels.jsonl"), encoding="utf-8")]
    rows = [r for r in rows if r.get("roi")]
    sel = rng.sample(rows, min(20, len(rows)))
    ious, cnts, rw, rh, iw_, ih_ = [], [], [], [], [], []
    for r in sel:
        im = Image.open(os.path.join(d, r["file"])).convert("RGB")
        box = PPOCRDataset.ink_bbox(im)
        ious.append(iou(box, r["roi"]))
        cnts.append(contains(box, r["roi"]))
        rw.append(r["roi"][2]); rh.append(r["roi"][3])
        iw_.append(box[2]); ih_.append(box[3])
    print(f"{t:52s} {len(sel):4d} {np.mean(ious):7.3f} {np.mean(cnts):4.2f} "
          f"{np.median(rw):5.0f} {np.median(rh):5.0f} {np.median(iw_):5.0f} {np.median(ih_):5.0f} "
          f"{np.median(ih_)/im.height:5.2f}")
