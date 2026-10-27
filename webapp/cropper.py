#!/usr/bin/env python
"""Cropper - find the band that holds the answer text in an arbitrary frame.

    from cropper import candidates
    for c in candidates(img):
        box, method, crop_image = c.box, c.method, c.image

The module is deliberately small and dependency-free: **numpy + Pillow + the
standard library only**.  It never imports torch, never loads a model and never
writes to disk.  It answers one question: *where in this picture is the text
that has to be read, and what should the recogniser be shown?*

Why this exists
---------------
`webapp/app.py` used to fall back to `ink_bbox` - "the pixels that differ from
the most common colour" - when a picture arrived without a band.  On a frame
covered by interference that fallback degenerates: the interference strokes
count as ink, so the ink box is the whole canvas and the recogniser gets a
noise picture instead of a band.  Measured on the owner's own screenshots:
`ink_bbox` returns the **whole frame** for all six, and the recogniser reads
2 of 6 correctly.  This module replaces that fallback with a layered decision:

    layer (a)  per-type / per-style heuristics - a table keyed by the captcha
               style (and, when the caller knows it, by the dataset type id);
    layer (b)  a strengthened ink box - the "crop to the ink" idea, but the
               background is estimated from *local stability* and the thin
               strokes (the interference) are removed by a morphological
               opening instead of being counted as ink;
    layer (c)  a tiny glyph detector - colour clustering, connected components
               and a search for a row of glyph-shaped components.  No learned
               weights, no extra dependencies, milliseconds per picture.

Layers (b) and (c) are *propositions*, not answers: a frame can hold several
plausible bands and a crop can be right for the wrong reason.  So the module
returns an **ordered list of candidates** and the caller (the web app) reads
each of them with the recogniser and keeps the most confident one.  The
recogniser's own confidence is the vote - the tiny detector proposes, the
model disposes.

The design notes and the measured numbers live in `reports/CROPPER.md`.
"""

import numpy as np

# --------------------------------------------------------------------------- #
# tunables
# --------------------------------------------------------------------------- #
# how close two colours must be to be considered "the same colour" (L∞ in RGB)
COLOR_TOL = 10
# how many of the most frequent colours are examined as digit-colour candidates
MAX_COLOR_CANDIDATES = 48
# a connected component is a glyph candidate if ...
GLYPH_MIN_H = 0.12       # ... its height is at least this fraction of the frame
GLYPH_MAX_H = 0.62       # ... and at most this fraction
GLYPH_MAX_W_RATIO = 1.80  # ... and its width is at most this * its height
GLYPH_MIN_AREA = 24      # ... and it has at least this many pixels
# the row of glyphs must fill at least this fraction of the frame width
ROW_MIN_SPAN = 0.10
# how close to the middle of the frame the row must be (1.0 = anywhere)
ROW_CENTER_TOL = 0.40
# how many candidates the caller gets by default
DEFAULT_LIMIT = 32


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
class CropResult(object):
    """What `crop()` returns: the band, the method that found it, optionally a
    *rendering* of the band (the pixels the recogniser should see)."""

    __slots__ = ("box", "method", "image", "detail")

    def __init__(self, box, method, image=None, detail=None):
        self.box = list(box) if box is not None else None
        self.method = method
        self.image = image
        self.detail = detail or {}

    def __iter__(self):
        """`box, method = result` works."""
        yield self.box
        yield self.method

    def __repr__(self):
        return "CropResult(box=%r, method=%r)" % (self.box, self.method)


def clamp_box(box, width, height):
    """Clamp [x, y, w, h] inside the frame; None when it collapses."""
    if box is None:
        return None
    x, y, w, h = [int(round(float(v))) for v in box]
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    return [x, y, w, h]


def box_of(mask):
    """The tight bounding box of the set pixels of a mask."""
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return None
    return [int(xs.min()), int(ys.min()),
            int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]


# --------------------------------------------------------------------------- #
# connected components (numpy only, run based)
# --------------------------------------------------------------------------- #
def label_components(mask):
    """4-connected labelling of a boolean mask.

    Returns `(labels, n, stats)`; `labels` is an int32 array, 0 = background,
    `stats` holds `[x0, x1, y0, y1, area]` per label.  The implementation walks
    the horizontal runs of every row and unions the runs that overlap - the
    classic two-pass algorithm with a union-find, but without scipy.
    """
    mask = np.ascontiguousarray(mask, dtype=bool)
    h, w = mask.shape
    parent = [0]

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:      # path compression
            parent[a], a = root, parent[a]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    rows = []
    prev = []
    for y in range(h):
        line = np.concatenate((np.zeros(1, np.int8), mask[y].view(np.int8), np.zeros(1, np.int8)))
        d = np.diff(line)
        starts = np.flatnonzero(d == 1)
        ends = np.flatnonzero(d == -1)
        cur = []
        for s, e in zip(starts.tolist(), ends.tolist()):
            lab = 0
            for (ps, pe, pl) in prev:
                if ps < e and s < pe:
                    if lab == 0:
                        lab = pl
                    else:
                        union(lab, pl)
            if lab == 0:
                parent.append(len(parent))
                lab = len(parent) - 1
            cur.append((s, e, lab))
        rows.append(cur)
        prev = cur

    remap = {}
    stats = []          # per label: [x0, x1, y0, y1, area]
    next_id = 1
    for y, cur in enumerate(rows):
        for (s, e, lab) in cur:
            r = find(lab)
            rid = remap.get(r)
            if rid is None:
                rid = next_id
                remap[r] = rid
                stats.append([s, e - 1, y, y, e - s])
                next_id += 1
            else:
                st = stats[rid - 1]
                if s < st[0]:
                    st[0] = s
                if e - 1 > st[1]:
                    st[1] = e - 1
                st[3] = y
                st[4] += e - s
    labels = np.zeros((h, w), dtype=np.int32)
    for y, cur in enumerate(rows):
        for (s, e, lab) in cur:
            labels[y, s:e] = remap[find(lab)]
    return labels, next_id - 1, stats


def _dilate(mask, r=1):
    out = np.ascontiguousarray(mask, dtype=bool)
    h, w = out.shape
    for _ in range(r):
        p = np.pad(out, 1, constant_values=False)
        m = p[0:h, 0:w].copy()
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                m |= p[dy:dy + h, dx:dx + w]
        out = m
    return out


def _erode(mask, r=1):
    out = np.ascontiguousarray(mask, dtype=bool)
    h, w = out.shape
    for _ in range(r):
        p = np.pad(out, 1, constant_values=False)
        m = p[0:h, 0:w].copy()
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                m &= p[dy:dy + h, dx:dx + w]
        out = m
    return out


def opening(mask, r=1):
    """Morphological opening - keeps only what contains an r-disk."""
    if r <= 0:
        return mask
    return _dilate(_erode(mask, r), r)


def closing(mask, r=1):
    """Morphological closing - fills what an r-disk can cover."""
    if r <= 0:
        return mask
    return _erode(_dilate(mask, r), r)


def fill_holes(mask):
    """Fill the holes of a mask.

    Every row and every column is filled between its first and its last set
    pixel.  For a character (a round shape with counters) that fills the
    counters - the hollow of an 8 - and it is enough for the recogniser: the
    strokes become solid.  It is not an exact flood fill, but it is fast and
    it never leaks outside the shape's bounding box.
    """
    out = np.ascontiguousarray(mask, dtype=bool).copy()
    if not out.any():
        return out
    h, w = out.shape
    idx = np.arange(w)
    first = np.minimum.accumulate(np.where(out, idx, w), axis=1)
    last = np.maximum.accumulate(np.where(out, idx, -1), axis=1)
    out |= (idx[None, :] >= first) & (idx[None, :] <= last)
    idx = np.arange(h)
    first = np.minimum.accumulate(np.where(out, idx[:, None], h), axis=0)
    last = np.maximum.accumulate(np.where(out, idx[:, None], -1), axis=0)
    out |= (idx[:, None] >= first) & (idx[:, None] <= last)
    return out


# --------------------------------------------------------------------------- #
# layer (c): the glyph detector
# --------------------------------------------------------------------------- #
def color_candidates(a, topk=MAX_COLOR_CANDIDATES):
    """The most frequent colours of the frame, merged into colour groups.

    A captcha draws its code in *one* solid colour; the antialiasing and the
    interference split that colour over a few neighbouring RGB values.  The
    groups are therefore merged with a small L∞ tolerance.  The colours are
    packed into one int32 before the histogram - `np.unique(axis=0)` on a full
    frame costs 10x more.
    """
    flat = a.reshape(-1, 3).astype(np.int32)
    packed = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
    values, counts = np.unique(packed, return_counts=True)
    order = np.argsort(-counts)[:topk]
    groups = []                       # [rep(3), total_count]
    for i in order:
        v = int(values[i])
        c = np.array([(v >> 16) & 255, (v >> 8) & 255, v & 255], dtype=np.int32)
        n = int(counts[i])
        placed = False
        for g in groups:
            if int(np.abs(g[0] - c).max()) <= COLOR_TOL:
                g[1] += n
                placed = True
                break
        if not placed:
            groups.append([c, n])
    groups.sort(key=lambda g: -g[1])
    return [(g[0], g[1]) for g in groups]


def color_mask(a, ref, tol=COLOR_TOL):
    """The pixels of the frame that are (nearly) one colour."""
    diff = np.abs(a.astype(np.int16) - ref.astype(np.int16)[None, None, :])
    return diff.max(axis=2) <= tol


def glyph_candidates(stats, height, width):
    """The connected components that look like a character."""
    out = []
    for (x0, x1, y0, y1, area) in stats:
        if area < GLYPH_MIN_AREA:
            continue
        h = y1 - y0 + 1
        w = x1 - x0 + 1
        if h < GLYPH_MIN_H * height or h > GLYPH_MAX_H * height:
            continue
        if w > GLYPH_MAX_W_RATIO * h:
            continue
        out.append({"x0": x0, "x1": x1, "y0": y0, "y1": y1, "area": area,
                    "w": w, "h": h, "cx": 0.5 * (x0 + x1), "cy": 0.5 * (y0 + y1)})
    return out


def best_row(glyphs, height, width):
    """The best horizontal row of glyph candidates.

    A row is a set of glyphs that overlap vertically, share a similar height
    and are spread horizontally.  The digits of a captcha are exactly that:
    a few characters of a similar height, side by side, in the middle of the
    frame.
    """
    if not glyphs:
        return None
    groups = []
    for g in sorted(glyphs, key=lambda d: d["cy"]):
        for grp in groups:
            g0 = min(d["y0"] for d in grp)
            g1 = max(d["y1"] for d in grp)
            overlap = min(g1, g["y1"]) - max(g0, g["y0"]) + 1
            if overlap > 0.45 * min(g["h"], g1 - g0 + 1):
                grp.append(g)
                break
        else:
            groups.append([g])

    best = None
    for grp in groups:
        grp = sorted(grp, key=lambda d: d["x0"])
        heights = np.array([d["h"] for d in grp], dtype=np.float64)
        med = float(np.median(heights))
        keep = [d for d in grp if 0.55 * med <= d["h"] <= 1.8 * med]
        if len(keep) < 2:
            keep = grp
        x0 = min(d["x0"] for d in keep)
        x1 = max(d["x1"] for d in keep)
        y0 = min(d["y0"] for d in keep)
        y1 = max(d["y1"] for d in keep)
        span = (x1 - x0 + 1) / float(width)
        cy = 0.5 * (y0 + y1) / float(height)
        near_center = max(0.0, 1.0 - abs(cy - 0.5) / ROW_CENTER_TOL)
        area = sum(d["area"] for d in keep)
        if span < ROW_MIN_SPAN:
            continue
        score = len(keep) * (0.6 + 0.4 * near_center) * (0.5 + 0.5 * min(1.0, span / 0.6))
        score *= min(1.0, area / 600.0) ** 0.35
        if best is None or score > best["score"]:
            best = {"score": score, "n": len(keep), "box": [x0, y0, x1 - x0 + 1, y1 - y0 + 1],
                    "area": area, "span": span}
    return best


def detect_glyph_band(a):
    """Layer (c): find the band of the code inside an arbitrary frame.

    Returns `(box, info)` - `box` is None when nothing glyph-like was found.
    """
    height, width = a.shape[:2]
    best = None
    for ref, count in color_candidates(a):
        mask = color_mask(a, ref)
        if mask.sum() < 100:
            continue
        # the thick structures only: the interference strokes are thin
        thick = opening(mask, 2)
        if not thick.any():
            continue
        labels, n, stats = label_components(thick)
        if n == 0:
            continue
        glyphs = glyph_candidates(stats, height, width)
        row = best_row(glyphs, height, width)
        if row is None:
            continue
        # prefer a candidate that both looks like a row and is a big colour
        score = row["score"] * (0.5 + 0.5 * min(1.0, count / (0.02 * height * width)))
        if best is None or score > best["score"]:
            best = {"score": score, "box": row["box"], "color": tuple(int(x) for x in ref),
                    "count": count, "n_glyphs": row["n"]}
    if best is None:
        return None, {}
    return clamp_box(best["box"], width, height), best


# --------------------------------------------------------------------------- #
# layer (b): the strengthened ink box
# --------------------------------------------------------------------------- #
def stable_mask(a, win=7):
    """The pixels that sit in a locally *stable* neighbourhood.

    A solid stroke (the body of a character) is locally constant, a thin
    interference line is not (the window sees both sides of the line) and a
    noisy background is not either.  This is what makes the box finder work on
    a frame the "most common colour" cannot describe.
    """
    g = a.astype(np.float32)
    h, w = g.shape[:2]
    if h < win or w < win:
        return np.ones((h, w), dtype=bool)
    # local variance per channel, as a win x win box filter (integral image)
    r = win // 2
    var = np.zeros((h, w), dtype=np.float32)
    area = float(win * win)
    for c in range(3):
        ch = g[:, :, c]
        pad = np.pad(ch, r, mode="edge")
        ii = np.pad(pad.cumsum(axis=0).cumsum(axis=1), ((1, 0), (1, 0)))
        s = (ii[win:, win:] - ii[:-win, win:] - ii[win:, :-win] + ii[:-win, :-win])
        var += (s / area) ** 2
    var /= 3.0
    # a stable pixel is a local maximum of the smoothed variance
    mean = var.mean()
    return var <= max(2.0, 0.35 * mean + 1.0)


def ink_box(a, win=7):
    """Layer (b): the strengthened ink box.

    The thin strokes are dropped and only the regions that are both locally
    stable and big enough survive; their bounding box is the band.
    """
    height, width = a.shape[:2]
    stable = stable_mask(a, win)
    if not stable.any():
        return None, {}
    solid = opening(stable, 2)
    if not solid.any():
        solid = stable
    labels, n, stats = label_components(solid)
    if n == 0:
        return None, {}
    keep = []
    for st in stats:
        area = st[4]
        h = st[3] - st[2] + 1
        w = st[1] - st[0] + 1
        if area >= max(30, 0.001 * height * width) and h >= 2 and w >= 2:
            keep.append(st)
    if not keep:
        # no solid blob: fall back to the tight box of every stable pixel
        box = box_of(stable)
        return (clamp_box(box, width, height), {"n": 1}) if box else (None, {})
    x0 = min(st[0] for st in keep)
    x1 = max(st[1] for st in keep)
    y0 = min(st[2] for st in keep)
    y1 = max(st[3] for st in keep)
    return clamp_box([x0, y0, x1 - x0 + 1, y1 - y0 + 1], width, height), {"n": len(keep)}


# --------------------------------------------------------------------------- #
# layer (a): per-type / per-style heuristics
# --------------------------------------------------------------------------- #
# The table is keyed by the id of a dataset type (`out/<owner>/<repo>/<type>`);
# a rule says where the code sits in that type's frames.  The rules are *not*
# taken from `labels.jsonl` - they describe the layout of the plugin, e.g.
# "the code is drawn in the lower half of the frame".
TYPE_HEURISTICS = {
    # type id -> (relative box, note)
    "out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map": ([0.02, 0.55, 0.96, 0.42], "code in the lower half"),
    "out/haq/mapcha/map": ([0.05, 0.30, 0.90, 0.45], "code under the header"),
}

# The relative bands learned from `labels.jsonl`: type id -> [rx, ry, rw, rh].
# The web app fills this table at startup from the dataset (the median band of
# the type, normalised by the frame), so a *known* type is cropped exactly
# where its answer is - the "per-plugin constant" the project's own research
# says the cropper should be.  A frame of an **unknown** type falls back to
# the generic layers below.
_LEARNED_BANDS = {}


def set_type_bands(bands):
    """Register the relative bands of the known types (type id -> [rx,ry,rw,rh])."""
    _LEARNED_BANDS.clear()
    _LEARNED_BANDS.update(bands or {})
    return len(_LEARNED_BANDS)


def type_heuristic(type_id, width, height):
    """The band of a known type, or None."""
    rule = _LEARNED_BANDS.get(type_id)
    note = "learned from labels.jsonl"
    if rule is None:
        rule = TYPE_HEURISTICS.get(type_id)
        if not rule:
            return None
        note = "hand-written rule"
    if isinstance(rule, (tuple, list)) and len(rule) == 2 and isinstance(rule[1], str):
        rule, note = rule[0], note + " / " + rule[1]
    rx, ry, rw, rh = [float(v) for v in rule]
    box = clamp_box([rx * width, ry * height, rw * width, rh * height], width, height)
    return box, note


# --------------------------------------------------------------------------- #
# the candidate list
# --------------------------------------------------------------------------- #
def render_binary(mask, shape):
    """Black glyphs on a white canvas - the rendering a recogniser reads best
    when the frame is full of interference."""
    canvas = np.full(tuple(shape) + (3,), 255, np.uint8)
    canvas[mask] = 0
    return canvas


def render_keep(a, mask):
    """The *original* pixels of the glyphs on a white canvas.

    The captcha draws its code in one colour; the interference around it is
    noise for the recogniser.  Keeping the original pixels (instead of black)
    and dropping everything else gives the recogniser a clean, still-coloured
    character - and the anti-aliased edge of the stroke has to be kept, so the
    mask is dilated by one pixel before the canvas is built.

    Measured on the owner's six screenshots: this rendering is read correctly
    on all six (confidence 0.92 - 1.00), where the plain crop of the same
    band is not.
    """
    canvas = np.full(a.shape, 255, np.uint8)
    sel = mask
    if sel.any():
        canvas[sel] = a[sel]
    return canvas


def _crop_render(canvas, box):
    """The rendering, cropped to its own band."""
    x, y, w, h = box
    return canvas[y:y + h, x:x + w]


def _colour_bank(a, limit=6, scale=2, full_k=14):
    """The most plausible "code colour" candidates, with their masks.

    A colour is plausible when its pixels form a few chunky components in the
    middle of the frame - that is what a captcha's code looks like.  The
    interference colours fail that test, so they never become candidates.

    The component labelling is the expensive part, and the shape of a glyph
    does not change with the resolution - but a **thin translucent** stroke
    can vanish from the subsampled mask.  So the frequent colours (the first
    `full_k`) are analysed in the full resolution, the rare ones on a
    `scale`-times smaller copy.
    """
    height, width = a.shape[:2]
    small = a[::scale, ::scale] if scale > 1 else a
    sh, sw = small.shape[:2]
    out = []
    # the colours are counted on the **full** frame: a thin translucent stroke
    # can vanish completely from the subsampled histogram
    for rank, (ref, count) in enumerate(color_candidates(a)):
        full = color_mask(a, ref)
        if full.sum() < 120:
            continue
        if rank < full_k:
            mask, mh, mw = full, height, width
        else:
            mask, mh, mw = full[::scale, ::scale], sh, sw
        labels, n, stats = label_components(opening(mask, 2) if mask.sum() > 4000 else mask)
        glyphs = glyph_candidates(stats, mh, mw)
        if not glyphs:
            continue
        row = best_row(glyphs, mh, mw)
        if row is None:
            continue
        score = row["score"] * (0.6 + 0.4 * min(1.0, count / (0.02 * mh * mw)))
        out.append({"color": tuple(int(x) for x in ref), "count": count, "mask": full,
                    "score": score, "n_glyphs": row["n"]})
    out.sort(key=lambda d: -d["score"])
    return out[:limit]


def strip_candidates(img, ks=(3, 4)):
    """Full-width horizontal strips - the captcha-scale analogue of a tile grid.

    The idea comes from Unlimited OCR 2 (Baidu, MIT): their "gundam" dynamic
    tiling shows the recogniser the page at several scales and lets its
    confidence choose.  Their tiles are 640x640 document pages; for a captcha
    frame the analogue of a tile is a **horizontal strip** - the unit that
    carries one line of text.

    Measured on our own frames (see `reports/UNLIMITED_OCR.md` §2.6): adding
    the strips to the candidate list helps a lot on the types where the answer
    is one line among several (`just-captcha/ProstoCaptcha/map` 0.100 ->
    0.900) and hurts on the types where the base answer is already certain -
    so the caller should use them only when the base answer is not confident.
    """
    W, H = img.size
    out = []
    for k in ks:
        for i in range(k):
            y0 = int(round(i * H / float(k)))
            y1 = int(round((i + 1) * H / float(k)))
            if y1 - y0 < 8:
                continue
            out.append(CropResult([0, y0, W, y1 - y0], "strip:k=%d,i=%d" % (k, i),
                                   detail={"prior": 0.2}))
    return out


def candidates(img, type_id=None, limit=DEFAULT_LIMIT, colour_limit=8):
    """The ordered list of bands worth reading.

    Each entry is a `CropResult` whose `image` is the **cropped rendering**
    the recogniser should see (or None when the crop of the original frame is
    wanted).  The list is ordered by a geometric prior; the caller is expected
    to read the first few and keep the most confident answer.

    The variants per colour are:
      * `raw`    - the original pixels, cropped to the colour's box;
      * `clean`  - the colour's pixels alone, holes filled, on white;
      * `open`   - the same after an opening (the thin strokes are gone);
      * `close`  - the same after a closing (the strokes are thicker).
    """
    a = np.asarray(img.convert("RGB"))
    height, width = a.shape[:2]
    shape = (height, width)
    out = []

    # ---- layer (a): the per-type table ------------------------------- #
    if type_id:
        hit = type_heuristic(type_id, width, height)
        if hit:
            box, note = hit
            out.append(CropResult(box, "type-heuristic:%s" % note,
                                  detail={"prior": 1.0}))

    # ---- layer (c): the glyph detector, and its renderings ----------- #
    # The variants of one colour are interleaved with the variants of the
    # others, so that truncating the list keeps the *diversity* of the
    # proposals instead of the variants of the first colour only.
    banks = _colour_bank(a, limit=colour_limit)
    per_colour = []
    for i, cand in enumerate(banks):
        mask = cand["mask"]
        box = box_of(mask)
        if box is None:
            continue
        box = clamp_box(box, width, height)
        x, y, w, h = box
        variants = [
            # the glyphs keep their own colour on a white canvas; the mask is
            # dilated by one pixel so that the anti-aliased edge of the stroke
            # survives (without it the recogniser reads a 6 as an l)
            ("keep", render_keep(a, _dilate(mask, 1))),
            ("keep2", render_keep(a, _dilate(closing(mask, 2), 1))),
            ("keep4", render_keep(a, _dilate(closing(mask, 4), 1))),
            # the plain crop of the original frame - what the model saw when
            # it was trained on whole frames
            ("crop", None),
        ]
        per_colour.append((cand, box, variants, 0.005 * i))

    depth = max((len(v) for (_c, _b, v, _p) in per_colour), default=0)
    for rank in range(depth):
        for (cand, box, variants, penalty) in per_colour:
            if rank >= len(variants):
                continue
            name, canvas = variants[rank]
            img = None if canvas is None else _crop_render(canvas, box)
            out.append(CropResult(box, "%s:%s" % (name, (cand["color"],)),
                                  image=img,
                                  detail={"prior": 1.0 - 0.02 * rank - penalty}))

    # ---- layer (b): the strengthened ink box --------------------------- #
    box, info = ink_box(a)
    if box is not None:
        out.append(CropResult(box, "ink-box", detail={"prior": 0.5}))

    # ---- the frame itself, as the last resort ------------------------- #
    out.append(CropResult(None, "whole-frame", detail={"prior": 0.25}))

    # the geometric prior orders the list; the recogniser's confidence picks
    # the winner among the first `limit` of them
    out.sort(key=lambda c: -c.detail.get("prior", 0.0))
    return out[:limit] if limit else out


def crop(img, type_id=None):
    """The single best band of a frame (no model, no voting).

    Kept for the callers that only need a box; the web app uses
    `candidates()` instead.
    """
    a = np.asarray(img.convert("RGB"))
    height, width = a.shape[:2]
    if type_id:
        hit = type_heuristic(type_id, width, height)
        if hit:
            box, note = hit
            return CropResult(box, "type-heuristic:%s" % note)
    box, info = detect_glyph_band(a)
    if box is not None:
        return CropResult(box, "glyph-detector",
                          detail={"color": info.get("color"), "n_glyphs": info.get("n_glyphs"),
                                  "score": round(info.get("score", 0.0), 3)})
    box, info = ink_box(a)
    if box is not None:
        return CropResult(box, "ink-box", info)
    return CropResult(None, "whole-frame", {})
