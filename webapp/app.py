#!/usr/bin/env python
"""CaptchaOCR — a tiny local web app that lets the owner poke the trained recogniser.

    .venv-gpu\\Scripts\\python.exe webapp\\app.py

Then open <http://127.0.0.1:8765/>.

The app has three parts:

* a **static page** (`webapp/static/index.html`) - a drop zone, a picker of demo
  images from the dataset, a Predict button and a result panel;
* a **JSON API** - `POST /predict` returns the prediction, the per-character
  confidence, the ground truth of a dataset image and whether they match;
* a **backend** - either the fine-tuned PP-OCRv6 (`train/run_ppocr/*/best.pt`)
  or our own CRNN (`train/run/**/ckpt/step_*.pt`).  Which one is served is decided
  by the checkpoint preference order below, and it is printed on startup.

Everything runs offline: the Python standard library does the HTTP, the model
weights come from the local disk, and the page has no CDN.

The preprocessing is a **self-contained copy** of the one in `train/ppocr_data.py`
(the PP-OCRv6 path) and `train/captcha_crnn.py` (the CRNN path); both of those
files are read-only for this app.  On startup the app compares its own copy with
`train/ppocr_data.py` (when that module imports) and prints the verdict, so the
duplication is checked rather than trusted.
"""

import argparse
import glob
import io
import json
import mimetypes
import os
import sys
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TRAIN = os.path.join(ROOT, "train")
STATIC = os.path.join(HERE, "static")

# The machine's Hugging Face cache lives inside the repository and holds the
# PP-OCRv6 weights; it must be pointed at BEFORE huggingface_hub is imported
# (the same trick `train/finetune_ppocr.py` uses).  The app never needs the
# network: the hub is asked for local files only.
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".hf-cache"))
os.environ.setdefault("HF_HUB_CACHE", os.path.join(ROOT, ".hf-cache", "hub"))

# The dataset is read-only for this app; only these two trees may be read.
DATA_ROOTS = [os.path.join(ROOT, "dataset", "out"), os.path.join(ROOT, "dataset", "out_ru")]

# --------------------------------------------------------------------------- #
# the checkpoint preference order (the brief of this task)
# --------------------------------------------------------------------------- #
def _ck(path):
    return os.path.join(ROOT, path)


def _latest_glob(pattern):
    hits = sorted(glob.glob(os.path.join(ROOT, pattern)))
    return hits[-1] if hits else None


def resolve_checkpoint(explicit=None):
    """(path, kind) of the checkpoint to serve, or (None, None).

    `kind` is "ppocr" or "crnn"; it follows from the directory the checkpoint
    lives in, not from the file name.
    """
    candidates = []
    if explicit:
        candidates.append((explicit, None))
    candidates.append((_ck("train/run_ppocr/big/best.pt"), "ppocr"))
    candidates.append((_ck("train/run_ppocr/final/best.pt"), "ppocr"))
    crnn_big = _latest_glob("train/run/crnn_big/ckpt/step_*.pt")
    if crnn_big:
        candidates.append((crnn_big, "crnn"))
    candidates.append((_ck("train/run/foldA/ckpt/step_0006578.pt"), "crnn"))

    for path, kind in candidates:
        if path and os.path.isfile(path):
            if kind is None:
                kind = "ppocr" if "run_ppocr" in path.replace("\\", "/") else "crnn"
            return path, kind
    return None, None


# --------------------------------------------------------------------------- #
# the dataset index (read-only)
# --------------------------------------------------------------------------- #
# The types that are not OCR tasks at all (group C).  Copied from
# `train/finetune_ppocr.py::GROUP_C` (read-only for this app) so the demo
# picker does not offer a type on which no recogniser can be judged.
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
    """Every labelled sample of the dataset, indexed by absolute path."""

    def __init__(self, roots):
        self.types = []          # [{"id", "tree", "dir", "n", "n_roi"}]
        self.by_path = {}        # abs path -> row
        self.by_type = {}        # type id -> [row, ...]
        for root in roots:
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
        """The demo types of the picker.

        A type is a candidate when it has a band (the recogniser was trained on
        the band, not on the frame), when it is not a group-C type (not an OCR
        task at all) and when its label is pure ASCII - the PP-OCRv6 dictionary
        has no Cyrillic at all (`train/ppocr_data.py::Vocab`), so a Cyrillic
        type can only be shown as a failure that is guaranteed in advance.
        """
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
        """A dataset path -> (row, abs path).  Returns (None, None) if the path
        is not inside the dataset (or does not exist)."""
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


# --------------------------------------------------------------------------- #
# preprocessing - a self-contained copy of train/ppocr_data.py and
# train/captcha_crnn.py (both read-only for this app)
# --------------------------------------------------------------------------- #
IMG_HEIGHT = 48
MAX_WIDTH = 320
MIN_WIDTH = 16
CRNN_GLYPH_HEIGHT = 32
CRNN_MIN_WIDTH = 64
CRNN_MAX_WIDTH = 400


def clamp_crop(img, roi):
    """The band crop of `train/ppocr_data.py::PPOCRDataset._load`."""
    x, y, w, h = [int(v) for v in roi]
    x = max(0, min(x, img.width - 1))
    y = max(0, min(y, img.height - 1))
    w = max(1, min(w, img.width - x))
    h = max(1, min(h, img.height - y))
    return img.crop((x, y, x + w, y + h))


def ink_bbox(img, tol=24):
    """The ink bounding box of `train/ppocr_data.py::PPOCRDataset.ink_bbox`.

    Used when a picture arrives without a band: the frame is cropped to its
    ink, which is the "per-plugin cropper" the project measured to be the
    decisive component.
    """
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
    """The height of one text line inside a band - `train/captcha_crnn.py`."""
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
    """-> (3, 48, 320) float32.

    Exactly `train/ppocr_data.py::PPOCRDataset` with `glyph_scale="band"`,
    `norm="paddle"`, `bgr=True`: crop the band, scale it to 48 px tall (the
    width follows the aspect ratio and is capped at 320), swap RGB -> BGR,
    normalise with (x - 0.5) / 0.5 and zero-pad on the right.
    """
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
    """-> (1, 32, W) float32.

    Exactly `train/captcha_crnn.py::CaptchaDataset`: grey, crop the band, scale
    so that the GLYPH (not the band) is 32 px tall, normalise with
    (x - 0.5) / 0.5.
    """
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


def norm_text(s):
    """The comparison form of a string - letters, digits and the arithmetic
    operators, everything else dropped (the same rule as
    `train/finetune_ppocr.py::norm`)."""
    if s is None:
        return ""
    return "".join(ch for ch in str(s) if ch.isalnum() or ch in "+-*/=")


def geometric_mean(values):
    import numpy as np

    if not values:
        return 0.0
    return float(np.exp(np.mean(np.log(np.clip(values, 1e-6, 1.0)))))


# --------------------------------------------------------------------------- #
# the backends
# --------------------------------------------------------------------------- #
class Backend:
    name = "none"

    def __init__(self):
        self.device = "cpu"
        self.info = {}

    def predict(self, img_rgb, roi):        # pragma: no cover - interface
        raise NotImplementedError


class PPOCRBackend(Backend):
    """The fine-tuned PP-OCRv6 (`train/ppocr_data.py` + `train/finetune_ppocr.py`)."""

    name = "ppocrv6"

    def __init__(self, ckpt_path, device):
        super().__init__()
        import torch
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
        model.load_state_dict(ck["model"])
        model.to(device).eval()
        self.model = model

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
        best = probs.argmax(dim=-1)
        best_p = probs.max(dim=-1).values
        idxs, confs = [], []
        prev = -1
        for t in range(best.shape[0]):
            k = int(best[t])
            if k != prev and k != self.blank:
                idxs.append(k)
                confs.append(float(best_p[t]))
            prev = k
        text = self.decode_indices(idxs)
        per_char = [{"char": c, "confidence": round(p, 4)}
                    for c, p in zip(text, confs)]
        return {"text": text, "confidence": round(geometric_mean(confs), 4),
                "per_char": per_char}


class CRNNBackend(Backend):
    """Our own CRNN + CTC (`train/captcha_crnn.py`)."""

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
        best = probs.argmax(dim=-1)
        best_p = probs.max(dim=-1).values
        idxs, confs = [], []
        prev = -1
        for t in range(best.shape[0]):
            k = int(best[t])
            if k != prev and k != 0:
                idxs.append(k)
                confs.append(float(best_p[t]))
            prev = k
        text = self.cs.decode(idxs)
        per_char = [{"char": c, "confidence": round(p, 4)}
                    for c, p in zip(text, confs)]
        return {"text": text, "confidence": round(geometric_mean(confs), 4),
                "per_char": per_char}


# --------------------------------------------------------------------------- #
# the application state
# --------------------------------------------------------------------------- #
class App:
    def __init__(self, args):
        self.args = args
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.error = None
        self.backend = None
        self.checkpoint, self.kind = resolve_checkpoint(args.checkpoint)
        self.dataset = Dataset(DATA_ROOTS)
        self.demo_types = self.dataset.demo_types(args.demo_types)
        self.preproc_parity = "not checked"
        self.started = time.time()

    # -- model -------------------------------------------------------------- #
    def load(self):
        try:
            if not self.checkpoint:
                raise RuntimeError("no checkpoint found (looked at train/run_ppocr/big/best.pt, "
                                   "train/run_ppocr/final/best.pt, train/run/crnn_big/ckpt/step_*.pt, "
                                   "train/run/foldA/ckpt/step_0006578.pt)")
            device = self.args.device
            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except Exception:
                    device = "cpu"
            if self.kind == "ppocr":
                backend = PPOCRBackend(self.checkpoint, device)
            else:
                backend = CRNNBackend(self.checkpoint, device)
            self.backend = backend
            self.preproc_parity = self.check_parity()
            self.error = None
        except Exception as exc:                     # pragma: no cover
            self.error = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        finally:
            self.ready.set()

    def check_parity(self):
        """Compare the local copy of the preprocessing with `train/ppocr_data.py`.

        The dataset module is read-only for this app; if it can be imported, its
        own pipeline is run on the same image and the two tensors are compared.
        """
        try:
            if TRAIN not in sys.path:
                sys.path.insert(0, TRAIN)
            import ppocr_data
            from PIL import Image
        except Exception as exc:
            return f"train/ppocr_data.py not importable ({type(exc).__name__})"
        row = None
        for r in self.dataset.by_path.values():
            if r.get("roi"):
                row = r
                break
        if row is None:
            return "no banded sample to compare with"
        try:
            import numpy as np
            img = Image.open(row["_abs"]).convert("RGB")
            mine, _ = ppocr_prepare(img, row["roi"])
            ds = ppocr_data.PPOCRDataset([], vocab=None, norm="paddle", glyph_scale="band",
                                         bgr=True)
            cropped = ppocr_data.PPOCRDataset._load(row["_abs"], row["roi"])
            resized, w = ds._prepare(cropped)
            arr = ds._normalize(resized)
            theirs = np.zeros((3, ppocr_data.IMG_HEIGHT, ppocr_data.MAX_WIDTH),
                              dtype=np.float32)
            theirs[:, :, :arr.shape[2]] = arr
            if np.allclose(mine, theirs, atol=1e-5):
                return "match (the local copy equals train/ppocr_data.py)"
            return "MISMATCH with train/ppocr_data.py"
        except Exception as exc:
            return f"parity check failed: {type(exc).__name__}: {exc}"

    # -- inference ---------------------------------------------------------- #
    def predict(self, img_rgb, roi):
        if not self.ready.wait(timeout=300):
            raise RuntimeError("the model is still loading")
        if self.backend is None:
            raise RuntimeError(self.error or "no model loaded")
        with self.lock:
            try:
                return self.backend.predict(img_rgb, roi)
            except RuntimeError as exc:
                if "out of memory" not in str(exc).lower():
                    raise
                # CUDA OOM (the GPU is shared with a training run): fall back to CPU.
                print("[webapp] CUDA OOM - retrying on the CPU", file=sys.stderr)
                import torch
                torch.cuda.empty_cache()
                old = self.backend.device
                self.backend.device = "cpu"
                self.backend.model.to("cpu")
                try:
                    return self.backend.predict(img_rgb, roi)
                finally:
                    self.backend.model.to(old)
                    self.backend.device = old

    def status(self):
        return {
            "ready": self.backend is not None,
            "loading": not self.ready.is_set(),
            "error": self.error,
            "backend": self.backend.name if self.backend else None,
            "checkpoint": os.path.relpath(self.checkpoint, ROOT).replace("\\", "/")
                          if self.checkpoint else None,
            "device": self.backend.device if self.backend else None,
            "model": self.backend.info if self.backend else None,
            "preproc_parity": self.preproc_parity,
            "demo_types": self.demo_types,
            "types": len(self.dataset.types),
            "uptime_s": round(time.time() - self.started, 1),
            "python": sys.executable,
        }


# --------------------------------------------------------------------------- #
# the HTTP handler
# --------------------------------------------------------------------------- #
def parse_multipart(body, boundary):
    """A tiny multipart/form-data reader -> [(headers, data), ...]."""
    parts = []
    sep = b"--" + boundary
    for chunk in body.split(sep):
        if not chunk or chunk.strip() in (b"", b"--"):
            continue
        chunk = chunk.lstrip(b"\r\n")
        head, sep2, data = chunk.partition(b"\r\n\r\n")
        if not sep2:
            continue
        if data.endswith(b"\r\n"):
            data = data[:-2]
        headers = {}
        for line in head.decode("utf-8", "replace").split("\r\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        parts.append((headers, data))
    return parts


class Handler(BaseHTTPRequestHandler):
    server_version = "CaptchaOCRWebapp/1.0"
    protocol_version = "HTTP/1.1"

    # -- helpers ------------------------------------------------------------ #
    def _send(self, code, body=b"", ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8")
        self._send(code, body)

    def _error(self, code, message):
        self._json({"error": message}, code)

    def log_message(self, fmt, *args):
        sys.stderr.write("[webapp] %s - %s\n" % (self.address_string(), fmt % args))

    # -- routing ------------------------------------------------------------ #
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        app = self.server.app

        if route in ("/", "/index.html"):
            return self._serve_static("index.html")
        if route.startswith("/static/"):
            return self._serve_static(route[len("/static/"):])
        if route == "/api/status":
            return self._json(app.status())
        if route == "/api/types":
            demo = set(app.demo_types)
            return self._json({"types": [
                {"id": t["id"], "tree": t["tree"], "n": t["n"], "n_roi": t["n_roi"],
                 "demo": t["id"] in demo}
                for t in app.dataset.types],
                "demo_types": app.demo_types})
        if route == "/api/demo":
            type_id = (query.get("type") or [app.demo_types[0]])[0]
            rows = app.dataset.by_type.get(type_id)
            if rows is None:
                return self._error(404, f"unknown type {type_id!r}")
            limit = int((query.get("limit") or ["3"])[0])
            out = []
            for r in rows[:limit]:
                out.append({
                    "file": r["file"],
                    "type": type_id,
                    "text": r.get("text"),
                    "answer": r.get("answer"),
                    "roi": r.get("roi"),
                    "width": r.get("width"),
                    "height": r.get("height"),
                    "url": "/api/image?path=" + urllib.parse.quote(r["_abs"]),
                    "path": os.path.relpath(r["_abs"], ROOT).replace("\\", "/"),
                })
            return self._json({"type": type_id, "samples": out})
        if route == "/api/image":
            rel = (query.get("path") or [""])[0]
            row, abs_path = app.dataset.resolve(rel)
            if abs_path is None or not os.path.isfile(abs_path):
                return self._error(404, "image not found")
            with open(abs_path, "rb") as f:
                data = f.read()
            ctype = mimetypes.guess_type(abs_path)[0] or "image/png"
            return self._send(200, data, ctype)
        return self._error(404, f"no such route: {route}")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        app = self.server.app
        if parsed.path != "/predict":
            return self._error(404, f"no such route: {parsed.path}")

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length else b""

        ctype = (self.headers.get("Content-Type") or "").lower()
        file_bytes = None
        file_name = None
        path = None
        extra = {}

        if ctype.startswith("application/json"):
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception as exc:
                return self._error(400, f"bad JSON: {exc}")
            path = payload.get("path")
            file_name = payload.get("file_name") or payload.get("name")
            if payload.get("image_base64"):
                import base64
                try:
                    file_bytes = base64.b64decode(payload["image_base64"])
                except Exception as exc:
                    return self._error(400, f"bad base64: {exc}")
            for k in ("ground_truth", "note"):
                if k in payload:
                    extra[k] = payload[k]
        elif ctype.startswith("multipart/form-data"):
            boundary = None
            for piece in ctype.split(";"):
                piece = piece.strip()
                if piece.startswith("boundary="):
                    boundary = piece[len("boundary="):].strip('"')
            if not boundary:
                return self._error(400, "multipart without a boundary")
            fields = {}
            for headers, data in parse_multipart(body, boundary.encode("utf-8")):
                disp = headers.get("content-disposition", "")
                name = None
                for piece in disp.split(";"):
                    piece = piece.strip()
                    if piece.startswith("name="):
                        name = piece[len("name="):].strip('"')
                if not name:
                    continue
                if "filename=" in disp:
                    file_bytes = data
                    file_name = name
                    for piece in disp.split(";"):
                        piece = piece.strip()
                        if piece.startswith("filename="):
                            file_name = piece[len("filename="):].strip('"')
                else:
                    fields[name] = data.decode("utf-8", "replace")
            path = fields.get("path")
            if file_bytes is not None and not path:
                # a bare upload: look it up in the dataset by its name
                candidate = os.path.abspath(os.path.join(ROOT, fields.get("path", "")))
                path = None
        else:
            # application/x-www-form-urlencoded (what Invoke-RestMethod sends)
            fields = urllib.parse.parse_qs(body.decode("utf-8", "replace"))
            path = (fields.get("path") or [None])[0]
            if fields.get("ground_truth"):
                extra["ground_truth"] = fields["ground_truth"][0]

        if file_bytes is None and not path:
            return self._error(400, "neither a path nor an uploaded file was given")

        # -- the image ------------------------------------------------------- #
        from PIL import Image

        row = None
        roi = None
        if path:
            row, abs_path = app.dataset.resolve(path)
            if abs_path is None or not os.path.isfile(abs_path):
                return self._error(404, f"no such image: {path}")
            with open(abs_path, "rb") as f:
                file_bytes = f.read()
            file_name = file_name or os.path.basename(abs_path)
            if row is not None:
                roi = row.get("roi")
        else:
            file_name = file_name or "upload.png"

        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.load()
            img = img.convert("RGB")
        except Exception as exc:
            return self._error(400, f"cannot read the image: {exc}")

        # -- inference ------------------------------------------------------- #
        t0 = time.perf_counter()
        try:
            result = app.predict(img, roi)
        except Exception as exc:
            return self._error(500, f"prediction failed: {type(exc).__name__}: {exc}")
        latency_ms = (time.perf_counter() - t0) * 1000.0

        pred = result["text"]
        ground_truth = None
        ground_truth_answer = None
        exact_match = None
        if row is not None:
            ground_truth = row.get("text")
            ground_truth_answer = row.get("answer")
            exact_match = norm_text(pred) == norm_text(ground_truth)
        elif extra.get("ground_truth"):
            ground_truth = extra["ground_truth"]
            exact_match = norm_text(pred) == norm_text(ground_truth)

        payload = {
            "text": pred,
            "confidence": result["confidence"],
            "per_char": result["per_char"],
            "ground_truth": ground_truth,
            "exact_match": exact_match,
            "file_name": file_name,
            "source_path": (os.path.relpath(abs_path, ROOT).replace("\\", "/")
                            if path and abs_path else None),
            "type": row.get("_type") if row else None,
            "ground_truth_answer": ground_truth_answer,
            "exact_match_answer": (norm_text(pred) == norm_text(ground_truth_answer)
                                   if ground_truth_answer else None),
            "used_band": bool(roi),
            "model": app.backend.name if app.backend else None,
            "checkpoint": (os.path.relpath(app.checkpoint, ROOT).replace("\\", "/")
                           if app.checkpoint else None),
            "device": app.backend.device if app.backend else None,
            "latency_ms": round(latency_ms, 1),
        }
        return self._json(payload)

    # -- static ------------------------------------------------------------- #
    def _serve_static(self, name):
        name = name.strip("/") or "index.html"
        target = os.path.abspath(os.path.join(STATIC, name))
        if os.path.commonpath([os.path.abspath(STATIC), target]) != os.path.abspath(STATIC):
            return self._error(403, "forbidden")
        if not os.path.isfile(target):
            return self._error(404, f"no such file: {name}")
        with open(target, "rb") as f:
            data = f.read()
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/javascript":
            ctype += "; charset=utf-8"
        return self._send(200, data, ctype)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, handler, app):
        super().__init__(addr, handler)
        self.app = app


def main():
    ap = argparse.ArgumentParser(description="CaptchaOCR web app (local, offline)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--device", default="auto", choices=("auto", "cuda", "cpu"),
                    help="where to run the model (auto = cuda when available)")
    ap.add_argument("--checkpoint", default=None,
                    help="serve this checkpoint instead of the default preference order")
    ap.add_argument("--demo-types", type=int, default=10,
                    help="how many types the demo picker offers")
    ap.add_argument("--no-model", action="store_true",
                    help="start without loading a model (the page still works)")
    args = ap.parse_args()

    app = App(args)
    print(f"[webapp] repository root: {ROOT}", flush=True)
    print(f"[webapp] dataset types: {len(app.dataset.types)}  "
          f"demo types: {', '.join(app.demo_types)}", flush=True)
    if app.checkpoint:
        print(f"[webapp] checkpoint: {os.path.relpath(app.checkpoint, ROOT)} "
              f"({app.kind})", flush=True)
    else:
        print("[webapp] NO CHECKPOINT FOUND", flush=True)

    if not args.no_model:
        threading.Thread(target=app.load, daemon=True).start()

    httpd = Server((args.host, args.port), Handler, app)
    url = f"http://{args.host}:{args.port}/"
    print(f"[webapp] serving {url}  (Ctrl+C to stop)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[webapp] stopped", flush=True)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
