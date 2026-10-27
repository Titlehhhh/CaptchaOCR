#!/usr/bin/env python
"""CaptchaOCR — a tiny local web app that lets the owner poke the trained recogniser.

    .venv-gpu\\Scripts\\python.exe webapp\\app.py

Then open <http://127.0.0.1:8765/>.

The app has three parts:

* a **static page** (`webapp/static/index.html`) - a drop zone, a picker of demo
  images from the dataset, a Predict button and a result panel;
* a **JSON API** - `POST /predict` returns the prediction, the per-character
  confidence, the ground truth of a dataset image and whether they match;
* a **backend** - either the fine-tuned PP-OCRv6
  (`train/runs/ppocrv6/universal_v1/best.pt`) or our own CRNN
  (`train/run/**/ckpt/step_*.pt`).  Which one is served is decided by the
  checkpoint of the backend, and it is printed on startup.

This file is the **entry point only**: the routes of the HTTP API and
`main()`.  The rest lives next door:

| module | what |
|---|---|
| `webapp/filepaths.py` | where things are (the repository root, the dataset trees) |
| `webapp/dataset.py` | the read-only index of the dataset (`Dataset`) |
| `webapp/backends.py` | the checkpoint rule, the preprocessing, `PPOCRBackend`, `CRNNBackend` |
| `webapp/pipeline.py` | the rule of the vote and the state of the app (`App`) |
| `webapp/cropper.py` | the cropper - the "eye" (no model) |
| `webapp/eval_cropper.py` | the measurement script (calls the same rule) |

The names the measurement script imports (`Dataset`, `resolve_checkpoint`,
`PPOCRBackend`, `CRNNBackend`, `DEFAULT_CHECKPOINT`) are re-exported here, so
`app.<name>` keeps working.

Everything runs offline: the Python standard library does the HTTP, the model
weights come from the local disk, and the page has no CDN.

The preprocessing is a **self-contained copy** of the one in `train/ppocr_data.py`
(the PP-OCRv6 path) and `train/captcha_crnn.py` (the CRNN path); both of those
files are read-only for this app.  On startup the app compares its own copy with
`train/ppocr_data.py` (when that module imports) and prints the verdict, so the
duplication is checked rather than trusted.
"""

import argparse
import io
import json
import mimetypes
import os
import random
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))

if HERE not in sys.path:
    sys.path.insert(0, HERE)

import cropper                                          # noqa: F401  (re-exported)
from backends import (CRNNBackend, DEFAULT_CHECKPOINT,  # noqa: F401
                      PPOCRBackend, resolve_checkpoint)
from dataset import DATA_ROOTS, GROUP_C, Dataset        # noqa: F401
from filepaths import ROOT, STATIC
from pipeline import (App, answer_score, norm_text,     # noqa: F401
                       read_candidates, vote_frame)

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
            if query.get("random"):
                # a random sample of the type - the demo is more fun when it
                # does not show the same three pictures every time
                rows = random.sample(rows, min(limit, len(rows)))
            else:
                rows = rows[:limit]
            out = [Dataset.sample_json(r, type_id) for r in rows]
            return self._json({"type": type_id, "samples": out})
        if route == "/api/random":
            # a random picture of the dataset: a random type and a random
            # sample of that type.  `pool=demo` keeps the demo types.
            pool = (query.get("pool") or ["all"])[0]
            limit = int((query.get("limit") or ["1"])[0])
            ids = app.demo_types if pool == "demo" else [t["id"] for t in app.dataset.types]
            ids = ids or [t["id"] for t in app.dataset.types]
            if not ids:
                return self._error(404, "no types")
            picked = []
            for type_id in random.sample(ids, min(limit, len(ids))):
                rows = app.dataset.by_type.get(type_id) or []
                if not rows:
                    continue
                r = random.choice(rows)
                picked.append(Dataset.sample_json(r, type_id))
            return self._json({"samples": picked})
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
        crop_meta = {}
        try:
            if roi:
                # the dataset knows the band - that is the measured-good path
                result = app.predict(img, roi)
                crop_meta = {"crop_method": "roi (labels.jsonl)", "crop_box": list(roi)}
            else:
                # no band: the cropper proposes the bands and the model votes
                result, crop_meta = app.predict_frame(img, row.get("_type") if row else None)
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
            "crop_method": crop_meta.get("crop_method"),
            "crop_box": crop_meta.get("crop_box"),
            "crop_votes": crop_meta.get("crop_votes"),
            "crop_candidates": crop_meta.get("crop_candidates"),
            "crop_strips": crop_meta.get("crop_strips"),
            "crop_tried": crop_meta.get("crop_tried"),
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
    ap.add_argument("--crop-limit", type=int, default=32,
                    help="how many bands the cropper may propose for a picture "
                         "that arrives without a band (more = slower, better)")
    ap.add_argument("--crop-conf", type=float, default=0.99,
                    help="the horizontal strips of the frame are tried as well "
                         "only when the best base answer is less confident than this")
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
