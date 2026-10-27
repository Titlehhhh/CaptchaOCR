#!/usr/bin/env python
import numpy as np

COLOR_TOL = 10
MAX_COLOR_CANDIDATES = 48
GLYPH_MIN_H = 0.12       # ... its height is at least this fraction of the frame
GLYPH_MAX_H = 0.62       # ... and at most this fraction
GLYPH_MAX_W_RATIO = 1.80  # ... and its width is at most this * its height
GLYPH_MIN_AREA = 24      # ... and it has at least this many pixels
ROW_MIN_SPAN = 0.10
ROW_CENTER_TOL = 0.40
DEFAULT_LIMIT = 32

class CropResult(object):
    __slots__ = ("box", "method", "image", "detail")

    def __init__(self, box, method, image=None, detail=None):
        self.box = list(box) if box is not None else None
        self.method = method
        self.image = image
        self.detail = detail or {}

    def __iter__(self):
        yield self.box
        yield self.method

    def __repr__(self):
        return "CropResult(box=%r, method=%r)" % (self.box, self.method)

def clamp_box(box, width, height):
    if box is None:
        return None
    x, y, w, h = [int(round(float(v))) for v in box]
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    return [x, y, w, h]

def box_of(mask):
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return None
    return [int(xs.min()), int(ys.min()),
            int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]

def label_components(mask, stats_only=False):
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
    if stats_only:
        return None, next_id - 1, stats
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
    if r <= 0:
        return mask
    return _dilate(_erode(mask, r), r)

def closing(mask, r=1):
    if r <= 0:
        return mask
    return _erode(_dilate(mask, r), r)

def fill_holes(mask):
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

def color_candidates(a, topk=MAX_COLOR_CANDIDATES):
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
    diff = np.abs(a.astype(np.int16) - ref.astype(np.int16)[None, None, :])
    return diff.max(axis=2) <= tol

def glyph_candidates(stats, height, width):
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

def row_groups(glyphs):
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
    return groups

def rows_with_boxes(glyphs, height, width):
    out = []
    for grp in row_groups(glyphs):
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
        out.append({"score": score, "n": len(keep), "area": area, "span": span,
                    "box": [x0, y0, x1 - x0 + 1, y1 - y0 + 1]})
    out.sort(key=lambda r: -r["score"])
    return out

def best_row(glyphs, height, width):
    rows = rows_with_boxes(glyphs, height, width)
    return rows[0] if rows else None

def detect_glyph_band(a):
    height, width = a.shape[:2]
    best = None
    for ref, count in color_candidates(a):
        mask = color_mask(a, ref)
        if mask.sum() < 100:
            continue
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
        score = row["score"] * (0.5 + 0.5 * min(1.0, count / (0.02 * height * width)))
        if best is None or score > best["score"]:
            best = {"score": score, "box": row["box"], "color": tuple(int(x) for x in ref),
                    "count": count, "n_glyphs": row["n"]}
    if best is None:
        return None, {}
    return clamp_box(best["box"], width, height), best

def stable_mask(a, win=7):
    g = a.astype(np.float32)
    h, w = g.shape[:2]
    if h < win or w < win:
        return np.ones((h, w), dtype=bool)
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
    mean = var.mean()
    return var <= max(2.0, 0.35 * mean + 1.0)

def ink_box(a, win=7):
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
        box = box_of(stable)
        return (clamp_box(box, width, height), {"n": 1}) if box else (None, {})
    x0 = min(st[0] for st in keep)
    x1 = max(st[1] for st in keep)
    y0 = min(st[2] for st in keep)
    y1 = max(st[3] for st in keep)
    return clamp_box([x0, y0, x1 - x0 + 1, y1 - y0 + 1], width, height), {"n": len(keep)}

TYPE_HEURISTICS = {
    "out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map": ([0.02, 0.55, 0.96, 0.42], "code in the lower half"),
    "out/haq/mapcha/map": ([0.05, 0.30, 0.90, 0.45], "code under the header"),
}
_LEARNED_BANDS = {}

def set_type_bands(bands):
    _LEARNED_BANDS.clear()
    _LEARNED_BANDS.update(bands or {})
    return len(_LEARNED_BANDS)

def type_heuristic(type_id, width, height):
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

def render_binary(mask, shape):
    canvas = np.full(tuple(shape) + (3,), 255, np.uint8)
    canvas[mask] = 0
    return canvas

def render_keep(a, mask):
    canvas = np.full(a.shape, 255, np.uint8)
    sel = mask
    if sel.any():
        canvas[sel] = a[sel]
    return canvas

def _crop_render(canvas, box):
    x, y, w, h = box
    return canvas[y:y + h, x:x + w]

def _colour_bank(a, limit=6, scale=2, full_k=14, max_scan=20, max_rows=4):
    height, width = a.shape[:2]
    small = a[::scale, ::scale] if scale > 1 else a
    sh, sw = small.shape[:2]
    out = []
    for rank, (ref, count) in enumerate(color_candidates(a)):
        if rank >= max_scan or len(out) >= limit * 2:
            break
        if count < 120:
            continue                       # too few pixels to be a code
        full = color_mask(a, ref)
        if full.sum() < 120:
            continue
        if rank < full_k:
            mask, mh, mw = full, height, width
        else:
            mask, mh, mw = full[::scale, ::scale], sh, sw
        labels, n, stats = label_components(opening(mask, 2) if mask.sum() > 4000 else mask,
                                           stats_only=True)
        glyphs = glyph_candidates(stats, mh, mw)
        if not glyphs:
            continue
        rows = rows_with_boxes(glyphs, mh, mw)
        if not rows:
            continue
        row = rows[0]
        score = row["score"] * (0.6 + 0.4 * min(1.0, count / (0.02 * mh * mw)))
        out.append({"color": tuple(int(x) for x in ref), "count": count, "mask": full,
                    "score": score, "n_glyphs": row["n"],
                    "rows": [{"box": r["box"], "score": r["score"], "n": r["n"]}
                             for r in rows[:max_rows]]})
    out.sort(key=lambda d: -d["score"])
    return out[:limit]

def strip_candidates(img, ks=(3, 4)):
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
    a = np.asarray(img.convert("RGB"))
    height, width = a.shape[:2]
    shape = (height, width)
    out = []
    if type_id:
        hit = type_heuristic(type_id, width, height)
        if hit:
            box, note = hit
            out.append(CropResult(box, "type-heuristic:%s" % note,
                                  detail={"prior": 1.0}))
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
            ("keep", render_keep(a, _dilate(mask, 1))),
            ("keep2", render_keep(a, _dilate(closing(mask, 2), 1))),
            ("keep4", render_keep(a, _dilate(closing(mask, 4), 1))),
            ("crop", None),
        ]
        per_colour.append((cand, box, variants, 0.005 * i))
    for i, cand in enumerate(banks):
        for j, row in enumerate(cand.get("rows", [])[:3]):
            rbox = clamp_box(row["box"], width, height)
            if rbox is None:
                continue
            out.append(CropResult(rbox, "row:%s:%d" % (cand["color"], j),
                                  detail={"prior": 0.9 - 0.02 * i - 0.05 * j}))
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
    box, info = ink_box(a)
    if box is not None:
        out.append(CropResult(box, "ink-box", detail={"prior": 0.5}))
    out.append(CropResult(None, "whole-frame", detail={"prior": 0.25}))
    out.sort(key=lambda c: -c.detail.get("prior", 0.0))
    return out[:limit] if limit else out

def crop(img, type_id=None):
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
