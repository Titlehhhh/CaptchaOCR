# `webapp/` — a tiny local web app for the trained recogniser

A single-page app that lets the project owner drop a captcha PNG into the browser and get the
model's prediction back. It is **local and offline**: the Python standard library does the HTTP,
the weights come from the disk, the page has no CDN and no external references.

```
browser  ──HTTP──>  webapp/app.py  ──torch──>  PP-OCRv6 (train/run_ppocr/*/best.pt)
   ▲                      │
   │                      └── reads (read-only) dataset/out/** , dataset/out_ru/**
   └── /api/demo , /api/image
```

---

## 1. Start it (one command)

From the **repository root** (`C:\Users\Title\Projects\CapthaModel`):

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv-gpu\Scripts\python.exe webapp\app.py
```

Then open **<http://127.0.0.1:8765/>**.

* Use **`.venv-gpu\Scripts\python.exe`** — the system Python is CPU-only and has no torch.
* The model is loaded in a background thread, so the page opens immediately; the first
  prediction waits for the load to finish (a few seconds).
* `Ctrl+C` stops the server.

The startup banner prints what is being served:

```
[webapp] repository root: C:\Users\Title\Projects\CapthaModel
[webapp] dataset types: 46  demo types: out/Archy-X/Krypton/map, out/FeelingAlive0/...
[webapp] checkpoint: train\run_ppocr\big\best.pt (ppocr)
[webapp] serving http://127.0.0.1:8765/  (Ctrl+C to stop)
```

---

## 2. The page

| what | where |
|---|---|
| drag & drop zone + file picker (also accepts a paste) | top left |
| **demo image picker**: a list of the dataset types; the chosen type shows its first 3 pictures with the ground truth under each | bottom left |
| **Predict** button | under the gallery |
| result panel: the predicted string, the per-character confidence, the file name, the ground truth, whether it matched, the latency, whether the band was used | right |

Clicking a demo picture selects it (its ground truth is shown under the thumbnail);
clicking **Predict** sends it to the model.

The demo types are chosen automatically: a type must have a **band** (`roi`), must not be a
**group-C** type (not an OCR task at all) and its label must be **pure ASCII** — the PP-OCRv6
dictionary has no Cyrillic, so a Cyrillic type could only be shown as a failure that is
guaranteed in advance. All 46 types are still listed in the dropdown.

---

## 3. The HTTP API

| route | what it does |
|---|---|
| `GET /` | the page (`webapp/static/index.html`) |
| `GET /api/status` | backend, checkpoint, device, model info, preprocessing parity |
| `GET /api/types` | all 46 types + the demo type ids |
| `GET /api/demo?type=<type id>&limit=3` | the demo pictures of a type with their ground truth |
| `GET /api/image?path=<path>` | the PNG itself (only inside `dataset/out` and `dataset/out_ru`) |
| `POST /predict` | the prediction |

`POST /predict` accepts three bodies:

```powershell
# a) a dataset path (form-encoded — what Invoke-RestMethod sends)
Invoke-RestMethod -Uri http://127.0.0.1:8765/predict -Method Post `
  -Body @{ path = "dataset\out\haq\mapcha\map\001.png" }

# b) a multipart upload
curl.exe -F "file=@dataset\out\haq\mapcha\map\001.png" http://127.0.0.1:8765/predict

# c) JSON with a base64 picture (what the page itself sends)
curl.exe -X POST http://127.0.0.1:8765/predict -H "Content-Type: application/json" `
  -d '{"image_base64":"<base64>","file_name":"x.png"}'
```

The answer:

```json
{
 "text": "zPyf",
 "confidence": 1.0,
 "per_char": [{"char": "z", "confidence": 1.0}, {"char": "P", "confidence": 1.0}],
 "ground_truth": "zPyf",
 "exact_match": true,
 "file_name": "001.png",
 "source_path": "dataset/out/haq/mapcha/map/001.png",
 "type": "out/haq/mapcha/map",
 "ground_truth_answer": "zPyf",
 "exact_match_answer": true,
 "used_band": true,
 "model": "ppocrv6",
 "checkpoint": "train/run_ppocr/big/best.pt",
 "device": "cuda",
 "latency_ms": 28.1
}
```

* `ground_truth` is the **drawn** string (`text` in `labels.jsonl`) — that is what the
  recogniser reads and what the comparison uses (letters and digits only, the same rule as
  `train/finetune_ppocr.py::norm`). `ground_truth_answer` is what a player has to type.
* A picture that is not in the dataset (an upload) has `ground_truth: null` and
  `exact_match: null`.

---

## 4. Options

| flag | default | what it does |
|---|---|---|
| `--port N` | `8765` | the port |
| `--host H` | `127.0.0.1` | the interface (keep it local) |
| `--device auto\|cuda\|cpu` | `auto` | `auto` = cuda when available |
| `--checkpoint PATH` | the preference order below | serve this checkpoint instead |
| `--demo-types N` | `10` | how many types the demo picker offers |
| `--no-model` | off | start without loading a model (the page still works) |

### Change the port

```powershell
.venv-gpu\Scripts\python.exe webapp\app.py --port 9000     # -> http://127.0.0.1:9000/
```

### Change the checkpoint

Without a flag the app takes the **first one that exists**, in this order:

1. `train/run_ppocr/big/best.pt` — the fine-tuned PP-OCRv6 (the current run)
2. `train/run_ppocr/final/best.pt` — the earlier PP-OCRv6 checkpoint
3. `train/run/crnn_big/ckpt/step_*.pt` — the newest CRNN step, if that run exists
4. `train/run/foldA/ckpt/step_0006578.pt` — the older CRNN checkpoint

To serve one explicitly:

```powershell
.venv-gpu\Scripts\python.exe webapp\app.py --checkpoint "train\run\foldA\ckpt\step_0006578.pt"
```

The kind of the checkpoint is taken from the directory it lives in (`run_ppocr` → PP-OCRv6,
anything else → our CRNN). A PP-OCRv6 checkpoint needs the transformers model
`PaddlePaddle/PP-OCRv6_medium_rec_safetensors`; it is already in the local Hugging Face cache
(`.hf-cache/`), and the app asks the hub for local files only — **no network is used**.

> The checkpoint is read **once, at startup**. When a training run rewrites `best.pt` while the
> server is up, the server keeps serving the snapshot it loaded; restart it to pick up a newer one.

---

## 5. If the GPU is busy

The GPU is shared with the training runs. A prediction is one small image, but if CUDA runs out
of memory the app prints `CUDA OOM - retrying on the CPU` and repeats the prediction on the CPU
automatically. To force the CPU from the start:

```powershell
.venv-gpu\Scripts\python.exe webapp\app.py --device cpu
```

---

## 6. Files

| file | what |
|---|---|
| `webapp/app.py` | the server (standard library only) |
| `webapp/static/index.html` | the page (self-contained: CSS and JS inline, no CDN) |
| `webapp/README.md` | this file |
| `reports/WEBAPP.md` | what was built and measured |

Nothing outside `webapp/` (and the report) is written by the app. The dataset is opened
**read-only**; the app refuses any path outside `dataset/out` and `dataset/out_ru`.
