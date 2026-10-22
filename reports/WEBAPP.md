# WEBAPP — a tiny local web app for the trained recogniser

**Agent:** T-WEBAPP · **Date:** 2026-10-22 · **Status:** done, verified over HTTP.

---

## 1. What was built

A local, offline single-page app that lets the owner drop a captcha PNG into the browser and get
the model's prediction back.

| part | where | what |
|---|---|---|
| the server | `webapp/app.py` | Python **standard library only** (`http.server`), a threaded HTTP server on `127.0.0.1:8765` |
| the page | `webapp/static/index.html` | drag & drop + file picker, a demo-image picker over the dataset, a Predict button, a result panel. CSS and JS are inline — **zero external references** |
| the docs | `webapp/README.md` | the exact start command, the port, the checkpoint |
| this report | `reports/WEBAPP.md` | what was built and measured |

The model is served by one of two backends, picked by the checkpoint preference order of the
brief (`webapp/app.py::resolve_checkpoint`):

1. `train/run_ppocr/big/best.pt` → **PP-OCRv6** (this is what is being served now)
2. `train/run_ppocr/final/best.pt` → PP-OCRv6
3. `train/run/crnn_big/ckpt/step_*.pt` → our CRNN (that run does not exist yet)
4. `train/run/foldA/ckpt/step_0006578.pt` → our CRNN

The kind of the checkpoint follows from the directory it lives in, not from its name.
`--checkpoint PATH` overrides the order.

### Preprocessing — and why it is trustworthy

The preprocessing was **not** taken on faith from `train/ppocr_data.py`: it was re-implemented
inside `webapp/app.py` (that file is read-only for this task, and another agent may be editing
it), and the app then **checks its own copy against the module** on every start:

```
[webapp] status -> "preproc_parity": "match (the local copy equals train/ppocr_data.py)"
```

The check runs the real `train/ppocr_data.py::PPOCRDataset` pipeline and the local copy on the
same banded sample and compares the tensors (`np.allclose`, atol 1e-5). The CRNN path is a copy
of `train/captcha_crnn.py::CaptchaDataset` (grey, band crop, the **glyph** scaled to 32 px, not
the band).

### The API

| route | what |
|---|---|
| `GET /` | the page |
| `GET /api/status` | backend, checkpoint, device, model info, preprocessing parity |
| `GET /api/types` | all 46 types + the demo type ids |
| `GET /api/demo?type=<id>&limit=3` | the demo pictures of a type with their ground truth |
| `GET /api/image?path=<path>` | the PNG (only inside `dataset/out` and `dataset/out_ru`) |
| `POST /predict` | the prediction |

`POST /predict` accepts a form-encoded `path=`, a multipart file upload, or JSON with
`image_base64` / `image_base64` + `ground_truth` — the page uses the JSON form, the two command
line forms are in the README.

The answer always carries: `text`, `confidence`, `per_char[]` (char + confidence),
`ground_truth`, `exact_match`, `file_name`, plus `source_path`, `type`, `ground_truth_answer`,
`exact_match_answer`, `used_band`, `model`, `checkpoint`, `device`, `latency_ms`.

`ground_truth` is the **drawn** string (`text` in `labels.jsonl`) — that is what the recogniser
reads and what `exact_match` compares (letters and digits only, the same `norm()` rule as
`train/finetune_ppocr.py`). `ground_truth_answer` is what a player has to type.

### The demo picker

A type is offered as a demo when it has a **band**, is **not a group-C type** (not an OCR task at
all — the list is copied from `train/finetune_ppocr.py::GROUP_C`) and its label is **pure ASCII**
(the PP-OCRv6 dictionary has no Cyrillic, so a Cyrillic type could only be shown as a failure
that is guaranteed in advance). All 46 types remain in the dropdown. Each demo type shows its
first 3 pictures with the ground truth (`drawn:` and `answer:`) under the thumbnail.

---

## 2. Files touched

| file | status |
|---|---|
| `webapp/app.py` | new (owned by this agent) |
| `webapp/static/index.html` | new (owned by this agent) |
| `webapp/README.md` | new (owned by this agent) |
| `reports/WEBAPP.md` | new (owned by this agent) |

**Nothing else.** `dataset/**`, `train/**`, `tools/**`, `docs/**`, `AGENTS.md` were only read.
The dataset is opened read-only (`open(..., "rb")`); the app refuses any path outside
`dataset/out` and `dataset/out_ru` (verified: a path pointing at `..\..\..\Windows\win.ini`
returns HTTP 404).

---

## 3. What was verified (commands + actual output)

### 3.1 Start (one command, from the repository root)

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv-gpu\Scripts\python.exe webapp\app.py
```

```
[webapp] repository root: C:\Users\Title\Projects\CapthaModel
[webapp] dataset types: 46  demo types: out/Archy-X/Krypton/map, out/FeelingAlive0/AdvancedCaptcha/math,
        out/JSH32/Minecaptcha/map, out/LagBug/XProtect/equation, out/LagBug/XProtect/gui,
        out/LagBug/XProtect/reverse, out/Mrbysco/Captcha/math, out/Yukun99/Captchas/itemslot,
        out/haq/mapcha/map, out/jSdCool/minecaptcha/text
[webapp] checkpoint: train\run_ppocr\big\best.pt (ppocr)
[webapp] serving http://127.0.0.1:8765/  (Ctrl+C to stop)
```

### 3.2 The brief's self-check

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/predict -Method Post -Body @{ path = "dataset\out\haq\mapcha\map\001.png" } | ConvertTo-Json
```

```json
{
    "text":  "zPyf",
    "confidence":  1.0,
    "per_char":  [
                     { "char": "z", "confidence": 1.0 },
                     { "char": "P", "confidence": 1.0 },
                     { "char": "y", "confidence": 1.0 },
                     { "char": "f", "confidence": 1.0 }
                 ],
    "ground_truth":  "zPyf",
    "exact_match":  true,
    "file_name":  "001.png",
    "source_path":  "dataset/out/haq/mapcha/map/001.png",
    "type":  "out/haq/mapcha/map",
    "ground_truth_answer":  "zPyf",
    "exact_match_answer":  true,
    "used_band":  true,
    "model":  "ppocrv6",
    "checkpoint":  "train/run_ppocr/big/best.pt",
    "device":  "cuda",
    "latency_ms":  384.3
}
```

### 3.3 The page

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8765/ -UseBasicParsing
```

```
GET / -> HTTP 200, 13520 bytes, text/html; charset=utf-8
```

The served HTML was checked for the elements the brief asks for (drop zone, file input, type
picker, gallery, Predict button, result fields) — all present — and for external references:
**0** (`src|href="//` / `http(s)://` matches). The inline JavaScript (6541 bytes) was extracted
and run through `node --check` → **JS SYNTAX OK**. No browser was started (per the brief).

### 3.4 The multipart upload

```powershell
curl.exe -F "file=@dataset\out\LagBug\XProtect\map\001.png" http://127.0.0.1:8765/predict
```

```json
{ "text": "ANda", "confidence": 0.4335,
  "per_char": [{"char":"A","confidence":0.7888},{"char":"N","confidence":0.3827},
               {"char":"d","confidence":0.6016},{"char":"a","confidence":0.1944}],
  "ground_truth": null, "exact_match": null, "file_name": "001.png",
  "used_band": false, "model": "ppocrv6", "device": "cuda", "latency_ms": 85.3 }
```

(An upload has no band, so the frame is cropped to its ink; the ground truth is `null` because
the picture did not come from the dataset.)

### 3.5 The base64 JSON upload (the path the page uses)

```json
{ "text": "YQm2", "confidence": 0.9965,
  "per_char": [{"char":"Y","confidence":0.9868},{"char":"Q","confidence":0.9995},
               {"char":"m","confidence":0.9999},{"char":"2","confidence":0.9997}],
  "ground_truth": null, "exact_match": null, "used_band": false, "latency_ms": 54.8 }
```

### 3.6 The demo sweep — 10 demo types × 3 pictures = 30 predictions

```
demo sweep: 30/30 exact match
latency (warm, n=30): min=29.7 ms  median=36.9 ms  mean=37.4 ms  max=54.4 ms
cold (first call after a restart): 384.3 ms
```

(the misses list is empty — every one of the 30 demo pictures was read exactly, including the
arithmetic types `20 + 1`, `6 + 10`, `71 + 51` and the word types `Purpur Block`,
`Brown Mushroom`).

### 3.7 The other routes

| check | result |
|---|---|
| `GET /api/status` | HTTP 200, `ready: true`, `backend: ppocrv6`, `device: cuda`, parity "match" |
| `GET /api/types` | HTTP 200, 46 types, 10 demo types |
| `GET /api/demo?type=out/haq/mapcha/map` | HTTP 200, 3 samples with `text` / `answer` / `roi` |
| `GET /api/image?path=dataset/out/haq/mapcha/map/001.png` | HTTP 200, `image/png`, 1913 bytes |
| `GET /api/image?path=..\..\..\Windows\win.ini` | **HTTP 404** (the path is outside the dataset) |
| a path that does not exist | HTTP 404 |

### 3.8 The CRNN fallback backend (second instance, port 8766)

```powershell
.venv-gpu\Scripts\python.exe webapp\app.py --port 8766 --checkpoint "train\run\foldA\ckpt\step_0006578.pt" --device cpu
```

```
"backend": "crnn", "checkpoint": "train/run/foldA/ckpt/step_0006578.pt", "device": "cpu",
"model": {"charset": "latin (62) + blank", "classes": 63, "step": 6578}
```

Prediction on `dataset/out/haq/mapcha/map/001.png`: `"text": "X7FG"` vs the ground truth `zPyf`,
`exact_match: false`, `latency_ms: 22.4`. That is the expected behaviour of the fold-A CRNN on a
type it was **not** trained on (it memorises its own types — `reports/TRAINING_MINIMAL_LATIN.md`),
not a bug of the web app. The backend, the CPU device path and the CRNN preprocessing were all
exercised.

---

## 4. Measured latency

Measured on the PP-OCRv6 backend on the GPU (the training run was using the GPU at the same
time), 48×320 input, one image per request:

| | ms |
|---|---|
| first call after a restart (CUDA kernels not yet initialised) | **384.3** |
| warm, minimum | **29.7** |
| warm, median (n = 30) | **36.9** |
| warm, mean (n = 30) | **37.4** |
| warm, maximum | **54.4** |

The CRNN backend on the CPU: **22.4 ms**.

The number in the JSON (`latency_ms`) is the inference only — it excludes the HTTP round trip and
the image decoding.

---

## 5. What was NOT verified

* **No browser was run.** The page was verified over HTTP only (status 200, the HTML content, the
  inline JS syntax, the absence of external references). The *visual* layout and the drag & drop
  interaction were not exercised in a real browser — per the brief, starting Edge on this machine
  would take the owner's live browser profile.
* **No measured accuracy.** The 30/30 figure above is a 30-picture sample of the demo types, not
  a benchmark. It says nothing about the model in general — the number belongs to
  `train/finetune_ppocr.py`, and the log of the `big` run is the authority there.
* **The CUDA-OOM fallback was not triggered.** The code path exists (it catches the OOM, empties
  the cache and repeats the prediction on the CPU), but no OOM was provoked during the session.
* **`--device cpu` was verified for the CRNN backend only** (it was the CRNN that ran on the CPU).
  The PP-OCRv6 backend on the CPU was not measured.
* **The `train/run/crnn_big/` branch was never exercised** — that run does not exist on disk, so
  the candidate list entry could not be taken.
* **The `big` run is still training.** The checkpoint is read once at startup, so the server
  serves the snapshot it loaded; a newer `best.pt` needs a restart.
* **The multipart parser** was tested with `curl.exe -F` only (one field, one file); a
  multi-field multipart body with non-ASCII field names was not tested.

---

## 6. What is broken

Nothing that was measured. Known limits, stated plainly:

* the server is **single-process and single-model**: one checkpoint at a time, and a restart is
  needed to change it;
* the demo picker offers only the **first 3 pictures** of a type (`limit=3`), by design;
* an uploaded picture is cropped to its **ink bounding box** (there is no band outside the
  dataset) — for a picture whose answer is not the only ink in the frame, the crop can be wrong.
  That is the cropper problem of this project, not of the app;
* the PP-OCRv6 dictionary has **no Cyrillic**, so the `out_ru` types that are written in
  Cyrillic cannot be read by the served model at all (measured: `5МП` → `5MT`). The demo picker
  therefore does not offer them.

---

## 7. Discrepancies

1. **The checkpoint that ended up being served:** `train/run_ppocr/big/best.pt` — the first item
   of the preference order. It appeared at 14:59 during the work; the brief said it might. It is
   the **epoch-3** snapshot (step 816); the epochs 4 and 5 that followed scored *worse* on the
   held-out types, so `best.pt` was not rewritten (the run's own log: epoch 3 → held-out median
   exact **0.47**, cer 0.2328, micro 0.5403).
2. **`train/run/final/best.pt` (preference 2) was therefore never served.** It was loaded and
   verified by the fallback chain only in the sense that the resolver prefers `big`; the CRNN
   branch was exercised explicitly with `--checkpoint`.
3. **The app serves a snapshot, not a live file.** The training run rewrites
   `train/run_ppocr/big/best.pt` while the server is up; the server keeps the weights it loaded
   at startup. Restart it to pick up a newer checkpoint. This is stated in the README.
4. **A copy of the preprocessing lives in `webapp/app.py`.** The brief allowed it; the app
   verifies the copy against `train/ppocr_data.py` on every start ("parity: match"), but if the
   module changes, the copy has to be updated by hand.
5. **An observation about the training run, not a change to it:** the `big` run's *zero step*
   (the pretrained model, before any fine-tuning) reports a held-out median exact of **0.588**,
   while the best fine-tuned epoch reports **0.47** on the same held-out types. That belongs to
   the training agent; it is recorded here only because it was visible in the log next to the
   checkpoint this app serves.
