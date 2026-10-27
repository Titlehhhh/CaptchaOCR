"""Tiny text/glyph band detectors.

Two detectors live here:

* `classical_detect(img)` - a pure classical CV detector (numpy + PIL only,
  no scipy / no OpenCV, so the web app can call it as-is).
* `LearnedDetector`      - a tiny U-Net (a few hundred thousand parameters)
  trained on the label `roi` bands; the weights live in
  `build/cropper_detector/detector.pt`.

Both return a box in the `(x, y, w, h)` convention of the dataset labels
(`labels.jsonl: roi`), i.e. the rectangle that holds the answer text.

Only this file and its siblings under `build/cropper_detector/` are written by
this task; the dataset, the trainer and the web app are read-only.
"""

import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------- #
# box helpers
# --------------------------------------------------------------------------- #
def box_iou(a, b):
    """IoU of two `(x, y, w, h)` boxes."""
    ax, ay, aw, ah = [float(v) for v in a]
    bx, by, bw, bh = [float(v) for v in b]
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    union = aw * ah + bw * bh - inter
    return float(inter / union) if union > 0 else 0.0


def box_contains(outer, inner):
    """True when `outer` covers `inner` completely."""
    ox, oy, ow, oh = [float(v) for v in outer]
    ix, iy, iw, ih = [float(v) for v in inner]
    return ix >= ox - 1e-6 and iy >= oy - 1e-6 and \
        ix + iw <= ox + ow + 1e-6 and iy + ih <= oy + oh + 1e-6


def box_union(boxes):
    xs = [b[0] for b in boxes]
    ys = [b[1] for b in boxes]
    xe = [b[0] + b[2] for b in boxes]
    ye = [b[1] + b[3] for b in boxes]
    x0, y0, x1, y1 = min(xs), min(ys), max(xe), max(ye)
    return (x0, y0, x1 - x0, y1 - y0)


def ink_bbox(img, tol=24):
    """The ink bounding box - the copy of `train/ppocr_data.py::ink_bbox`.

    Kept verbatim (it is the current cropper and the baseline of the
    measurement) so the numbers of this prototype and of the project agree.
    """
    a = np.asarray(img, dtype=np.int16)
    if a.ndim == 2:
        colors, counts = np.unique(a, return_counts=True)
        bg = colors[int(counts.argmax())]
        diff = np.abs(a - bg)
    else:
        flat = a.reshape(-1, a.shape[2])
        colors, counts = np.unique(flat, axis=0, return_counts=True)
        bg = colors[int(counts.argmax())]
        diff = np.abs(a - bg[None, None, :]).max(axis=2)
    mask = diff > tol
    if not mask.any():
        return (0, 0, img.width, img.height)
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    return (int(cols[0]), int(rows[0]),
            int(cols[-1] - cols[0] + 1), int(rows[-1] - rows[0] + 1))


# --------------------------------------------------------------------------- #
# small binary-image helpers (numpy only)
# --------------------------------------------------------------------------- #
def _dilate(mask, radius=1):
    out = mask
    for _ in range(radius):
        p = np.zeros((mask.shape[0] + 2, mask.shape[1] + 2), dtype=bool)
        p[1:-1, 1:-1] = out
        m = out
        out = (p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:] | m)
    return out


def _erode(mask, radius=1):
    out = mask
    for _ in range(radius):
        p = np.zeros((mask.shape[0] + 2, mask.shape[1] + 2), dtype=bool)
        p[1:-1, 1:-1] = out
        out = (p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:] & out)
    return out


def connected_components(mask):
    """Connected components of a boolean mask (4-connectivity).

    Implemented with a run-length scan + union-find: no scipy, no OpenCV.

    Returns a list of `(x0, y0, x1, y1, area)` with inclusive x1/y1.
    """
    h, w = mask.shape
    parent = []

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    runs = []          # (y, x0, x1, label)
    prev = []          # runs of the previous row
    for y in range(h):
        row = mask[y]
        if not row.any():
            prev = []
            continue
        padded = np.concatenate(([False], row, [False]))
        diff = np.diff(padded.astype(np.int8))
        starts = np.flatnonzero(diff == 1)
        ends = np.flatnonzero(diff == -1)
        cur = []
        for s, e in zip(starts, ends):
            label = len(parent)
            parent.append(label)
            runs.append((y, int(s), int(e) - 1, label))
            cur.append((int(s), int(e) - 1, label))
        # link with the previous row
        for (ca, cb, cl) in cur:
            for (pa, pb, pl) in prev:
                if pa <= cb and ca <= pb:      # x-ranges overlap
                    union(cl, pl)
        prev = cur

    agg = {}
    for (y, x0, x1, label) in runs:
        r = find(label)
        a = agg.get(r)
        if a is None:
            agg[r] = [x0, y, x1, y, x1 - x0 + 1]
        else:
            a[0] = min(a[0], x0)
            a[1] = min(a[1], y)
            a[2] = max(a[2], x1)
            a[3] = max(a[3], y)
            a[4] += x1 - x0 + 1
    return [(a[0], a[1], a[2], a[3], a[4]) for a in agg.values()]


# --------------------------------------------------------------------------- #
# classical detector
# --------------------------------------------------------------------------- #
# Parameters of the classical detector (all documented in the report).
CLASSICAL_PARAMS = {
    "quant_bits": 3,        # colour quantisation: colour >> (8 - quant_bits)
    "min_colour_frac": 0.0015,   # a colour must cover this much of the frame
    "max_colours": 16,      # how many quantised colours are examined
    "close_radius": 1,      # morphological closing before the CC
    "min_glyph_h": 3,       # a glyph is at least this tall (px)
    "max_glyph_h_frac": 0.62,
    "max_glyph_w_over_h": 3.0,
    "max_glyph_area_frac": 0.06,
    "min_glyph_density": 0.06,
    "row_tol": 0.45,        # vertical clustering tolerance (x glyph height)
    "min_row_glyphs": 2,
    "pad_x": 0.02,          # padding of the returned box (fraction of width)
    "pad_y": 0.10,
}


def _glyph_like(c, H, W, p):
    x0, y0, x1, y1, area = c
    w = x1 - x0 + 1
    h = y1 - y0 + 1
    if h < p["min_glyph_h"] or h > p["max_glyph_h_frac"] * H:
        return False
    if w < 1:
        return False
    if w > p["max_glyph_w_over_h"] * h:
        return False
    if area > p["max_glyph_area_frac"] * W * H:
        return False
    if area / float(w * h) < p["min_glyph_density"]:
        return False
    return True


def _cluster_rows(glyphs, p):
    """Group glyph boxes into horizontal rows (a text line)."""
    if not glyphs:
        return []
    items = []
    for c in glyphs:
        x0, y0, x1, y1, area = c
        items.append({"box": (x0, y0, x1 - x0 + 1, y1 - y0 + 1),
                      "cx": (x0 + x1) / 2.0,
                      "cy": (y0 + y1) / 2.0,
                      "h": y1 - y0 + 1,
                      "w": x1 - x0 + 1,
                      "area": area})
    items.sort(key=lambda it: it["cy"])
    rows = []
    for it in items:
        placed = False
        for row in rows:
            med_h = np.median([m["h"] for m in row])
            tol = p["row_tol"] * min(med_h, it["h"])
            if abs(it["cy"] - row["cy"]) <= tol:
                row["items"].append(it)
                row["cy"] = float(np.median([m["cy"] for m in row["items"]]))
                placed = True
                break
        if not placed:
            rows.append({"cy": it["cy"], "items": [it]})
    return rows


def _score_row(row, H, W):
    """How much does this row look like a line of answer glyphs?"""
    items = row["items"]
    n = len(items)
    hs = np.array([m["h"] for m in items], dtype=np.float64)
    cys = np.array([m["cy"] for m in items], dtype=np.float64)
    med_h = float(np.median(hs))
    if med_h <= 0:
        return -1e9
    align = float(np.exp(-np.std(cys) / (0.30 * med_h)))
    consist = float(np.exp(-np.std(hs) / (0.35 * med_h)))
    xs = sorted(m["box"][0] for m in items)
    ends = sorted(m["box"][0] + m["box"][2] for m in items)
    gaps = [ends[i + 1] - xs[i + 1] for i in range(len(xs) - 1)]
    med_gap = float(np.median(gaps)) if gaps else 0.0
    gap_pen = float(np.exp(-med_gap / (2.5 * med_h))) if gaps else 1.0
    count = min(n, 6) / 6.0
    area = sum(m["area"] for m in items) / float(W * H)
    dens = float(np.clip(area / (0.01 + 0.02 * n), 0.0, 1.0))
    # a text line does not normally span the whole frame width
    span = (max(ends) - min(xs)) / float(W)
    span_pen = float(np.exp(-((span - 0.75) ** 2) / 0.35))
    score = (align ** 2) * consist * gap_pen * count * dens * span_pen
    return score


def classical_detect(img, params=None):
    """Find the rectangle that holds the answer text.

    Algorithm (classical CV, numpy + PIL only):

    1. quantise the colours (`rgb >> (8 - q)`) and keep the colours that cover
       at least `min_colour_frac` of the frame - on a real server screenshot
       the glyphs are ONE solid colour, on a dataset frame the interference is
       drawn from a small palette, so in both cases the candidates are few;
    2. for every candidate colour build a mask, close it morphologically (the
       interference lines cut the glyphs) and take its connected components;
    3. keep the components that look like a glyph: not too tall, not a long
       thin stroke, not a huge blob, and not a sparse cloud;
    4. cluster the surviving components into horizontal rows and score each
       row by how much it looks like a line of text (aligned centres, similar
       heights, regular gaps, plausible size and span);
    5. return the bounding box of the best row, padded a little.

    Returns `None` when nothing looks like text.
    """
    p = dict(CLASSICAL_PARAMS)
    if params:
        p.update(params)
    if img.mode != "RGB":
        img = img.convert("RGB")
    a = np.asarray(img, dtype=np.uint8)
    H, W = a.shape[:2]
    if H < 4 or W < 4:
        return None

    shift = 8 - p["quant_bits"]
    q = (a >> shift) << shift
    flat = q.reshape(-1, 3).astype(np.int64)
    key = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
    uniq, counts = np.unique(key, return_counts=True)
    min_count = max(16, int(p["min_colour_frac"] * H * W))
    order = np.argsort(-counts)
    cand = [int(uniq[i]) for i in order if counts[i] >= min_count][:p["max_colours"]]

    glyphs = []
    for ck in cand:
        mask = key.reshape(H, W) == ck
        if p["close_radius"]:
            mask = _dilate(mask, p["close_radius"])
            mask = _erode(mask, p["close_radius"])
        for c in connected_components(mask):
            if _glyph_like(c, H, W, p):
                glyphs.append(c)
    if not glyphs:
        return None

    rows = _cluster_rows(glyphs, p)
    best, best_score = None, -1e9
    for row in rows:
        if len(row["items"]) < p["min_row_glyphs"]:
            continue
        s = _score_row(row, H, W)
        if s > best_score:
            best_score, best = s, row
    if best is None:
        # a single glyph is still better than nothing
        rows = sorted(rows, key=lambda r: -len(r["items"]))
        if not rows:
            return None
        best = rows[0]
    box = box_union([m["box"] for m in best["items"]])
    px = int(round(p["pad_x"] * box[2]))
    py = int(round(p["pad_y"] * box[3]))
    x = max(0, int(box[0]) - px)
    y = max(0, int(box[1]) - py)
    w = min(W - x, int(box[2]) + 2 * px)
    h = min(H - y, int(box[3]) + 2 * py)
    if w <= 0 or h <= 0:
        return None
    return (x, y, w, h)


# --------------------------------------------------------------------------- #
# learned detector
# --------------------------------------------------------------------------- #
class TinyUNet:
    """A compact U-Net: ~170k parameters, segmentation of the answer band.

    The net does NOT know the size of the frame: every image is scaled into a
    square canvas (the aspect ratio is kept, the rest is padded), so the same
    net works on a 128x128 dataset frame and on a 458x343 screenshot.
    """

    def __init__(self, in_ch=3, base=(12, 24, 48, 64)):
        import torch
        import torch.nn as nn
        torch = torch
        c1, c2, c3, c4 = base

        def blk(i, o):
            return nn.Sequential(
                nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
            )

        self.e1 = blk(in_ch, c1)
        self.e2 = blk(c1, c2)
        self.e3 = blk(c2, c3)
        self.e4 = blk(c3, c4)
        self.d3 = blk(c4 + c3, c3)
        self.d2 = blk(c3 + c2, c2)
        self.d1 = blk(c2 + c1, c1)
        self.out = nn.Conv2d(c1, 1, 1)
        self.pool = nn.MaxPool2d(2)
        self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False)

    def forward(self, x):
        import torch
        import torch.nn.functional as F
        e1 = self.e1(x)
        e2 = self.e2(self.pool(e1))
        e3 = self.e3(self.pool(e2))
        e4 = self.e4(self.pool(e3))
        d3 = self.d3(torch.cat([self.up(e4), e3], dim=1))
        d2 = self.d2(torch.cat([self.up(d3), e2], dim=1))
        d1 = self.d1(torch.cat([self.up(d2), e1], dim=1))
        return self.out(d1)


CANVAS = 128          # the square canvas of the learned detector


def scale_to_canvas(img, canvas=CANVAS):
    """Image -> (canvas x canvas) tensor + the transform that maps back."""
    import torch
    w, h = img.size
    s = canvas / float(max(w, h))
    nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    small = img.resize((nw, nh), Image.BILINEAR)
    canvas_img = Image.new("RGB", (canvas, canvas), (0, 0, 0))
    ox, oy = (canvas - nw) // 2, (canvas - nh) // 2
    canvas_img.paste(small, (ox, oy))
    arr = np.asarray(canvas_img, dtype=np.float32) / 255.0
    arr = (arr - 0.5) / 0.5
    arr = np.ascontiguousarray(arr.transpose(2, 0, 1))
    return torch.from_numpy(arr), (s, ox, oy)


def canvas_to_box(box_canvas, w, h, transform):
    """A box in canvas coordinates -> a box in the original image."""
    s, ox, oy = transform
    x0, y0, bw, bh = [float(v) for v in box_canvas]
    x0 = (x0 - ox) / s
    y0 = (y0 - oy) / s
    bw = bw / s
    bh = bh / s
    x0 = max(0.0, x0)
    y0 = max(0.0, y0)
    bw = min(float(w) - x0, bw)
    bh = min(float(h) - y0, bh)
    if bw <= 0 or bh <= 0:
        return None
    return (int(round(x0)), int(round(y0)), int(round(bw)), int(round(bh)))


class LearnedDetector:
    """The trained U-Net: image -> the rectangle of the answer band."""

    def __init__(self, path=None, device="cpu"):
        import torch
        self.torch = torch
        path = path or os.path.join(HERE, "detector.pt")
        blob = torch.load(path, map_location="cpu", weights_only=False)
        self.meta = blob.get("meta", {})
        self.net = TinyUNet()
        self.net.load_state_dict(blob["model"])
        self.net.to(device).eval()
        self.device = device
        self.threshold = float(self.meta.get("threshold", 0.5))

    def mask(self, img):
        torch = self.torch
        if img.mode != "RGB":
            img = img.convert("RGB")
        x, _ = scale_to_canvas(img)
        with torch.no_grad():
            logits = self.net(x.unsqueeze(0).to(self.device))
            prob = torch.sigmoid(logits.float())[0, 0].cpu().numpy()
        return prob

    def detect(self, img):
        prob = self.mask(img)
        m = prob >= self.threshold
        if not m.any():
            return None
        rows = np.flatnonzero(m.any(axis=1))
        cols = np.flatnonzero(m.any(axis=0))
        box_canvas = (int(cols[0]), int(rows[0]),
                      int(cols[-1] - cols[0] + 1), int(rows[-1] - rows[0] + 1))
        w, h = img.size
        # the canvas is square; the image sits centred inside it
        return canvas_to_box(box_canvas, w, h, self._transform(img))

    def _transform(self, img):
        w, h = img.size
        s = CANVAS / float(max(w, h))
        nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
        return (s, (CANVAS - nw) // 2, (CANVAS - nh) // 2)


# --------------------------------------------------------------------------- #
# the dispatcher used by the evaluation script
# --------------------------------------------------------------------------- #
def make_detector(method):
    """`method` in {"classical", "learned", "oracle", "ink"} -> a callable."""
    if method == "classical":
        return lambda img: classical_detect(img)
    if method == "learned":
        det = LearnedDetector()

        def f(img):
            return det.detect(img)
        f.detector = det
        return f
    if method == "ink":
        return lambda img: ink_bbox(img)
    raise ValueError("unknown method: %s" % method)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
