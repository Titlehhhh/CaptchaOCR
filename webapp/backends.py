#!/usr/bin/env python
import glob
import json
import os
import sys

from filepaths import ROOT, TRAIN

def _ck(path):
    return os.path.join(ROOT, path)

def _latest_glob(pattern):
    hits = sorted(glob.glob(os.path.join(ROOT, pattern)))
    return hits[-1] if hits else None

DEFAULT_CHECKPOINT = "train/runs/ppocrv6/universal_v1/best.pt"

def resolve_checkpoint(explicit=None):
    path = explicit or DEFAULT_CHECKPOINT
    if not path or not os.path.isfile(_ck(path)):
        return None, None
    flat = path.replace("\\", "/")
    kind = "ppocr" if ("ppocrv6" in flat or "run_ppocr" in flat) else "crnn"
    return _ck(path), kind

IMG_HEIGHT = 48
MAX_WIDTH = 320
MIN_WIDTH = 16
CRNN_GLYPH_HEIGHT = 32
CRNN_MIN_WIDTH = 64
CRNN_MAX_WIDTH = 400

def clamp_crop(img, roi):
    x, y, w, h = [int(v) for v in roi]
    x = max(0, min(x, img.width - 1))
    y = max(0, min(y, img.height - 1))
    w = max(1, min(w, img.width - x))
    h = max(1, min(h, img.height - y))
    return img.crop((x, y, x + w, y + h))

def ink_bbox(img, tol=24):
    import numpy as np

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
        return 0, 0, img.width, img.height
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    return int(cols[0]), int(rows[0]), int(cols[-1] - cols[0] + 1), int(rows[-1] - rows[0] + 1)

def line_height(img):
    import numpy as np

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

def ppocr_prepare(img_rgb, roi):
    import numpy as np
    from PIL import Image

    img = img_rgb
    if roi:
        img = clamp_crop(img, roi)
    else:
        x, y, w, h = ink_bbox(img)
        img = img.crop((x, y, x + w, y + h))
    scale = IMG_HEIGHT / max(1, img.height)
    w = int(round(img.width * scale))
    w = max(MIN_WIDTH, min(MAX_WIDTH, w))
    out = img.resize((w, IMG_HEIGHT), Image.BILINEAR)
    a = np.asarray(out, dtype=np.float32) / 255.0
    a = a[:, :, ::-1]                      # RGB -> BGR
    a = (a - 0.5) / 0.5
    canvas = np.zeros((3, IMG_HEIGHT, MAX_WIDTH), dtype=np.float32)
    canvas[:, :, :w] = np.ascontiguousarray(a.transpose(2, 0, 1))
    return canvas, w

def crnn_prepare(img_rgb, roi):
    import numpy as np
    from PIL import Image

    img = img_rgb.convert("L")
    if roi:
        img = clamp_crop(img, roi)
    else:
        x, y, w, h = ink_bbox(img)
        img = img.crop((x, y, x + w, y + h))
    line = line_height(img)
    scale = CRNN_GLYPH_HEIGHT / max(1, line)
    w = int(round(img.width * scale))
    w = max(CRNN_MIN_WIDTH, w)
    w = min(CRNN_MAX_WIDTH, w)
    out = img.resize((w, CRNN_GLYPH_HEIGHT), Image.BILINEAR)
    a = np.asarray(out, dtype=np.float32) / 255.0
    a = (a - 0.5) / 0.5
    return a[None, :, :], w

def geometric_mean(values):
    import numpy as np

    if not values:
        return 0.0
    return float(np.exp(np.mean(np.log(np.clip(values, 1e-6, 1.0)))))

def greedy_decode(probs, blank, decode):
    best = probs.argmax(dim=-1)
    best_p = probs.max(dim=-1).values
    idxs, confs = [], []
    prev = -1
    for t in range(best.shape[0]):
        k = int(best[t])
        if k != prev and k != blank:
            idxs.append(k)
            confs.append(float(best_p[t]))
        prev = k
    text = decode(idxs)
    per_char = [{"char": c, "confidence": round(p, 4)}
                for c, p in zip(text, confs)]
    return {"text": text, "confidence": round(geometric_mean(confs), 4),
            "per_char": per_char}

class Backend:
    name = "none"

    def __init__(self):
        self.device = "cpu"
        self.info = {}

    def predict(self, img_rgb, roi):        # pragma: no cover - interface
        raise NotImplementedError

class PPOCRBackend(Backend):
    name = "ppocrv6"

    def __init__(self, ckpt_path, device):
        super().__init__()
        import torch
        import torch.nn as nn
        from huggingface_hub import hf_hub_download
        from transformers import PPOCRV6SmallRecForTextRecognition

        self.torch = torch
        ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        self.args = ck.get("args", {}) or {}
        self.repo = self.args.get("model") or "PaddlePaddle/PP-OCRv6_medium_rec_safetensors"
        self.step = ck.get("step")
        self.epoch = ck.get("epoch")

        model = PPOCRV6SmallRecForTextRecognition.from_pretrained(
            self.repo, local_files_only=True)
        if ck.get("character_list"):
            old = model.head.head
            n = len(ck["character_list"])
            if n != old.out_features:
                model.head.head = nn.Linear(old.in_features, n, bias=True)
        model.load_state_dict(ck["model"])
        model.to(device).eval()
        self.model = model

        if ck.get("character_list"):
            self.character_list = list(ck["character_list"])
        else:
            proc_path = hf_hub_download(self.repo, "preprocessor_config.json",
                                        local_files_only=True)
            with open(proc_path, encoding="utf-8") as f:
                proc = json.load(f)
            self.character_list = list(proc["character_list"])
        self.blank = 0
        self.num_classes = len(self.character_list)

        self.device = device
        self.info = {
            "repo": self.repo,
            "classes": self.num_classes,
            "blank_index": self.blank,
            "step": self.step,
            "epoch": self.epoch,
            "norm": self.args.get("norm", "paddle"),
            "glyph_scale": self.args.get("glyph_scale", "band"),
        }

    def decode_indices(self, indices):
        out = []
        for i in indices:
            i = int(i)
            if i != self.blank and 0 <= i < self.num_classes:
                out.append(self.character_list[i])
        return "".join(out)

    def predict(self, img_rgb, roi):
        import torch

        canvas, _w = ppocr_prepare(img_rgb, roi)
        px = torch.from_numpy(canvas).unsqueeze(0).to(self.device)
        with torch.no_grad():
            with torch.autocast("cuda", dtype=torch.float16,
                                enabled=self.device.startswith("cuda")):
                h = self.model.model(px).last_hidden_state
                enc = self.model.head.encoder(h).last_hidden_state
                logits = self.model.head.head(enc)
            probs = torch.softmax(logits.float(), dim=-1)[0]
        return greedy_decode(probs, self.blank, self.decode_indices)

    def predict_batch(self, items):
        import numpy as np
        import torch

        if not items:
            return []
        canvases = []
        for img_rgb, roi in items:
            canvas, _w = ppocr_prepare(img_rgb, roi)
            canvases.append(canvas)
        px = torch.from_numpy(np.stack(canvases)).to(self.device)
        with torch.no_grad():
            with torch.autocast("cuda", dtype=torch.float16,
                                enabled=self.device.startswith("cuda")):
                h = self.model.model(px).last_hidden_state
                enc = self.model.head.encoder(h).last_hidden_state
                logits = self.model.head.head(enc)
            probs = torch.softmax(logits.float(), dim=-1)
        out = []
        for i in range(probs.shape[0]):
            out.append(greedy_decode(probs[i], self.blank, self.decode_indices))
        return out

class CRNNBackend(Backend):
    name = "crnn"

    def __init__(self, ckpt_path, device):
        super().__init__()
        import torch

        if TRAIN not in sys.path:
            sys.path.insert(0, TRAIN)
        from captcha_crnn import CHARSET, CRNN, build_encoder

        self.torch = torch
        ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        self.cs = build_encoder(CHARSET)
        model = CRNN(self.cs.num_classes)
        model.load_state_dict(ck["model"])
        model.to(device).eval()
        self.model = model
        self.step = ck.get("step")
        self.epoch = ck.get("epoch")
        self.device = device
        self.info = {
            "charset": "latin (62) + blank",
            "classes": self.cs.num_classes,
            "step": self.step,
            "epoch": self.epoch,
            "glyph_height": CRNN_GLYPH_HEIGHT,
        }

    def predict(self, img_rgb, roi):
        import torch

        arr, _w = crnn_prepare(img_rgb, roi)
        px = torch.from_numpy(arr).unsqueeze(0).to(self.device)
        with torch.no_grad():
            logits, _t = self.model(px)
        probs = torch.softmax(logits.float(), dim=-1)[0]
        return greedy_decode(probs, 0, self.cs.decode)
