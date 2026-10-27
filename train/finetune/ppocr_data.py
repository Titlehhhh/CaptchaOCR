import io
import json
import os
import random

import numpy as np
import torch
from PIL import Image, ImageEnhance

NORM_MODES = ("paddle", "imagenet")

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

IMG_HEIGHT = 48
MAX_WIDTH = 320


def find_types(roots):
    found = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        tag = os.path.basename(os.path.normpath(root))
        for dirpath, _dirs, files in os.walk(root):
            if "labels.jsonl" not in files:
                continue
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            found.append((f"{tag}/{rel}", dirpath))
    return sorted(found)


def read_labels(directory):
    rows = []
    with open(os.path.join(directory, "labels.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_items(types, label_field="text", limit_per_type=None):
    items = []
    for type_id, directory in types:
        rows = read_labels(directory)
        if limit_per_type:
            rows = rows[:limit_per_type]
        for r in rows:
            text = r.get(label_field) or r.get("answer") or ""
            if not text:
                continue
            roi = r.get("roi")
            if not roi:
                continue
            items.append({
                "type": type_id,
                "path": os.path.join(directory, r["file"]),
                "text": text,
                "answer": r.get("answer", text),
                "roi": roi,
            })
    return items


def build_eval_items(types, label_field="text", limit_per_type=None, no_roi_mode="content"):
    items = []
    for type_id, directory in types:
        rows = read_labels(directory)
        if limit_per_type:
            rows = rows[:limit_per_type]
        for r in rows:
            text = r.get(label_field) or r.get("answer") or ""
            if not text:
                continue
            roi = r.get("roi")
            if roi:
                items.append({
                    "type": type_id,
                    "path": os.path.join(directory, r["file"]),
                    "text": text,
                    "answer": r.get("answer", text),
                    "roi": roi,
                    "has_roi": True,
                })
            elif no_roi_mode != "skip":
                items.append({
                    "type": type_id,
                    "path": os.path.join(directory, r["file"]),
                    "text": text,
                    "answer": r.get("answer", text),
                    "roi": None,
                    "has_roi": False,
                })
    return items


def type_stats(types):
    out = []
    for type_id, directory in types:
        rows = read_labels(directory)
        with_band = sum(1 for r in rows if r.get("roi"))
        texts = [(r.get("text") or "") for r in rows]
        alpha = sorted(set("".join(texts)))
        lens = [len(t) for t in texts if t]
        out.append({
            "type": type_id,
            "n": len(rows),
            "n_roi": with_band,
            "alphabet": "".join(alpha),
            "len_min": min(lens) if lens else 0,
            "len_max": max(lens) if lens else 0,
            "text_eq_answer": sum(1 for r in rows if (r.get("text") or "") == (r.get("answer") or "")),
        })
    return out


class Vocab:

    def __init__(self, character_list):
        self.character_list = list(character_list)
        self.blank = 0
        self.table = {}
        for i, ch in enumerate(self.character_list):
            if i == self.blank:
                continue
            self.table.setdefault(ch, i)
        self.num_classes = len(self.character_list)

    @classmethod
    def from_extended(cls, character_list, extra_chars=()):
        return cls(list(character_list) + sorted(set(extra_chars)))

    def __len__(self):
        return self.num_classes

    def encode(self, text):
        return [self.table[c] for c in text if c in self.table]

    def decode(self, indices):
        out = []
        for i in indices:
            i = int(i)
            if i != self.blank and 0 <= i < self.num_classes:
                out.append(self.character_list[i])
        return "".join(out)

    def covers(self, text):
        return all(c in self.table for c in text)


class PPOCRDataset(torch.utils.data.Dataset):

    def __init__(self, items, vocab, glyph_height=IMG_HEIGHT, max_width=MAX_WIDTH,
                 augment=False, seed=0, norm="paddle", glyph_scale="band",
                 bgr=True, min_width=16):
        self.items = items
        self.vocab = vocab
        self.glyph_height = glyph_height
        self.max_width = max_width
        self.min_width = min_width
        self.augment = augment
        self.norm = norm
        self.glyph_scale = glyph_scale
        self.bgr = bgr
        self.rng = random.Random(seed)

    def __len__(self):
        return len(self.items)

    def _augment(self, img):
        r = self.rng
        roll = r.random()
        if roll < 0.10:
            quality = r.randint(15, 40)
        elif roll < 0.40:
            quality = r.randint(40, 95)
        else:
            quality = None
        if quality is not None:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            buf.seek(0)
            img = Image.open(buf).convert("RGB")
        if r.random() < 0.15:
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=r.randint(45, 90))
            buf.seek(0)
            img = Image.open(buf).convert("RGB")
        if r.random() < 0.5:
            img = ImageEnhance.Brightness(img).enhance(r.uniform(0.8, 1.2))
        if r.random() < 0.5:
            img = ImageEnhance.Contrast(img).enhance(r.uniform(0.8, 1.2))
        return img

    @staticmethod
    def _load(path, roi):
        img = Image.open(path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        if roi:
            x, y, w, h = roi
            x = max(0, min(x, img.width - 1))
            y = max(0, min(y, img.height - 1))
            w = max(1, min(w, img.width - x))
            h = max(1, min(h, img.height - y))
            img = img.crop((x, y, x + w, y + h))
        return img

    @staticmethod
    def ink_bbox(img, tol=24):
        a = np.asarray(img, dtype=np.int16)
        flat = a.reshape(-1, a.shape[2])
        colors, counts = np.unique(flat, axis=0, return_counts=True)
        bg = colors[int(counts.argmax())]
        diff = np.abs(a - bg[None, None, :]).max(axis=2)
        mask = diff > tol
        if not mask.any():
            return 0, 0, img.width, img.height
        rows = np.flatnonzero(mask.any(axis=1))
        cols = np.flatnonzero(mask.any(axis=0))
        return int(cols[0]), int(rows[0]), int(cols[-1] - cols[0] + 1), int(rows[-1] - rows[0] + 1)

    @staticmethod
    def _line_height(img):
        a = np.asarray(img.convert("L"), dtype=np.float32)
        if a.ndim != 2 or a.shape[0] < 3:
            return img.height
        busy = a.std(axis=1) > 6.0
        runs = []
        start = None
        for i, b in enumerate(busy):
            if b and start is None:
                start = i
            elif not b and start is not None:
                runs.append(i - start)
                start = None
        if start is not None:
            runs.append(len(busy) - start)
        runs = [r for r in runs if r >= 2]
        if not runs:
            return img.height
        return max(1, int(np.median(runs)))

    def _content_rows(self, img):
        a = np.asarray(img.convert("L"), dtype=np.float32)
        if a.ndim != 2 or a.shape[0] < 3:
            return 0, img.height - 1
        busy = a.std(axis=1) > 6.0
        idx = np.flatnonzero(busy)
        if idx.size == 0:
            return 0, img.height - 1
        return int(idx[0]), int(idx[-1])

    def _prepare(self, img):
        if self.glyph_scale == "glyph":
            top, bottom = self._content_rows(img)
            line = self._line_height(img)
            crop = img.crop((0, top, img.width, bottom + 1))
            scale = self.glyph_height / max(1, line)
        else:
            crop = img
            scale = self.glyph_height / max(1, img.height)
        w = int(round(crop.width * scale))
        w = max(self.min_width, min(self.max_width, w))
        out = crop.resize((w, self.glyph_height), Image.BILINEAR)
        return out, w

    def _normalize(self, img):
        a = np.asarray(img, dtype=np.float32) / 255.0
        if self.bgr:
            a = a[:, :, ::-1]
        if self.norm == "imagenet":
            a = (a - np.array(IMAGENET_MEAN, dtype=np.float32)) / np.array(IMAGENET_STD, dtype=np.float32)
        else:
            a = (a - 0.5) / 0.5
        return np.ascontiguousarray(a.transpose(2, 0, 1))

    def __getitem__(self, i):
        item = self.items[i]
        img = self._load(item["path"], item["roi"])
        if item.get("roi") is None:
            x, y, w, h = self.ink_bbox(img)
            img = img.crop((x, y, x + w, y + h))
        if self.augment:
            img = self._augment(img)
        img, w = self._prepare(img)
        arr = self._normalize(img)

        canvas = np.zeros((3, self.glyph_height, MAX_WIDTH), dtype=np.float32)
        canvas[:, :, :w] = arr

        label = self.vocab.encode(item["text"])
        return {
            "image": torch.from_numpy(canvas),
            "label": torch.tensor(label, dtype=torch.long),
            "width": w,
            "type": item["type"],
            "index": i,
        }


def collate(batch):
    images = torch.stack([b["image"] for b in batch])
    labels = torch.cat([b["label"] for b in batch]) if batch else torch.zeros(0, dtype=torch.long)
    lengths = torch.tensor([len(b["label"]) for b in batch], dtype=torch.long)
    return {
        "images": images,
        "labels": labels,
        "lengths": lengths,
        "widths": torch.tensor([b["width"] for b in batch], dtype=torch.long),
        "types": [b["type"] for b in batch],
        "indices": [b["index"] for b in batch],
    }


def levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(pred, gold):
    if not gold:
        return None
    return levenshtein(pred, gold) / len(gold)
