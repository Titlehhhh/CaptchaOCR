import os, sys, itertools
from PIL import Image
import numpy as np

# The GalleryCaptcha reference gallery was removed from this repository on 2026-10-22
# (it held third-party screenshots). Point CAPTCHA_GALLERY_DIR at a local copy to use it.
base = os.environ.get("CAPTCHA_GALLERY_DIR", "")
if not base:
    raise SystemExit("the reference gallery is no longer part of this repository (2026-10-22); "
                     "set CAPTCHA_GALLERY_DIR to a local copy to run this script")

def grid(w, h, gx, gy):
    return [round(i * w / gx) for i in range(gx + 1)], [round(i * h / gy) for i in range(gy + 1)]

def load_tiles(path, gx=3, gy=3, rot=0):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    xs, ys = grid(W, H, gx, gy)
    tiles = []
    for r in range(gy):
        for c in range(gx):
            t = np.asarray(im.crop((xs[c], ys[r], xs[c+1], ys[r+1])).convert("RGB")).astype(np.int16)
            if rot == 180:
                t = t[::-1, ::-1]
            tiles.append(t)
    return tiles, xs, ys, W, H

def cost_matrices(tiles):
    n = len(tiles)
    costV = np.zeros((n, n)); costH = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j: continue
            a, b = tiles[i], tiles[j]
            w = min(a.shape[1], b.shape[1]); h = min(a.shape[0], b.shape[0])
            costV[i, j] = np.abs(a[-1, :w, :] - b[0, :w, :]).mean()
            costH[i, j] = np.abs(a[:h, -1, :] - b[:h, 0, :]).mean()
    return costV, costH

def best_arrangement(tiles, gx=3, gy=3):
    costV, costH = cost_matrices(tiles)
    n = gx * gy
    best = (1e18, None)
    for perm in itertools.permutations(range(n)):
        tot = 0.0
        for idx in range(gx):
            for jdx in range(gy):
                p = idx * gx + jdx
                if jdx > 0:
                    tot += costH[perm[p-1], perm[p]]
                if idx > 0:
                    tot += costV[perm[p-gx], perm[p]]
                if tot >= best[0]:
                    break
            if tot >= best[0]:
                break
        if tot < best[0]:
            best = (tot, perm)
    return best

def report(path, gx=3, gy=3):
    for rot in (0, 180):
        tiles, xs, ys, W, H = load_tiles(path, gx, gy, rot)
        tot, perm = best_arrangement(tiles, gx, gy)
        ident = tuple(range(gx * gy))
        idcost, _ = best_arrangement(tiles, gx, gy)
        print(f"\n{os.path.relpath(path, base)}  rot={rot}: best cost={tot:.2f}")
        for r in range(gy):
            print("   " + " ".join(f"{perm[r*gx+c]:2d}" for c in range(gx)))
        out = Image.new("RGB", (W, H))
        for r in range(gy):
            for c in range(gx):
                out.paste(Image.fromarray(tiles[perm[r*gx+c]].astype("uint8")), (xs[c], ys[r]))
        tag = "rot180" if rot == 180 else "rot0"
        out.save(os.path.join(os.path.dirname(__file__), "..", "tmp",
                 f"recon_{tag}_" + os.path.basename(os.path.dirname(path))[:12] + "_" + os.path.basename(path)))
    print("   reconstructions saved to tmp/")

for rel in sys.argv[1:]:
    p = os.path.join(base, rel)
    report(p)
