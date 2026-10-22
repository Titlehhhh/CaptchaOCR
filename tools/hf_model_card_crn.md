---
license: mit
library_name: transformers
tags:
- captcha
- ocr
- crnn
- ctc
- minecraft
pipeline_tag: image-to-text
---

# CaptchaOCR model — recogniser of Minecraft anti-bot captchas

A text recogniser for the captchas drawn by open-source Minecraft anti-bot plugins, trained
on the [CaptchaOCR dataset]({DATASET_REPO}).

> **Числа в этой карточке не выдуманы.** Всё, что можно было посчитать, посчитано из
> чекпоинта и из файла результатов; всё, что посчитать было нельзя, оставлено плейслолдером
> и помечено явно.

## What it reads

Frames from the [CaptchaOCR dataset]({DATASET_REPO}) — the kind of pictures the model is trained
on. The caption gives the type and the **gold answer** from `labels.jsonl` (what the player has
to type). The links are absolute: the pictures live in the dataset repository, not in this one.

| | | |
|---|---|---|
| ![Minecraft map captcha](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/resolve/main/data/out/haq/mapcha/map/001.png) | ![Latin code captcha](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/resolve/main/data/out/LagBug/XProtect/code/001.png) | ![Cyrillic captcha](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/resolve/main/data/out_ru/LimboFilter/symbols/001.png) |
| `haq/mapcha/map` — 128×128 map, 4 Latin characters · answer `s8TO` | `LagBug/XProtect/code` — 130×130, white background, noise · answer `EzhYNY` | `LimboFilter/symbols` — 128×128, 3 Cyrillic characters · answer `ЪМИ` |

## What it is

* **Architecture:** CRNN (CNN → BiLSTM) with a CTC head, {N_CLASSES} classes
  ({N_CHARS} characters plus the CTC blank).
* **Input:** a grayscale captcha **text band**, scaled to {IMAGE_HEIGHT}×{IMAGE_WIDTH},
  normalised with `(x / 255 - {IMAGE_MEAN}) / {IMAGE_STD}`.
* **Output:** CTC logits, decoded greedily.
* **Charset:** `{CHARSET}`
* **Hidden size:** {HIDDEN}; glyph height: {GLYPH_HEIGHT} px.

Greedy decoding is the right decoder for this task: the answers are random strings, so a
language model has nothing to exploit and can only steer the decoder towards a more frequent
but wrong string.

## How to use it

```python
import torch
from transformers import AutoModel, AutoProcessor
from PIL import Image

model = AutoModel.from_pretrained("{REPO_ID}", trust_remote_code=True).eval()
processor = AutoProcessor.from_pretrained("{REPO_ID}", trust_remote_code=True)

image = Image.open("captcha.png")
# roi = [x, y, w, h] — полоса с ответом. Её берут из labels.jsonl или из константы плагина.
inputs = processor(images=image, roi=[4, 36, 107, 46], text="AB3D", return_tensors="pt")
with torch.no_grad():
    logits = model(**inputs).logits
text, confidence = model.greedy_decode(logits)[0]
print(text, confidence)
```

`text=` is the **expected answer**; it is used only to widen the input until the CTC
constraint `T >= 2L + 1` holds (the same thing the training pipeline does) and never reaches
the model. If the answer is unknown, pass `label_lengths=` instead.

**The band is the whole game.** On the captcha types that are scenes (a chat log, an
inventory window) the answer is one line among several; feeding the model the whole frame
makes it read the wrong line. The measured difference between "band" and "whole frame" on
this dataset is an order of magnitude.

## Measured results

{RESULTS_BLOCK}

{RESULTS_WARNING}

## Training data

* Types used for training: {N_TRAIN_TYPES}; samples: {N_TRAIN_SAMPLES}.
* Dataset: {DATASET_REPO} — the dataset card there lists the provenance and the licence of
  every type.
* The data is **synthetic**: every image was rendered by this project's own generators.
  The renders are faithful to the upstream algorithms, but the pixels are not a screenshot
  of a live server.

## Limitations

* **Only the text band is read.** The model is not a solver: it does not reverse strings,
  does not turn Russian number words into digits and does not compute arithmetic.
* **The charset is fixed.** Characters outside `{CHARSET}` are out of scope.
* **No confidence calibration.** The reported confidence is the geometric mean of the
  emission posteriors of the frames that produced a character — a ranking score, not a
  probability.
* **Generalisation is the hard part.** A recogniser trained on a handful of plugin styles can
  memorise the style instead of learning the characters; the type-held-out numbers in
  "Measured results" are the ones that mean anything.

## Reproducing

The generator, the training code and the export script live in the **CaptchaOCR** repository.
The published weights come from the checkpoint `{CHECKPOINT}`.

## Licence

* **The weights, the code and this card:** MIT.
* **The dataset is not MIT** — it is split by the licence of the upstream plugin. See the
  dataset card.
