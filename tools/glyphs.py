import os, re, sys, collections
from PIL import Image
import numpy as np

base = os.path.join(os.path.dirname(__file__), "..", "site", "captchas")

def components(mask, min_px=25):
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not seen[y, x]:
                stack = [(y, x)]; seen[y, x] = True; pts = []
                while stack:
                    cy, cx = stack.pop(); pts.append((cy, cx))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                                seen[ny, nx] = True; stack.append((ny, nx))
                if len(pts) >= min_px:
                    ys = [p[0] for p in pts]; xs = [p[1] for p in pts]
                    out.append((min(xs), min(ys), max(xs), max(ys), len(pts)))
    return out

def report(path, ink):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(int)
    H, W, _ = a.shape
    m = ink(a)
    print(f"\n== {os.path.relpath(path, base)} {W}x{H}  ink px={m.sum()}")
    cols = collections.Counter(map(tuple, a[m]))
    print("   ink colours:", [(f"#{r:02X}{g:02X}{b:02X}", n) for (r, g, b), n in cols.most_common(6)])
    for c in components(m):
        x0, y0, x1, y1, n = c
        print(f"   glyph bbox x[{x0}..{x1}] y[{y0}..{y1}]  {x1-x0+1}x{y1-y0+1}  px={n}")

red = lambda a: (a[:,:,0] > 90) & (a[:,:,0] - a[:,:,1] > 60) & (a[:,:,0] - a[:,:,2] > 60)
pink = lambda a: (a[:,:,0] > 120) & (a[:,:,0] - a[:,:,1] > 25) & (a[:,:,2] - a[:,:,1] > 15) & (a[:,:,2] < 240)

def mask_for(rel):
    """The ink mask of a catalogue section.

    The V5 section (API V5, the 3x3 Latin/digit puzzles) carries *red* ink, the V53
    section (API V53, the 2x2 puzzles) carries *pink* ink. The version has to be
    matched exactly: a plain `"V5" in rel` test is also true for "V53", so the V53
    section would be analysed with the red mask.
    """
    m = re.search(r"API_V(\d+)", rel)
    version = m.group(1) if m else None
    return red if version == "5" else pink

for rel in sys.argv[1:]:
    p = os.path.join(base, rel)
    if os.path.isdir(p):
        for f in sorted(x for x in os.listdir(p) if x.endswith(".png")):
            report(os.path.join(p, f), mask_for(rel))
    else:
        report(p, mask_for(rel))
