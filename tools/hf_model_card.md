---
license: apache-2.0
tags:
- captcha
- ocr
- minecraft
- anti-bot
- pp-ocr
- base_model:PaddlePaddle/PP-OCRv6_medium_rec_safetensors
---

# CaptchaOCR PP-OCRv6 — a text recogniser for Minecraft anti-bot captchas

> ## Status: the weights are **not published yet**. This repository holds the model card only.
>
> The fine-tune on the [CaptchaOCR dataset]({DATASET_URL}) has **not been run to completion**.
> The main run reached **{EPOCHS_COMPLETED} epochs of {PLANNED_EPOCHS} planned
> ({STEPS_COMPLETED} of {PLANNED_STEPS} steps)** and was stopped by the author, so there is
> **no checkpoint, no `config.json` and no weight file** in this repository. Nothing here is
> invented: every number below is a measurement, and the file it was measured in is named
> next to it.
>
> **RU:** репозиторий модели пока **пуст по весам** — здесь только карточка. Основной прогон
> дообучения отработал **{EPOCHS_COMPLETED} эпох из {PLANNED_EPOCHS}** (шаг
> **{STEPS_COMPLETED} из {PLANNED_STEPS}**) и был остановлен автором; обучение продолжается.
> Пилотный прогон на 2 эпохи (`train/run_ppocr/smoke/`) — это отдельный прогон, его числа
> не относятся к основному прогону и в таблицах ниже не подмешаны.

## What it reads

Frames from the [CaptchaOCR dataset]({DATASET_URL}) — the kind of pictures the model is trained
on. The caption gives the type and the **gold answer** from `labels.jsonl` (what the player has
to type). The links are absolute: the pictures live in the dataset repository, not in this one.

| | | |
|---|---|---|
| ![Minecraft map captcha](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/resolve/main/data/out/haq/mapcha/map/001.png) | ![Latin code captcha](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/resolve/main/data/out/LagBug/XProtect/code/001.png) | ![Cyrillic captcha](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/resolve/main/data/out_ru/LimboFilter/symbols/001.png) |
| `haq/mapcha/map` — 128×128 map, 4 Latin characters · answer `s8TO` | `LagBug/XProtect/code` — 130×130, white background, noise · answer `EzhYNY` | `LimboFilter/symbols` — 128×128, 3 Cyrillic characters · answer `ЪМИ` |

## What this model is

A fine-tune of **PP-OCRv6 medium** (PaddleOCR's text recogniser) on the CaptchaOCR dataset: the
captchas that open-source Minecraft anti-bot plugins draw, rendered by this project's own Java
generators ({N_TYPES} captcha types, {N_SAMPLES} labelled PNG, {N_PLUGINS} upstream plugins).

* **Architecture:** PP-OCRv6 medium recogniser — PP-LCNetV4 backbone + CTC head,
  `transformers` class `{MODEL_CLASS}`
  (`model_type: pp_ocrv6_small_rec`), {N_PARAMS} parameters, hidden size {HIDDEN_SIZE}.
* **Dictionary:** the base model's own {HEAD_CLASSES} classes (index 0 = CTC blank, space at the end).
* **Input:** the captcha **text band** (the strip of pixels that carries the answer), not the whole
  frame: resized to height 48, width scaled proportionally and right-padded to 320, BGR channel
  order, normalised as `(x / 255 - 0.5) / 0.5`.
* **Output:** per-timestep class probabilities; decoded greedily (CTC: collapse repeats, drop the
  blank). Greedy decoding is the right decoder here — the answers are random strings, so a language
  model has nothing to exploit.

**The band is the whole game.** On the 29 dataset types that carry a band, the base model scores
`acc_micro = {BAND_ACC_ROI}` on the band and `acc_micro = {FRAME_ACC_ROI}` on the whole frame — about
16× worse on the frame. A solver must crop first.

## Provenance and licence

* **Base model:** [`{BASE_MODEL}`]({BASE_MODEL_URL}) — {BASE_LICENCE}, by PaddlePaddle.
* **This model:** that base, fine-tuned on the CaptchaOCR dataset published here:
  [`{DATASET_REPO}`]({DATASET_URL})
  ({N_TYPES} captcha types · {N_SAMPLES} labelled PNG · {N_PLUGINS} upstream plugins).
* **Licence of the weights:** {BASE_LICENCE}, inherited from the base model. The fine-tuning code and
  this card are released under the same terms.
* **Licence of the dataset:** *not* {BASE_LICENCE} — the dataset is split by the licence of the
  upstream plugin of each captcha type. The dataset card has the per-type table, and the file
  `LICENSE` in the dataset repository spells the same table out in full.

## Measured results

### This repository's weights

**No weights, no metrics — the training run has not been completed.** This section will hold the
exact match and CER per type and on the type-held-out split when a fine-tune that is actually
better than the base model is finished. Until then, treat every number below as the **starting
point**, not as a result of this repository.

### The fine-tuning run that was measured (incomplete, stopped by the author)

{TRAIN_RUN_BLOCK}

### The base model, measured before fine-tuning (the zero step of that run)

{ZERO_STEP_TABLE}

### The base model on the whole dataset (archived benchmark)

| measurement | value | source |
|---|---|---|
| exact match (micro) on the {N_ROI_TYPES} band-carrying types, band crop | {BAND_ACC_ROI} | `reports/bench_models/ppocrv6-medium.json` |
| exact match (micro) on the same {N_ROI_TYPES} types, whole frame | {FRAME_ACC_ROI} | `reports/bench_models/ppocrv6-medium.json` |
| exact match (micro) on all {N_TYPES} types, band crop | {ALL_TYPES_BAND_ACC} | `reports/bench_models/ppocrv6-medium.json` |

Every number in this card comes from a file of the **CaptchaOCR** project repository — the
measured results are in `reports/`, they are not typed by hand and nothing is extrapolated.

**Why the weights are not here yet.** The measured run did **not** improve on the base model:
the median exact match over the 7 held-out types fell from {ZERO_STEP_MEDIAN} (untouched base)
to {AFTER_MEDIAN} at epoch {BEST_EPOCH} and to {LAST_EVAL_MEDIAN} at epoch {LAST_EVAL_EPOCH}, and
one type out of seven got better while six got worse. A checkpoint like that is deliberately
**not** published: shipping it as "the model" would misrepresent it. Training continues with a
changed hypothesis (a much smaller learning rate, a frozen backbone, a larger and more diverse
training set) — the plan and the measurements are in `reports/TRAINING_PPOCR_V6.md` §8.

## How to use it

> The snippet below is the **preprocessing the project itself uses** (`train/ppocr_data.py`), and it
> was verified end-to-end against the base model on a real sample of the dataset (it decoded the
> held-out sample `JSH32/Minecaptcha/map/001.png`, band `[25, 77, 79, 35]`, as `PTAY`, which is the
> gold answer). It is written for the moment the weights are published — until then
> `from_pretrained("{REPO_ID}")` has nothing to load.

```python
import json

import numpy as np
import torch
from huggingface_hub import hf_hub_download
from PIL import Image
from transformers import PPOCRV6SmallRecForTextRecognition

REPO_ID = "{REPO_ID}"

model = PPOCRV6SmallRecForTextRecognition.from_pretrained(REPO_ID).eval()
# the dictionary comes with the model repository (preprocessor_config.json)
character_list = json.load(
    open(hf_hub_download(REPO_ID, "preprocessor_config.json"), encoding="utf-8")
)["character_list"]

HEIGHT, MAX_WIDTH = 48, 320


def prepare(band: Image.Image) -> torch.Tensor:
    """band -> (1, 3, 48, 320) float tensor."""
    scale = HEIGHT / max(1, band.height)
    w = max(1, min(MAX_WIDTH, int(round(band.width * scale))))
    small = band.convert("RGB").resize((w, HEIGHT), Image.BILINEAR)
    a = np.asarray(small, dtype=np.float32) / 255.0
    a = a[:, :, ::-1]            # BGR, as PP-OCRv6 expects
    a = (a - 0.5) / 0.5         # paddle normalisation
    canvas = np.zeros((3, HEIGHT, MAX_WIDTH), dtype=np.float32)
    canvas[:, :, :w] = a.transpose(2, 0, 1)
    return torch.from_numpy(canvas)[None]


def greedy_decode(probs) -> str:
    """CTC greedy decode: collapse repeats, drop the blank."""
    best = probs.argmax(dim=-1)[0].tolist()
    chars, prev = [], -1
    for k in best:
        if k != prev and k != 0:
            chars.append(character_list[k])
        prev = k
    return "".join(chars)


image = Image.open("captcha.png")
x, y, w, h = (25, 77, 79, 35)        # the answer band: take it from labels.jsonl
band = image.crop((x, y, x + w, y + h))

with torch.no_grad():
    probs = model(pixel_values=prepare(band)).last_hidden_state

print(greedy_decode(probs))
```

The band (`roi`) is not optional: on scene-like captchas the answer is one line among several, and
the whole frame makes the model read the wrong line.

## Reproducing

The training code lives in the **CaptchaOCR** project repository:

```powershell
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --epochs 30 --batch-size 32
```

`train/finetune_ppocr.py` fine-tunes `{BASE_MODEL}` on the dataset, holds out whole **plugins**
(never a random image split: several captcha types have only a few distinct answers, so a random
split lets the exact gold answer of a test image appear in the training half), and reports exact
match and CER per type plus the median over types. `train/ppocr_data.py` holds the dataset loader
and the preprocessing shown above.

The measured report of the run quoted above is `reports/TRAINING_PPOCR_V6.json` (numbers) and
`reports/TRAINING_PPOCR_V6.md` (the analysis), both in the project repository.

## Repository metadata

While the weights are absent, this repository declares **only** `license: {BASE_LICENCE}` and the
tags above — there is deliberately **no** `library_name`, **no** `pipeline_tag` and **no**
`base_model:` field, because those three fields make the Hub list the repository as a loadable
`transformers` model. There is nothing to load yet. When the weights are published, the
`library_name: transformers` and `pipeline_tag: image-to-text` fields will be added back together
with the weight files, in the same commit.

## Limitations

* **Only the text band is read.** This is a recogniser, not a solver: it does not reverse strings,
  does not turn Russian number words into digits and does not compute arithmetic.
* **No Cyrillic in the dictionary.** The base model's {HEAD_CLASSES} classes contain no Cyrillic at
  all, so the Cyrillic captcha types of the dataset cannot be expressed in this model's alphabet.
* **The data is synthetic.** Every image is a render of this project's own generators — faithful to
  the upstream algorithms, but not a screenshot of a live server.
* **Generalisation is the hard part.** A recogniser can memorise a plugin's style instead of
  learning the characters; only the type-held-out numbers mean anything.

## Citation

This model is a fine-tune of PP-OCRv6 by PaddlePaddle ({BASE_LICENCE}). The dataset is the
CaptchaOCR dataset, re-rendered from open-source Minecraft anti-bot plugins. See the dataset card
for the provenance and the per-type licence of every captcha type.
