"""Dataset + charset helpers for the PP-OCRv6 fine-tune (`train/finetune_ppocr.py`).

Nothing here writes into `dataset/**` - the dataset is read-only for this task.

Four things this module is careful about:

* **The band rule.** A sample whose `roi` is `null` is NOT a recognition target: the
  whole frame would be shown to the model and the label would not correspond to any
  string in the picture. Types without a band are dropped from training; they may
  still be *evaluated* (for the eight types whose frame IS the text), and there the
  frame is cropped to its ink bounding box first.
* **The label is `text`, not `answer`.** In 9 of the 46 types `text != answer`
  (the Russian number words, the arithmetic types, the reversed string). The
  recogniser reads the *drawn* string; converting it into what the player types is
  the solver's step and is not part of this metric.
* **The preprocessing is the one the 0.40 baseline was measured with**
  (`bench/bench_models.py`, `backend_ppocr_onnx`): crop by `roi`, resize to 48 px
  tall keeping the aspect ratio, cap the width at 320, scale to [0, 1], normalise
  with `(x - 0.5) / 0.5`, zero-pad on the right to 320.
* **The pictures are colour, not grey.** The dataset PNGs are RGB (max channel
  spread 255), so the RGB -> BGR swap of the PaddleOCR pipeline is not a no-op and
  has to be reproduced.
"""

import io
import json
import os
import random

import numpy as np
import torch
from PIL import Image, ImageEnhance

# The two normalisations that were compared. `paddle` is what the PaddleOCR
# training pipeline and `bench/bench_models.py` use; `imagenet` is what the HF
# `PPOCRV6SmallRecImageProcessor` uses. Which one the pretrained weights want is
# measured, not assumed - see `reports/TRAINING_PPOCR_V6.md`.
NORM_MODES = ("paddle", "imagenet")

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

IMG_HEIGHT = 48
MAX_WIDTH = 320


# --------------------------------------------------------------------------- #
# dataset discovery
# --------------------------------------------------------------------------- #
def find_types(roots):
    """Every captcha type under the given roots -> (type_id, directory).

    The type id keeps the tree name (`out/...`, `out_ru/...`) so the two trees can
    never collide.
    """
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
    """Turn (type_id, directory) pairs into dataset items.

    Samples without a band are dropped: the band rule. A type that keeps no
    sample at all is reported by the caller and excluded from training.
    """
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
    """Items for evaluation: banded samples use the band, unbanded ones the frame.

    `no_roi_mode`:
      * ``content`` - crop the frame to its ink bounding box (the eight types whose
        frame IS the text); this is the "per-plugin cropper" the project measured
        to be the decisive component;
      * ``frame``   - the whole frame, downscaled to 48 px tall;
      * ``skip``    - the type is not evaluated at all.
    """
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
    """Per type: n, n with a band, alphabet of `text`, length range."""
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


# --------------------------------------------------------------------------- #
# the model's own dictionary
# --------------------------------------------------------------------------- #
class Vocab:
    """The pretrained model's dictionary (`preprocessor_config.json`).

    Index 0 is the blank; the rest are the characters of the original PaddleOCR
    `character_dict` (18 708 of them), and the space sits at the very end
    (index 18 709) because PaddleOCR's `CTCLabelDecode` appends it after the
    dictionary.

    The mapping was verified against the ONNX repository's `inference.yml`:
    the two lists are identical except for the name of index 0 ('blank' vs
    '<blank>'), i.e. the class indices are the same.

    Measured: the dictionary has **no Cyrillic at all** (not a single entry
    contains a codepoint in U+0400..U+04FF), so the Cyrillic types of the
    dataset cannot be expressed in this model's alphabet.
    """

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
        """Build a Vocab from an EXTENDED character list.

        `character_list` is the original (pretrained PaddleOCR) dictionary and `extra_chars`
        the characters missing from it that the training labels need (the Cyrillic ones, for
        instance). The extras are appended at the END, sorted, so the blank (index 0) and every
        original character keep their index - the pretrained head rows keep their meaning.
        """
        return cls(list(character_list) + sorted(set(extra_chars)))

    def __len__(self):
        return self.num_classes

    def encode(self, text):
        """Text -> class indices. Characters outside the dictionary are dropped
        (the caller must not let that happen - it excludes such types)."""
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


# --------------------------------------------------------------------------- #
# the dataset
# --------------------------------------------------------------------------- #
class PPOCRDataset(torch.utils.data.Dataset):
    """Band crop -> 48 px tall -> normalise -> padded to 320 px wide.

    `glyph_scale` selects what "48 px" means vertically:

    * ``band``  - the band itself becomes 48 px tall. This is what
      `bench/bench_models.py` did for the 0.40 baseline.
    * ``glyph`` - the band is cropped to its text rows first, so the *glyph*
      becomes 48 px tall and the vertical padding of the band disappears. This is
      what PaddleOCR does in training (a tight text-line crop scaled to 48).
    """

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

    # -- deployment artefacts, not distortions ---------------------------------
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
        """The bounding box of the ink (the pixels that differ from the background).

        Used for the types without a band, where the frame *is* the text: the
        cropper is "the ink box". The background is taken as the most common
        colour of the frame, so it works for light-on-dark and dark-on-light.
        """
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
        """Height of one line of glyphs inside a band, in pixels.

        Same measurement as `train/captcha_crnn.py`: the rows of a text line vary
        a lot, the blank rows between the lines do not, so the median length of
        the "busy" runs is the height of one line. Works for dark-on-light and
        light-on-dark because it looks at the variation, not at the brightness.
        """
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
        """The rows of the band that carry the text (the busy rows)."""
        a = np.asarray(img.convert("L"), dtype=np.float32)
        if a.ndim != 2 or a.shape[0] < 3:
            return 0, img.height - 1
        busy = a.std(axis=1) > 6.0
        idx = np.flatnonzero(busy)
        if idx.size == 0:
            return 0, img.height - 1
        return int(idx[0]), int(idx[-1])

    def _prepare(self, img):
        """Band/frame -> (image, width)."""
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

        # zero-pad on the right to the model's native width, exactly like the
        # PaddleOCR `RecResizeImg` / `bench/bench_models.py` did
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
    """The images are already 3 x 48 x 320; only the labels have to be flattened."""
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


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
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
    """Character error rate; `None` for an empty gold string."""
    if not gold:
        return None
    return levenshtein(pred, gold) / len(gold)
