#!/usr/bin/env python
import json
import os
import urllib.parse

from filepaths import DATA_ROOTS, ROOT

GROUP_C = {
    "out/Archy-X/Krypton/menu",                # answer = a material name, nothing is drawn
    "out/China2B2T/Captcha/wool",              # one constant answer
    "out/FeelingAlive0/AdvancedCaptcha/button",  # the band carries a phrase, not the answer
    "out/Joey61021/captcha/colorgui",          # answer = a colour name
    "out/LagBug/XProtect/color",               # answer = a colour name
    "out/LagBug/XProtect/different",           # one constant answer
    "out/LagBug/XProtect/drop",                # one constant answer
    "out/LagBug/XProtect/jump",                # one constant answer
    "out/LagBug/XProtect/slot",                # the band carries the slot number
    "out/LagBug/XProtect/sneak",               # one constant answer
    "out/Z4OLLIEZ4/reCaptcha/captchasx",       # answer = a colour name
    "out/jSdCool/minecaptcha/image",           # 63-70 characters, unreadable by construction
    "out_ru/GalleryCaptcha/ru-object-swatch",     # answer = a colour name
    "out_ru/CaptchaGUI/clickblock",           # 7 unique pictures, the answer is a slot number
    "out_ru/LimboFilter/framed2x2",           # words in rotated frames
    "out_ru/LimboFilter/framed3x3",           # words in rotated frames
}

class Dataset:
    def __init__(self, roots=None):
        self.types = []          # [{"id", "tree", "dir", "n", "n_roi"}]
        self.by_path = {}        # abs path -> row
        self.by_type = {}        # type id -> [row, ...]
        for root in (roots if roots is not None else DATA_ROOTS):
            if not os.path.isdir(root):
                continue
            tree = os.path.basename(os.path.normpath(root))
            for dirpath, _dirs, files in os.walk(root):
                if "labels.jsonl" not in files:
                    continue
                rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
                type_id = f"{tree}/{rel}"
                rows = []
                with open(os.path.join(dirpath, "labels.jsonl"), encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        row = json.loads(line)
                        row["_type"] = type_id
                        row["_tree"] = tree
                        row["_abs"] = os.path.abspath(os.path.join(dirpath, row["file"]))
                        rows.append(row)
                        self.by_path[row["_abs"]] = row
                self.types.append({
                    "id": type_id,
                    "tree": tree,
                    "dir": rel,
                    "n": len(rows),
                    "n_roi": sum(1 for r in rows if r.get("roi")),
                })
                self.by_type[type_id] = rows
        self.types.sort(key=lambda t: t["id"])

    def demo_types(self, count=10):
        candidates = []
        for t in self.types:
            if t["id"] in GROUP_C or t["n_roi"] == 0:
                continue
            texts = "".join((r.get("text") or "") for r in self.by_type[t["id"]])
            if not texts or any(ord(c) > 127 for c in texts):
                continue
            candidates.append(t["id"])
        return candidates[:count]

    def resolve(self, rel_path):
        if not rel_path:
            return None, None
        candidate = os.path.abspath(rel_path)
        if not os.path.isfile(candidate):
            candidate = os.path.abspath(os.path.join(ROOT, rel_path))
        if not os.path.isfile(candidate):
            return None, None
        for root in DATA_ROOTS:
            try:
                if os.path.commonpath([os.path.abspath(root), candidate]) != os.path.abspath(root):
                    continue
            except ValueError:
                continue
            return self.by_path.get(candidate), candidate
        return None, candidate

    @staticmethod
    def sample_json(r, type_id):
        return {
            "file": r["file"],
            "type": type_id,
            "text": r.get("text"),
            "answer": r.get("answer"),
            "roi": r.get("roi"),
            "width": r.get("width"),
            "height": r.get("height"),
            "url": "/api/image?path=" + urllib.parse.quote(r["_abs"]),
            "path": os.path.relpath(r["_abs"], ROOT).replace("\\", "/"),
        }
