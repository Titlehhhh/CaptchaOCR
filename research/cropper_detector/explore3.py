"""Explore the 6 real screenshots: colour histograms, zoom on the middle."""
import os
from collections import Counter
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST = os.path.join(ROOT, "test")

for name in ["1651", "5932", "2013", "5968", "3620", "7488"]:
    p = os.path.join(TEST, name + ".png")
    im = Image.open(p).convert("RGB")
    a = np.asarray(im)
    flat = a.reshape(-1, 3)
    cols, cnt = np.unique(flat, axis=0, return_counts=True)
    order = np.argsort(-cnt)
    print(f"--- {name} {im.size}  unique={len(cols)}")
    for i in order[:12]:
        c = cols[i]
        print(f"    {tuple(int(x) for x in c)} : {cnt[i]:7d} ({100*cnt[i]/len(flat):5.2f}%)")
    # save a zoom of the central area
    w, h = im.size
    crop = im.crop((0, 0, w, h)).resize((w, h))
    crop.save(os.path.join(ROOT, f"build/cropper_detector/real_{name}.png"))
