---
license: apache-2.0
language:
  - en
  - ru
library_name: transformers
pipeline_tag: image-to-text
tags:
  - captcha
  - ocr
  - minecraft
  - pp-ocrv6
  - text-recognition
  - cyrillic
datasets:
  - Titlehhhh/captchaocr-dataset
base_model:
  - PaddlePaddle/PP-OCRv6_medium_rec_safetensors
---

# CaptchaOCR PP-OCRv6 — a text recogniser for Minecraft anti-bot captchas

A fine-tune of **PP-OCRv6_medium_rec** on Minecraft anti-bot captchas whose CTC head was
**extended to 18 762 classes**, so that it reads Cyrillic as well as Latin letters and digits.
Feed it **one crop of the answer band**, get the string drawn on it.

> **This card describes the `universal_v1` checkpoint — the weights that are actually in this
> repository.** The card that was here before described an older run (`all20`) whose weights are
> **no longer** published: 18 710 classes, 15 types, median exact 0.920. Those numbers were true
> of that model and are **not** true of this one.

## What is in this repository

| file | what it is |
|---|---|
| `model.safetensors` | the weights: 308 tensors, 19 186 154 float parameters |
| `config.json` | the base architecture, with `head_out_channels` patched to 18 762 |
| `preprocessor_config.json` | the base processor + the PaddleOCR normalisation + the 18 762-character dictionary |
| `processor_config.json` | `PPOCRV6SmallRecImageProcessor` |
| `character_list.txt` | the dictionary, one entry per line, index 0 = `blank` |
| `finetune_meta.json` | the provenance of the export (checkpoint, epoch, step, α) |
| `README.md` | this card |

Provenance, as shipped in `finetune_meta.json`:

| | |
|---|---|
| base model | `PaddlePaddle/PP-OCRv6_medium_rec_safetensors` (Apache-2.0) |
| fine-tuned checkpoint | `train/runs/ppocrv6/universal_v1/best.pt` |
| epoch / step | 4 (the last of 5) / 2 440 |
| classes | **18 762** (index 0 = `blank`) — the pretrained head is **kept and extended**, not replaced |
| float parameters | **19 186 154** |
| weight interpolation | **none** — α = 1.0, the checkpoint exactly (see below) |
| transformers class | `PPOCRV6SmallRecForTextRecognition` |
| normalisation | mean = std = 0.5 (the PaddleOCR convention) |
| exported by | `train/export_ppocr_hf.py` |

### What changed in the head

The pretrained PP-OCRv6 dictionary has **18 710** classes and no Cyrillic letters at all. Rows
**0 … 18 709** of the published dictionary are the pretrained ones (index 18 709 is the space);
rows **18 710 … 18 761** are the **52 Cyrillic characters** that were appended:

```
ЁАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ  +  авдеикмнопрстцчшыья
```

The pretrained rows were **kept**, not replaced (`--expand-charset` grows the head and copies the
old rows). The extension was done in an earlier run of the same recipe; in this run the flag
reported «0 characters missing», i.e. the grown head was inherited from the previous checkpoint
together with its weights.

## The training run in numbers

| | |
|---|---|
| initialised from | `train/runs/ppocrv6/limbo_cyr3/best.pt` — the **«replay mix»** Cyrillic checkpoint (3 short Cyrillic types + digits + 5 Latin types, 4 epochs) |
| epochs × steps | 5 × 488 = **2 440** steps |
| batch size | 32 |
| learning rate | **8e-6** for the backbone **and** 8e-6 for the head |
| weight decay / grad clip | 0.01 / 1.0 |
| `--limit-per-type` | **1 500** |
| training examples | **15 594** |
| evaluation set | **11 400** images over 18 types |
| wall clock | **33.9 min** (2 032 s) at **108 img/s** (one GTX 1080 Ti, fp16/AMP) |
| seed | 42 · `--workers 0` (the sandbox this was trained in denies multiprocessing named pipes) |

### What was trained on, and what was not

**12 types were trained on.** Eight of them are fed as the **answer band** (the `roi` rectangle
of the dataset); the four that have no band at all are trained on the **whole frame**, so the
model has to find the code by itself:

| type | input |
|---|---|
| `out/Archy-X/Krypton/map` | band |
| `out/haq/mapcha/map` | band |
| `out/just-captcha/ProstoCaptcha/map` | band |
| `out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | band |
| `out_ru/GalleryCaptcha/ru-symbols` | band |
| `out_ru/GalleryCaptcha/ru-web` | band |
| `out_ru/LimboFilter/digits` | band |
| `out_ru/LimboFilter/symbols` | band |
| `out/InstantlyMoist/Captcha/textcaptcha` | **whole frame** |
| `out/LagBug/XProtect/code` | **whole frame** |
| `out/LagBug/XProtect/map` | **whole frame** |
| `out/irootdev/AnBot/captcha` | **whole frame** |

(The names above are the dataset's own `type_id` values.)

**6 types were never seen in training.** The unit of generalisation is the **plugin**, never the
picture: these six whole plugins were held out of the training set:

`out/JSH32/Minecaptcha/map`, `out/jonesdevelopment/sonar/standard`,
`out/jonesdevelopment/sonar/legacy`, `out/jonesdevelopment/sonar/complex`,
`out_ru/BotFilter/map`, `out_ru/CaptchaVerifyZ/map`.

**3 types were excluded on purpose:** `out_ru/GalleryCaptcha/ru-numberword`,
`out_ru/GalleryCaptcha/ru-numberword-caption` and `out_ru/LimboFilter/map`. In all three the picture shows a
Russian number **written out in words** while the player types **digits** (`text != answer` in
all 10 000 rows of each). Converting a written number into a typed one is a **solver step**,
not an OCR task, so the model was not asked to do it. That is a limitation of the *task*, not a
defect of the model — but it does mean these three types are **not supported**.

## Measured results

Measured inside the same run (`train/runs/ppocrv6/universal_v1/result.json`): 11 400 images over
18 types, greedy CTC decoding, exact match against the drawn string.

| aggregate | before this run¹ | **after** |
|---|---|---|
| median exact match over 18 types | 0.8750 | **0.8875** |
| median CER | 0.0394 | **0.0344** |
| micro exact match (11 400 images) | 0.6499 | **0.7797** |
| micro CER | 0.1795 | **0.0755** |

¹ «before this run» is the **zero step of this very run** — the checkpoint it was initialised
from (`limbo_cyr3/best.pt`), **not** the pretrained PP-OCRv6 base. The fine-tune moved the
median only a little (0.875 → 0.8875) but the **micro** average a lot (0.6499 → 0.7797): the
median is dominated by the types that were already solved, while the micro average counts every
image — and the frame-trained types that were unreadable rose sharply
(`out/LagBug/XProtect/code` 0.00 → 0.36, `out/LagBug/XProtect/map` 0.00 → 0.27,
`out/InstantlyMoist/Captcha/textcaptcha` 0.12 → 0.24).

### Types the model was trained on

These numbers are a **sample-level hold-out**: the first 200 rows of every type were taken out
of training, the rest were trained on. They are *not* unseen-plugin numbers.

| type | n | exact (zero step) | **exact** | CER |
|---|---:|---:|---:|---:|
| `out/Archy-X/Krypton/map` | 200 | 1.0000 | **1.0000** | 0.0000 |
| `out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | 200 | 1.0000 | **1.0000** | 0.0000 |
| `out/irootdev/AnBot/captcha` | 200 | 0.9350 | **0.9950** | 0.0017 |
| `out/haq/mapcha/map` | 200 | 0.9650 | 0.9550 | 0.0112 |
| `out_ru/GalleryCaptcha/ru-web` | 200 | 0.9300 | 0.9250 | 0.0150 |
| `out/just-captcha/ProstoCaptcha/map` | 200 | 0.9250 | 0.9150 | 0.0150 |
| `out_ru/LimboFilter/digits` | 200 | 0.8900 | 0.8900 | 0.0288 |
| `out_ru/GalleryCaptcha/ru-symbols` | 200 | 0.8600 | **0.8850** | 0.0400 |
| `out_ru/LimboFilter/symbols` | 200 | 0.7650 | **0.8000** | 0.0783 |
| `out/LagBug/XProtect/code` | 200 | 0.0000 | **0.3600** | 0.1542 |
| `out/LagBug/XProtect/map` | 200 | 0.0000 | **0.2700** | 0.1850 |
| `out/InstantlyMoist/Captcha/textcaptcha` | 200 | 0.1200 | **0.2400** | 0.4220 |

### Types the model never saw

Whole plugins that were held out of training — these are the honest generalisation numbers.

| type | n | exact (zero step) | **exact** | CER |
|---|---:|---:|---:|---:|
| `out_ru/CaptchaVerifyZ/map` | 1 500 | 0.9647 | **0.9780** | 0.0045 |
| `out/JSH32/Minecaptcha/map` | 1 500 | 0.9340 | **0.9373** | 0.0162 |
| `out_ru/BotFilter/map` | 1 500 | 0.7113 | **0.8140** | 0.0508 |
| `out/jonesdevelopment/sonar/legacy` | 1 500 | 0.5973 | **0.7693** | 0.0793 |
| `out/jonesdevelopment/sonar/complex` | 1 500 | 0.3520 | **0.6253** | 0.1293 |
| `out/jonesdevelopment/sonar/standard` | 1 500 | 0.2613 | **0.5707** | 0.1671 |

**One caveat about the protocol.** The evaluation runs on held-out rows of the **same generator
render** the model was trained on (the generators are not seeded, so a re-render is a different
sample set). For the twelve trained types the hold-out is by *sample*; only the six held-out
plugins above are genuinely unseen styles.

## No weight interpolation — and why the previous card said α = 0.4

The previous version of this repository published a WiSE-FT soup, `θ = 0.4·θ_ft + 0.6·θ_pretrained`.
That was the right call **for that model**: a small fine-tune on a few types degraded the unseen
plugins, and interpolating back towards the base restored them (measured there: base median
0.588 → α = 0.4 median 0.638 → α = 1.0 median 0.480).

This model is different in two ways: it is trained on **most** of the types it is evaluated on,
and its head has **grown**. On an expanded head the interpolation has nothing to interpolate
*towards* for the 52 appended rows — the base model has no such rows — while the encoder is
dragged back to the pretrained solution. Measured on the α-sweep of the `limbo_cyr3`
predecessor: the sweep's best α = 0.6 lifted the Latin held-out types from 0.644 to 0.772 and
at the same time **collapsed the Cyrillic ones**:

| type | α = 1.0 | after interpolation (α = 0.6) |
|---|---:|---:|
| `out_ru/LimboFilter/symbols` | 0.765 | **0.016** |
| `out_ru/GalleryCaptcha/ru-symbols` | 0.860 | **0.002** |
| `out_ru/LimboFilter/digits` | 0.890 | **0.666** |

So WiSE-FT is **destructive** on an expanded head. That soup was kept as an exhibit
(`train/runs/ppocrv6/limbo_cyr3/soup_best.pt`) and is **not** used here. What works for a
vocabulary expansion on this model is **replay** — keeping the old data in the training mix —
and this checkpoint is therefore published with **α = 1.0**: the fine-tuned weights, unchanged.

## What this model is NOT good at

* **It is not a universal captcha solver.** It is a fine-tune for a **known set of captcha
  styles**: a plugin that draws in a style absent from the training set will not be handled.
  For the six plugins that were held out, the honest expectation is the numbers in the table
  above — between 0.57 and 0.98 exact match, not 1.0.
* **The three number-word types are not supported at all** (`out_ru/GalleryCaptcha/ru-numberword`,
  `out_ru/GalleryCaptcha/ru-numberword-caption`, `out_ru/LimboFilter/map`): the picture shows a number
  written in Russian words while the answer is digits. Use a solver step for those.
* **The weakest trained types are `out/LagBug/XProtect/code` (0.36) and `out/LagBug/XProtect/map`
  (0.27)**: both are the same 130×130 sheet with per-character cumulative translation and 51
  interference lines. `out/InstantlyMoist/Captcha/textcaptcha` (0.24) is a 128×128 sheet with
  thin diagonal noise.
* **It reads a band, not a picture.** On a whole game screenshot it falls apart — see below.

## How to use it

```python
import torch
from PIL import Image
from transformers import PPOCRV6SmallRecForTextRecognition, PPOCRV6SmallRecImageProcessor

REPO = "Titlehhhh/captchaocr-ppocrv6"

model = PPOCRV6SmallRecForTextRecognition.from_pretrained(REPO)
proc = PPOCRV6SmallRecImageProcessor.from_pretrained(REPO)

image = Image.open("001.png").convert("RGB")          # a crop of the answer band
px = proc(images=[image], return_tensors="pt")["pixel_values"]   # 48 x 320, mean = std = 0.5

with torch.no_grad():
    logits = model.head.head(model.head.encoder(
        model.model(px).last_hidden_state).last_hidden_state)

# greedy CTC decoding against character_list.txt (index 0 = "blank")
with open("character_list.txt", encoding="utf-8") as f:
    dictionary = [line.rstrip("\r\n") for line in f]   # rstrip, not strip: " " is a class

ids = logits.argmax(-1)[0].tolist()
text, prev = [], -1
for i in ids:
    if i != prev and i != 0:        # collapse repeats, drop the blank
        text.append(dictionary[i])
    prev = i
print("".join(text))
```

The same 18 762-character dictionary is also inside `preprocessor_config.json`, so the processor
can decode without the text file. The input geometry is 48 × 320 (resize + pad), and the
normalisation is `mean = std = 0.5` — the PaddleOCR convention the fine-tune was trained with.
**Do not let the processor fall back to the ImageNet statistics**: `preprocessor_config.json`
already carries the patched values.

### The important practical part: give it a band, not a screenshot

The model is trained on the **band** for 8 of its 12 types, so it expects a tight crop of the
code. On a **whole game screenshot** it collapses: measured on the six real screenshots of the
project owner, feeding the whole frame gives **2/6** correct readings.

The fix is a **cropper** — an «eye» in front of the recogniser. It proposes candidate text bands
(a per-type heuristic, an ink box, and a glyph detector), the model reads every candidate, and
the reading with the **highest confidence** wins (vote counts are only a tie-break). With the
cropper: **6/6** on those same six screenshots. The implementation ships with the project
(`webapp/cropper.py`, `webapp/app.py` — see
<https://github.com/Titlehhhh/CaptchaOCR> and `reports/CROPPER.md` for the measured numbers).

If you use the dataset: crop by `roi` whenever it is not `null`.

## The dataset this was trained on

[`Titlehhhh/captchaocr-dataset`](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset)
— synthetic, every image is a re-render by this project's own Java generators of a captcha drawn
by an open-source Minecraft plugin. As published (commit
`dd4d7479a95f8e4c8ea19643dfe5889fe5dea113`):

| | |
|---|---|
| types | **20** (12 in `out`, 8 in `out_ru`), 13 plugins |
| samples | **200 000** (10 000 per type), 1.9 GiB of PNG bytes |
| files | 9 Parquet shards (`data/train-*-of-00009.parquet`), one row per sample, raw PNG in `image` |
| bands | 12 types carry an `roi` band; 119 984 rows have one, 80 016 do not |
| `text != answer` | 3 types (the Russian number words) |
| alphabet | 115 distinct characters over the whole set |

Two facts worth stating plainly:

* The model was trained on the **project's own render** of that dataset (10 000 images per
  type), not on the published Parquet shards — the pixels are the same style, the sample set is
  that of the local render.
* The type **`out_ru/LimboFilter/digits`** (four digits, real-server style) was trained on and
  **is not part of the published dataset snapshot**: the generator gained that type after the
  dataset was exported.

### Provenance and licence

* Base model: `PaddlePaddle/PP-OCRv6_medium_rec_safetensors`, **Apache-2.0**. These weights are
  a derivative of it.
* The dataset is **synthetic** — re-renders, not screenshots of a live server; no picture, page
  or answer of a third-party commercial service is used or published.
* The dataset is published under **the licence of the upstream plugin each row came from**
  (`license_name: mixed-per-plugin-licences`; the per-plugin breakdown is in the dataset
  repository's `LICENSE` and in its card). Some of those licences forbid commercial hosting or
  reserve all rights — **read them before you use the data**.
* The 52 characters added to the head are the Cyrillic alphabet; the images that taught them
  come from the `GalleryCaptcha` and `LimboFilter` types, whose licences are listed above.

## Reproducing

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:HF_HOME="C:\Users\Title\Projects\CapthaModel\.hf-cache"

# the run that produced these weights
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\runs\ppocrv6\universal_v1 `
    --init-from train\runs\ppocrv6\limbo_cyr3\best.pt --expand-charset --train-frames `
    --epochs 5 --batch-size 32 --lr 8e-6 --head-lr 8e-6 --workers 0 --seed 42 `
    --limit-per-type 1500 --holdout-per-type 200 --eval-every 5 --save-every 400 --max-minutes 60 `
    --val-types out/jonesdevelopment/sonar/standard out/jonesdevelopment/sonar/legacy out/jonesdevelopment/sonar/complex out_ru/BotFilter/map out_ru/CaptchaVerifyZ/map out/laforetbrut/are-you-sure/code out/JSH32/Minecaptcha/map `
    --exclude-types ru-numberword ru-numberword-caption LimboFilter/map

# the export (alpha = 1.0 -> the checkpoint itself, no interpolation)
.venv-gpu\Scripts\python.exe train\export_ppocr_hf.py `
    --ckpt train\runs\ppocrv6\universal_v1\best.pt --soup-alpha 1.0 `
    --out train\runs\ppocrv6\universal_v1\export_hf
```

Notes on the command as it was actually run:

* `--init-from train\runs\ppocrv6\limbo_cyr3\best.pt` points at the **replay-mix** checkpoint of
  the same recipe (the chain is `limbo_cyr` → charset expansion → `limbo_cyr3` → replay mix →
  `universal_v1`); the whole chain is documented in `reports/TRAINING_LIMBO_DIGITS.md` §8.
* The filter `out/laforetbrut/are-you-sure/code` matched **no type** in the dataset and had no
  effect; the other six `--val-types` are the six held-out plugins.
* `--expand-charset` was a **no-op in this run** («0 characters missing»): the head had already
  been grown to 18 762 classes by the predecessor checkpoint.
* The dataset is **not seeded**: a re-render produces a different sample set, so the exact
  per-type numbers above belong to the render this checkpoint was measured on.
