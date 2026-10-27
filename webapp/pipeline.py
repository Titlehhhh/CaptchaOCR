#!/usr/bin/env python
import os
import sys
import threading
import time
import traceback

import cropper

from backends import (CRNNBackend, DEFAULT_CHECKPOINT, PPOCRBackend,
                      ppocr_prepare, resolve_checkpoint)
from dataset import DATA_ROOTS, Dataset
from filepaths import ROOT, TRAIN

def answer_score(text):
    t = (text or "").strip()
    if not t:
        return 0.0
    if not t.isalnum():
        return 0.10                      # spaces, ':', '+' - a phrase
    if not (3 <= len(t) <= 10):
        return 0.25                      # too short or too long for a code
    if t[0].isupper() and t[1:].islower():
        return 0.30                      # "Captcha" - a word, not a code
    return 1.0

def norm_text(s):
    if s is None:
        return ""
    return "".join(ch for ch in str(s) if ch.isalnum() or ch in "+-*/=")

def _views(img_rgb, cands):
    from PIL import Image

    views = []
    for c in cands:
        if c.image is not None:
            view = Image.fromarray(c.image)
            views.append((view, [0, 0, view.width, view.height]))
        elif c.box:
            views.append((img_rgb, c.box))
        else:
            views.append((img_rgb, None))
    return views

def read_candidates(backend, img_rgb, cands):
    if not cands:
        return None, []
    views = _views(img_rgb, cands)
    if hasattr(backend, "predict_batch"):
        results = backend.predict_batch(views)
    else:
        results = [backend.predict(v, r) for v, r in views]
    votes = {}
    tried = []
    for c, res in zip(cands, results):
        tried.append({"method": c.method, "box": c.box, "text": res["text"],
                      "confidence": res["confidence"]})
        shape = answer_score(res["text"])
        v = votes.setdefault(res["text"], {"votes": 0, "confidence": 0.0,
                                            "shape": shape, "method": c.method,
                                            "box": c.box, "result": res})
        v["votes"] += 1
        score = res["confidence"] * (0.05 + 0.95 * shape)
        if score > v["confidence"] * (0.05 + 0.95 * v["shape"]):
            v["confidence"] = res["confidence"]
            v["shape"] = shape
            v["method"] = c.method
            v["box"] = c.box
            v["result"] = res
    if not votes:
        return None, tried
    best = max(votes.values(),
               key=lambda v: (v["confidence"] * (0.05 + 0.95 * v["shape"]), v["votes"]))
    return best, tried

def vote_frame(backend, img_rgb, cands, strip_conf=0.99):
    best, tried = read_candidates(backend, img_rgb, cands)
    if best is None:
        return None, {"crop_method": None, "crop_box": None, "crop_votes": 0,
                      "crop_candidates": 0, "crop_tried": [],
                      "crop_alternatives": 0, "crop_strips": 0}
    strips_used = 0
    if best["confidence"] < strip_conf:
        strips = cropper.strip_candidates(img_rgb)
        if strips:
            sbest, stried = read_candidates(backend, img_rgb, strips)
            strips_used = len(strips)
            tried = tried + stried
            if sbest is not None and sbest["confidence"] > best["confidence"]:
                best = sbest
    meta = {"crop_method": best["method"], "crop_box": best["box"],
            "crop_votes": best["votes"], "crop_candidates": len(tried),
            "crop_tried": tried, "crop_alternatives": 0,
            "crop_strips": strips_used}
    return best, meta

def learn_type_bands(dataset):
    import statistics

    bands = {}
    for t in dataset.types:
        rows = dataset.by_type.get(t["id"]) or []
        rel = []
        for r in rows:
            roi = r.get("roi")
            w = r.get("width") or 0
            h = r.get("height") or 0
            if not roi or not w or not h:
                continue
            x, y, bw, bh = [float(v) for v in roi]
            rel.append((x / w, y / h, bw / w, bh / h))
        if not rel:
            continue
        bands[t["id"]] = [round(statistics.median(v), 6) for v in zip(*rel)]
    return bands

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
        self.type_bands = self.learn_type_bands()
        cropper.set_type_bands(self.type_bands)
        self.preproc_parity = "not checked"
        self.started = time.time()

    def learn_type_bands(self):
        return learn_type_bands(self.dataset)

    def load(self):
        try:
            if not self.checkpoint:
                raise RuntimeError(f"no checkpoint at {DEFAULT_CHECKPOINT} "
                                   "(override with --checkpoint)")
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

    def _vote(self, img_rgb, cands):
        return read_candidates(self.backend, img_rgb, cands)

    def predict_frame(self, img_rgb, type_id=None):
        cands = cropper.candidates(img_rgb, type_id=type_id,
                                    limit=self.args.crop_limit)
        best, meta = vote_frame(self.backend, img_rgb, cands,
                                 strip_conf=self.args.crop_conf)
        if best is None:
            raise RuntimeError("the cropper proposed nothing")
        return best["result"], meta

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
