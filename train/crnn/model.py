
import io
import json
import math
import os
import random

import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageEnhance




CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


CYRILLIC = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"

BLANK = 0


class Charset:


    def __init__(self, charset: str):
        self.charset = charset
        self.table = {c: i + 1 for i, c in enumerate(charset)}
        self.reverse = {i + 1: c for i, c in enumerate(charset)}
        self.num_classes = len(charset) + 1

    def __call__(self, text: str):
        return self.encode(text)

    def encode(self, text: str):
        return [self.table[c] for c in text if c in self.table]

    def decode(self, indices):
        return "".join(self.reverse.get(int(i), "") for i in indices)


def build_encoder(charset: str) -> Charset:

    return Charset(charset)





def find_types(roots, wanted=None, exclude=None):

    found = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            if "labels.jsonl" not in files:
                continue
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            if wanted and not any(w in rel for w in wanted):
                continue
            if exclude and any(e in rel for e in exclude):
                continue
            found.append((rel, dirpath, root))
    return sorted(found)


def read_labels(directory):
    rows = []
    with open(os.path.join(directory, "labels.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


class CaptchaDataset(torch.utils.data.Dataset):


    def __init__(self, items, encode, glyph_height=32, min_width=64, max_width=400,
                 augment=False, seed=0, affine=False):
        self.items = items
        self.encode = encode
        self.glyph_height = glyph_height
        self.min_width = min_width
        self.max_width = max_width
        self.augment = augment
        self.affine = affine
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
            img = Image.open(buf).convert("L")
        if r.random() < 0.15:
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=r.randint(45, 90))
            buf.seek(0)
            img = Image.open(buf).convert("L")
        if r.random() < 0.5:
            img = ImageEnhance.Brightness(img).enhance(r.uniform(0.8, 1.2))
        if r.random() < 0.5:
            img = ImageEnhance.Contrast(img).enhance(r.uniform(0.8, 1.2))
        return img

    def _load(self, path, roi):
        img = Image.open(path)
        if img.mode != "L":
            img = img.convert("L")
        if roi:
            x, y, w, h = roi
            x = max(0, min(x, img.width - 1))
            y = max(0, min(y, img.height - 1))
            w = max(1, min(w, img.width - x))
            h = max(1, min(h, img.height - y))
            img = img.crop((x, y, x + w, y + h))
        return img

    @staticmethod
    def _line_height(img):

        a = np.asarray(img, dtype=np.float32)
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

    def _background(self, img):

        a = np.asarray(img, dtype=np.uint8)
        return int(np.bincount(a.ravel(), minlength=256).argmax())

    def _augment_affine(self, img):

        bg = self._background(img)
        angle = self.rng.uniform(-7.0, 7.0)
        scale = self.rng.uniform(0.90, 1.10)
        dx = self.rng.randint(-2, 3)
        dy = self.rng.randint(-1, 2)
        img = img.rotate(angle, resample=Image.BILINEAR, fillcolor=bg)
        w, h = img.size
        matrix = (scale, 0.0, (1.0 - scale) * w / 2.0 + dx,
                  0.0, scale, (1.0 - scale) * h / 2.0 + dy)
        return img.transform((w, h), Image.AFFINE, matrix, resample=Image.BILINEAR,
                             fillcolor=bg)

    def __getitem__(self, i):
        item = self.items[i]
        img = self._load(item["path"], item["roi"])
        if self.augment:
            img = self._augment(img)

        label = self.encode(item["text"])
        n_label = len(label)









        line = self._line_height(img)
        scale = self.glyph_height / max(1, line)
        w = int(round(img.width * scale))
        w = max(self.min_width, w)
        needed = 4 * (2 * n_label + 1)
        w = max(w, needed)
        w = min(self.max_width, w)

        img = img.resize((w, self.glyph_height), Image.BILINEAR)
        if self.augment and self.affine:
            img = self._augment_affine(img)
        a = np.asarray(img, dtype=np.float32) / 255.0
        a = (a - 0.5) / 0.5
        tensor = torch.from_numpy(a).unsqueeze(0)

        return {
            "image": tensor,
            "label": torch.tensor(label, dtype=torch.long),
            "width": w,
            "type": item["type"],
            "index": i,
        }


def collate(batch):

    widths = [b["width"] for b in batch]
    h = batch[0]["image"].shape[1]
    max_w = max(widths)
    images = torch.zeros(len(batch), 1, h, max_w)
    for i, b in enumerate(batch):
        images[i, 0, :, : b["width"]] = b["image"]
    labels = torch.cat([b["label"] for b in batch]) if batch else torch.zeros(0, dtype=torch.long)
    lengths = torch.tensor([len(b["label"]) for b in batch], dtype=torch.long)
    return {
        "images": images,
        "labels": labels,
        "lengths": lengths,
        "widths": torch.tensor(widths, dtype=torch.long),
        "types": [b["type"] for b in batch],
        "indices": [b["index"] for b in batch],
    }


def build_items(types, label_field="text", limit_per_type=None, keep=None):

    items = []
    for type_id, directory in types:
        rows = read_labels(directory)
        if keep is not None and type_id in keep:
            allowed = keep[type_id]
            rows = [r for r in rows if r["file"] in allowed]
        if limit_per_type:
            rows = rows[:limit_per_type]
        for r in rows:
            text = r.get(label_field) or r.get("answer") or ""
            if not text:
                continue
            items.append({
                "type": type_id,
                "path": os.path.join(directory, r["file"]),
                "text": text,
                "answer": r.get("answer", text),
                "roi": r.get("roi"),
                "type_id": type_id,
            })
    return items



class CRNN(nn.Module):


    def __init__(self, num_classes, hidden=256, dropout=0.1, glyph_height=32):
        super().__init__()
        c = num_classes
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 2)),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 2)),
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 1)),
            nn.Conv2d(128, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(inplace=True),
        )




        self.rows = max(1, glyph_height // 8)
        self.rnn = nn.LSTM(self.rows * 256, hidden, num_layers=2, bidirectional=True,
                           dropout=dropout, batch_first=True)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden * 2, c)

    def forward(self, x):

        f = self.cnn(x)
        b, c, h, w = f.shape
        if h != self.rows:
            raise ValueError(
                f"input height {x.shape[2]} gives {h} feature rows, but the model was "
                f"built for {self.rows} - the glyph height and the model must agree")
        f = f.permute(0, 3, 1, 2).reshape(b, w, h * c)
        f, _ = self.rnn(f)
        f = self.dropout(f)
        return self.fc(f), w




def greedy_decode(logits, decode):

    probs = torch.softmax(logits, dim=-1)
    best = probs.argmax(dim=-1)
    best_p = probs.max(dim=-1).values
    out = []
    for b in range(best.shape[0]):
        chars = []
        confs = []
        prev = -1
        for t in range(best.shape[1]):
            k = int(best[b, t])
            if k != prev and k != BLANK:
                chars.append(k)
                confs.append(float(best_p[b, t]))
            prev = k
        text = decode(chars)
        if confs:
            conf = float(np.exp(np.mean(np.log(np.clip(confs, 1e-6, 1.0)))))
        else:
            conf = 0.0
        out.append((text, conf))
    return out


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
