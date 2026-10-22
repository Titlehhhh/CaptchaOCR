import os, sys, collections
from PIL import Image
import numpy as np

# The GalleryCaptcha reference gallery was removed from this repository on 2026-10-22
# (it held third-party screenshots). Point CAPTCHA_GALLERY_DIR at a local copy to use it.
base = os.environ.get("CAPTCHA_GALLERY_DIR", "")
if not base:
    raise SystemExit("the reference gallery is no longer part of this repository (2026-10-22); "
                     "set CAPTCHA_GALLERY_DIR to a local copy to run this script")

def hist(path, top=12, only=None):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).reshape(-1, 3)
    c = collections.Counter(map(tuple, a))
    print(f"\n== {os.path.relpath(path, base)}  {im.size}  distinct={len(c)}")
    for col, n in c.most_common(top):
        print(f"   #{col[0]:02X}{col[1]:02X}{col[2]:02X} {col}  x{n}  ({100*n/len(a):.2f}%)")

for rel in sys.argv[1:]:
    p = os.path.join(base, rel)
    if os.path.isdir(p):
        for f in sorted(x for x in os.listdir(p) if x.endswith(".png")):
            hist(os.path.join(p, f))
    else:
        hist(p)
