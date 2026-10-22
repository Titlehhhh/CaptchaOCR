import os, sys
from PIL import Image, ImageDraw

base = os.path.join(os.path.dirname(__file__), "..", "site", "captchas")
outdir = os.path.join(os.path.dirname(__file__), "..", "tmp")
os.makedirs(outdir, exist_ok=True)

def crop(path, gx, gy, tag, scale=3):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    big = im.resize((W*scale, H*scale), Image.NEAREST)
    d = ImageDraw.Draw(big)
    for c in range(1, gx):
        x = c*W*scale//gx
        d.line([(x,0),(x,H*scale)], fill=(255,0,255), width=2)
        d.text((x+3,3), str(c), fill=(255,0,255))
    for r in range(1, gy):
        y = r*H*scale//gy
        d.line([(0,y),(W*scale,y)], fill=(255,0,255), width=2)
        d.text((3,y+3), str(r), fill=(255,0,255))
    p = os.path.join(outdir, f"crop_{tag}.png")
    big.save(p)
    print(p)

for rel in sys.argv[1:]:
    p = os.path.join(base, rel)
    tag = os.path.basename(p) + os.path.basename(os.path.dirname(p))
    crop(p, 3, 3, tag)
