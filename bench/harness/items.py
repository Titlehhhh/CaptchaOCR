"""The item sets of the harness: which types, which samples, band or frame.

An *item* is one picture with everything a scorer needs: the path, the drawn text
(the gold), the answer, and the band (``roi``) if the type has one.
"""

import glob
import json
import os

from paths import OUT, OUT_RU

from .config import LEGACY_TYPES


def read_types():
    """All captcha types: (type_id, folder, rows)."""
    out = []
    for root, tag in ((OUT, "out"), (OUT_RU, "out_ru")):
        for lj in sorted(glob.glob(os.path.join(root, "**", "labels.jsonl"), recursive=True)):
            d = os.path.dirname(lj)
            rel = os.path.relpath(d, root).replace(os.sep, "/")
            rows = []
            with open(lj, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
            out.append((f"{tag}/{rel}", d, rows))
    return out


def _spread(n_rows: int, n_take: int):
    """Deterministic, evenly spread row indices (0 .. n_rows-1)."""
    if n_take <= 1:
        return [0]
    if n_rows <= n_take:
        return list(range(n_rows))
    return [round(k * (n_rows - 1) / (n_take - 1)) for k in range(n_take)]


def build_items(set_name: str, n_per_type: int):
    """Build one item set. Every item carries its band, the drawn text and the answer."""
    types = read_types()
    items = []
    if set_name == "full":
        wanted = None
        take = n_per_type
    elif set_name == "legacy104":
        wanted = set(LEGACY_TYPES)
        take = 8
    elif set_name == "legacy64":
        wanted = set(LEGACY_TYPES)
        take = 8
    else:
        raise ValueError(set_name)

    for tid, folder, rows in types:
        short = tid.split("/", 1)[1]
        if wanted is not None and short not in wanted:
            continue
        if set_name == "legacy64" and not any(r.get("roi") for r in rows[:8]):
            continue
        idxs = _spread(len(rows), take) if set_name == "full" else list(range(min(take, len(rows))))
        for i in idxs:
            r = rows[i]
            items.append({
                "type": tid,
                "path": os.path.join(folder, r["file"]),
                "file": r["file"],
                "answer": str(r.get("answer", "")),
                "text": str(r.get("text") or r.get("answer", "")),
                "roi": r.get("roi"),
                "has_roi": bool(r.get("roi")),
            })
    return items


def load_input(item, mode: str):
    """The picture the model sees. 'band' = the roi crop, 'frame' = the whole PNG."""
    from PIL import Image
    img = Image.open(item["path"]).convert("RGB")
    if mode == "band" and item["roi"]:
        x, y, w, h = item["roi"]
        x = max(0, min(x, img.width - 1))
        y = max(0, min(y, img.height - 1))
        w = max(1, min(w, img.width - x))
        h = max(1, min(h, img.height - y))
        img = img.crop((x, y, x + w, y + h))
    return img
