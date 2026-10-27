# `webapp/` — a tiny local web app for the trained recogniser

A single-page app that lets the project owner drop a captcha PNG into the browser and get the
model's prediction back. It is **local and offline**: the Python standard library does the HTTP,
the weights come from the disk, the page has no CDN and no external references.

```
browser  ──HTTP──>  webapp/app.py  ──torch──>  PP-OCRv6 (train/runs/ppocrv6/universal_v1/best.pt)
   ▲                      │
   │                      └── reads (read-only) dataset/out/** , dataset/out_ru/**
   └── /api/demo , /api/image , /api/random
```

---

## 0. The modules

`app.py` is the **entry point only**: the routes of the HTTP API and `main()`. The logic lives
next door, in modules of 25–370 lines:

| module | what |
|---|---|
| `webapp/app.py` | the entry point: the HTTP routes (`GET /api/*`, `POST /predict`) and `main()` |
| `webapp/filepaths.py` | where things are: the repository root, the static page, the two dataset trees |
| `webapp/dataset.py` | the read-only index of the dataset: `Dataset` — the samples of a type, the demo types, the `labels.jsonl` row of a picture |
| `webapp/backends.py` | the checkpoint rule (`DEFAULT_CHECKPOINT`, `resolve_checkpoint`), the preprocessing, and the two backends `PPOCRBackend` / `CRNNBackend` |
| `webapp/pipeline.py` | **the rule of the vote** (`answer_score`, `read_candidates`, `vote_frame`) and the state of the app (`App`) |
| `webapp/cropper.py` | the cropper — the "eye" (numpy + Pillow, no model) |
| `webapp/eval_cropper.py` | the measurement script — it calls the **same** rule of `pipeline.py` |
| `webapp/show_boxes.py` | draws the winning band on the picture it was given |
| `webapp/static/index.html` | the page (self-contained: CSS and JS inline, no CDN) |

The names the measurement script imports (`Dataset`, `resolve_checkpoint`, `PPOCRBackend`,
`CRNNBackend`, `DEFAULT_CHECKPOINT`) are re-exported by `app.py`, so `app.<name>` keeps working.

---

## 1. The cropper — the "eye"

A picture that arrives **without** a band (an upload, a file the dataset does
not know) used to be cropped to its *ink*: the pixels that differ from the
frame's most common colour. On a frame full of interference that degenerates —
the interference counts as ink, the box becomes the whole canvas, and the
recogniser reads noise. Measured on the owner's own screenshots: **2 of 6**
read correctly.

`webapp/cropper.py` replaces that fallback with a layered decision:

| layer | what it does |
|---|---|
| (a) per-type heuristics | a table keyed by the captcha style (the layout of the plugin), plus the band **learned** from `labels.jsonl` for a known type |
| (b) the strengthened ink box | the background is estimated from *local stability*, the thin strokes are removed by a morphological opening |
| (c) the glyph detector | colour clustering, connected components, a search for a row of glyph-shaped components |

The layers **propose**, they do not decide: the cropper returns an ordered list
of candidate bands (each with a rendering), the recogniser reads every one of
them, and the **rule of §2** picks the winner. The tiny detector proposes, the
model disposes.

The rendering that works best is the **original pixels of the glyphs on a
white canvas** — the anti-aliased edge of the stroke is kept, otherwise a 6 is
read as an `l`.

Measured on the owner's six screenshots (`test/*.png`): **6/6** (was 2/6).

---

## 2. The rule of the vote — one rule, one place

The rule lives in `webapp/pipeline.py` and **only** there. The web app
(`pipeline.App.predict_frame`), the measurement script
(`webapp/eval_cropper.py::vote`) and the drawing script
(`webapp/show_boxes.py`) all call the same function — there is no second copy
of it anywhere.

In one paragraph: the cropper proposes the bands, the recogniser reads **every**
one of them (in one batched forward pass), and the winner is **the most
confident reading that looks like an answer**. The number of proposals that
agreed on a reading only breaks a tie — counting the votes first is wrong: a
crowd of bad proposals (the whole frame, a colour that is not the code) outvotes
one excellent proposal.

"What looks like an answer" is `answer_score()` — deliberately blunt, because
it is the difference between the code and the title of a chat scene:

| the reading | score | why |
|---|---|---|
| empty | 0.00 | nothing was read |
| has a space or punctuation (`Tries Left: 2`) | 0.10 | a phrase, not a code |
| 1–2 or 11+ characters | 0.25 | too short or too long for a code |
| one capitalised word (`Captcha`, `Enter`) | 0.30 | a **word**, not a code |
| 3–10 letters and digits (`izND`, `A7k2p`, `1651`) | 1.00 | a code |

The score scales the confidence: `confidence × (0.05 + 0.95 × shape)`. The title
of a scene is read with a high confidence too — the shape is what tells the code
from the title.

**Two rounds.** The proposed bands are read first. The horizontal strips of the
frame (the captcha-scale analogue of the "gundam" tiling of Unlimited OCR 2) are
tried **only** when that first answer is less confident than `--crop-conf`
(default 0.99). They are not mixed into the first round on purpose: a bigger
candidate pool makes the "most confident wins" rule find *confident rubbish*
(measured: 6 samples of 210 broken — `reports/UNLIMITED_OCR.md` §2.6).

---

## 3. Start it (one command)

From the **repository root** (the directory that contains `AGENTS.md` and `dataset/`):

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
[webapp] dataset types: 21  demo types: out/Archy-X/Krypton/map, out/JSH32/Minecaptcha/map, ...
[webapp] checkpoint: train\runs\ppocrv6\universal_v1\best.pt (ppocr)
[webapp] serving http://127.0.0.1:8765/  (Ctrl+C to stop)
```

The dataset of this checkout holds **21 types** (12 in `dataset/out`, 9 in
`dataset/out_ru`, 210 000 PNGs); **8** of them are demo types (§4).

---

## 4. The page

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
guaranteed in advance. On this checkout that leaves **8 types**; all 21 types are still listed
in the dropdown.

---

## 5. The HTTP API

| route | what it does |
|---|---|
| `GET /` | the page (`webapp/static/index.html`) |
| `GET /api/status` | backend, checkpoint, device, model info, preprocessing parity |
| `GET /api/types` | all the types + the demo type ids |
| `GET /api/demo?type=<type id>&limit=3` | the demo pictures of a type with their ground truth |
| `GET /api/demo?type=<type id>&limit=3&random=1` | the same, but a **random sample** of that type |
| `GET /api/random?pool=all\|demo&limit=1` | a **random picture of a random type** |
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

The answer (measured, `dataset/out/haq/mapcha/map/001.png` on the pinned checkpoint):

```json
{
  "text": "ly8r",
  "confidence": 0.9649,
  "per_char": [{"char": "l", "confidence": 0.867}, {"char": "y", "confidence": 1.0},
               {"char": "8", "confidence": 1.0}, {"char": "r", "confidence": 0.9999}],
  "ground_truth": "ly8r",
  "exact_match": true,
  "file_name": "001.png",
  "source_path": "dataset/out/haq/mapcha/map/001.png",
  "type": "out/haq/mapcha/map",
  "ground_truth_answer": "ly8r",
  "exact_match_answer": true,
  "used_band": true,
  "crop_method": "roi (labels.jsonl)",
  "crop_box": [28, 68, 71, 46],
  "crop_votes": null,
  "crop_candidates": null,
  "crop_strips": null,
  "crop_tried": null,
  "model": "ppocrv6",
  "checkpoint": "train/runs/ppocrv6/universal_v1/best.pt",
  "device": "cuda",
  "latency_ms": 380.0
}
```

* `used_band` is `true` when the picture came from the dataset and the band of
  `labels.jsonl` was used — that is the measured-good path.
* When there is **no** band, the cropper proposes the bands
  (`crop_method`, `crop_box`, `crop_votes`, `crop_candidates`, `crop_strips`, `crop_tried`):
  `crop_method` is the winning proposal, `crop_votes` how many proposals
  agreed on the reading, `crop_candidates` how many bands were read, and
  `crop_tried` the readings themselves.

* `ground_truth` is the **drawn** string (`text` in `labels.jsonl`) — that is what the
  recogniser reads and what the comparison uses (letters and digits only, the same rule as
  `train/finetune_ppocr.py::norm`). `ground_truth_answer` is what a player has to type.
* A picture that is not in the dataset (an upload) has `ground_truth: null` and
  `exact_match: null`.

---

## 6. Options

| flag | default | what it does |
|---|---|---|
| `--port N` | `8765` | the port |
| `--host H` | `127.0.0.1` | the interface (keep it local) |
| `--device auto\|cuda\|cpu` | `auto` | `auto` = cuda when available |
| `--checkpoint PATH` | the pinned checkpoint below | serve this checkpoint instead |
| `--demo-types N` | `10` | how many types the demo picker offers (this checkout has 8 eligible ones) |
| `--crop-limit N` | `32` | how many bands the cropper may propose for a picture without a band (more = slower, better) |
| `--crop-conf F` | `0.99` | the horizontal strips of the frame are tried as well only when the best base answer is less confident than this |
| `--no-model` | off | start without loading a model (the page still works) |

### Change the port

```powershell
.venv-gpu\Scripts\python.exe webapp\app.py --port 9000     # -> http://127.0.0.1:9000/
```

### Change the checkpoint

The app serves **one pinned checkpoint**:

```
train/runs/ppocrv6/universal_v1/best.pt     # PP-OCRv6_medium_rec, head extended to 18 762 classes
```

To serve another one:

```powershell
.venv-gpu\Scripts\python.exe webapp\app.py --checkpoint "train\runs\ppocrv6\limbo_digits3\best.pt"
```

The kind of the checkpoint is taken from the directory it lives in (`ppocrv6` → PP-OCRv6,
anything else → our CRNN). A PP-OCRv6 checkpoint needs the transformers model
`PaddlePaddle/PP-OCRv6_medium_rec_safetensors`; it is already in the local Hugging Face cache
(`.hf-cache/`), and the app asks the hub for local files only — **no network is used**.

> The checkpoint is read **once, at startup**. When a training run rewrites `best.pt` while the
> server is up, the server keeps serving the snapshot it loaded; restart it to pick up a newer one.

---

## 7. If the GPU is busy

The GPU is shared with the training runs. A prediction is one small image, but if CUDA runs out
of memory the app prints `CUDA OOM - retrying on the CPU` and repeats the prediction on the CPU
automatically. To force the CPU from the start:

```powershell
.venv-gpu\Scripts\python.exe webapp\app.py --device cpu
```

---

## 8. Measure the cropper

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv-gpu\Scripts\python.exe webapp\eval_cropper.py --selftest      # the cropper alone, no model
.venv-gpu\Scripts\python.exe webapp\eval_cropper.py --demo-sweep --n 40 --seed 1234 `
    --out build\eval_webapp_refactor.json                            # the full measurement
```

The measurement uses the **same** model, the **same** preprocessing and the **same**
rule of the vote as the app (§2) — `eval_cropper.py` calls `pipeline.vote_frame`, it does
not keep a copy of the rule.

Three parts:

* **the screenshots** — the owner's six `test/*.png`; the file name **is** the code;
* **the demo sweep** — the 8 demo types × 3 pictures, read with the band of `labels.jsonl`
  (the path that already worked; it must not break);
* **the dataset** — a seeded random sample (21 types × `--n`): the **oracle band** of
  `labels.jsonl` (the ceiling of the model), the **cropper's** band and the **whole frame**,
  compared against both `answer` and `text` (they differ in a few types — arithmetic, Russian
  number words, the reversed string — and for those a recogniser that reads `text` cannot
  match `answer` by construction).

### The measured numbers

`--demo-sweep --n 40 --seed 1234` (21 types × 40 = 840 samples), against `answer`:

| input | exact match |
|---|---|
| oracle (the band of `labels.jsonl`) | **0.6679** |
| cropper (the band the cropper finds) | **0.6226** |
| whole frame (the old `ink_bbox` fallback) | **0.4357** |

Per tree: `out` (12 types, 480 samples) oracle 0.7354 / cropper 0.6958 / frame 0.4979;
`out_ru` (9 types, 360 samples) oracle 0.5778 / cropper 0.5250 / frame 0.3528.

The owner's screenshots: **6/6 exact**. The demo sweep: **23/24** — the one miss is
`out/JSH32/Minecaptcha/map 001.png`, gold `MMLI`, read `MMLl`: a model error on the
reference band, not a cropper error.

> The cropper number is the one that depends on the **rule**: before the rule was
> shared (`webapp/eval_cropper.py` kept a copy of it without the "looks like an
> answer" weight), the measurer read **0.5952**; with the app's own rule it reads
> **0.6226**. The oracle and the whole frame did not move (0.6679 / 0.4357 in both
> runs) — they do not go through the vote.

---

## 9. Files

| file | what |
|---|---|
| `webapp/app.py` | the entry point: the HTTP routes and `main()` |
| `webapp/filepaths.py` | the paths of the app |
| `webapp/dataset.py` | the read-only index of the dataset |
| `webapp/backends.py` | the checkpoint rule, the preprocessing, `PPOCRBackend`, `CRNNBackend` |
| `webapp/pipeline.py` | the rule of the vote and the state of the app |
| `webapp/cropper.py` | the cropper — the "eye" (numpy + Pillow, no model) |
| `webapp/eval_cropper.py` | the measurement script |
| `webapp/show_boxes.py` | draws the winning band on a picture |
| `webapp/static/index.html` | the page (self-contained: CSS and JS inline, no CDN) |
| `webapp/README.md` | this file |
| `reports/WEBAPP.md` | what was built and measured (the server) |
| `reports/CROPPER.md` | the cropper: the design and the measured numbers |

Nothing outside `webapp/` (and the reports) is written by the app. The dataset is opened
**read-only**; the app refuses any path outside `dataset/out` and `dataset/out_ru`.
