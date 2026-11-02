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

<img src="https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/resolve/main/assets/model_hero.png" alt="A haq/mapcha/map captcha frame, the answer band cropped from it by roi, and the string the model decodes from that band: ly8r" width="100%">

![base](https://img.shields.io/badge/base-PP--OCRv6_medium_rec-0b5cad) ![params](https://img.shields.io/badge/params-19.2M-informational) ![classes](https://img.shields.io/badge/CTC_classes-18%2C762-blueviolet) ![median](https://img.shields.io/badge/median_exact-88.75%25-brightgreen) ![cer](https://img.shields.io/badge/median_CER-3.44%25-green) ![heldout](https://img.shields.io/badge/held--out_plugins-6-yellow) ![license](https://img.shields.io/badge/license-Apache--2.0-blue) ![task](https://img.shields.io/badge/task-image--to--text-success)

# CaptchaOCR PP-OCRv6 — captcha text recogniser

A PP-OCRv6 fine-tune that reads a captcha image, usually the answer band: 18 evaluated styles,
Latin letters, digits, and part of the Cyrillic alphabet.

## Use it in 10 lines

```python
import torch
from PIL import Image
from transformers import PPOCRV6SmallRecForTextRecognition
from transformers import PPOCRV6SmallRecImageProcessor

REPO = "Titlehhhh/captchaocr-ppocrv6"
model = PPOCRV6SmallRecForTextRecognition.from_pretrained(REPO).eval()
proc = PPOCRV6SmallRecImageProcessor.from_pretrained(REPO)
inputs = proc(images=[Image.open("band.png").convert("RGB")], return_tensors="pt")
with torch.no_grad():
    logits = model(**inputs)
print(proc.post_process_text_recognition(logits))  # [{'text': 'ly8r', 'score': 0.96}]
```

`band.png` is a tight crop of the answer band, not a screenshot. The processor resizes it to
48 × 320, normalises it, and decodes CTC with the 18 762-entry dictionary from
`preprocessor_config.json`. This exact snippet was run against these weights.

<details>
<summary>Manual CTC decoding</summary>

If you would rather decode by hand, the forward returns the logits in `last_hidden_state`:

```python
with open("character_list.txt", encoding="utf-8") as f:
    dictionary = [line.rstrip("\r\n") for line in f]   # rstrip, not strip: " " is a class
ids = logits.last_hidden_state.argmax(-1)[0].tolist()
text, prev = [], -1
for i in ids:
    if i != prev and i != 0:        # collapse repeats, drop the blank
        text.append(dictionary[i])
    prev = i
print("".join(text))
```
</details>

## What it supports

| Supports | Does not support |
|---|---|
| **18 evaluated styles**: 11 from the published dataset snapshot, 1 unpublished (`LimboFilter/digits`), 6 held-out plugins | **3 types that draw a number as a word** while the answer is digits: `ru-numberword`, `ru-numberword-caption`, `LimboFilter/map`. Those need a solver step, not OCR |
| Latin letters, digits, and 52 of 66 Cyrillic letters: all 33 uppercase, 19 lowercase | 14 lowercase Cyrillic letters are not classes: б, г, ё, ж, з, й, л, у, ф, х, щ, ъ, э, ю. Characters outside `character_list.txt` are never produced |
| A tight crop of the answer band (`roi` in the dataset), noisy bands with lines, per-character shifts, coloured backgrounds | A whole game screenshot without a cropper: 2 of 6 screenshots read correctly as-is, 6 of 6 with the project's cropper |
| Styles close to the trained plugins, including other plugins of the same visual family | A style absent from training: expect 0.57–0.98 exact, never 1.0 |

## Results

Exact match and CER after greedy CTC decoding, on 11 400 images of 18 styles: 200 rows per trained
style plus 1 500 rows per held-out plugin. The median is taken over the 18 per-style scores; the
micro average counts every image, and 9 000 of the 11 400 belong to held-out plugins.

| Metric | Score |
|---|---:|
| median exact match (18 styles) | **0.8875** |
| median CER | **0.0344** |
| micro exact match (11 400 images) | **0.7797** |
| micro CER | **0.0755** |

**Plugins never seen in training** — what to expect on a new style:

| Plugin | Style | Exact | CER |
|---|---|---:|---:|
| CaptchaVerifyZ | map | 0.9780 | 0.0045 |
| Minecaptcha | map | 0.9373 | 0.0162 |
| BotFilter | map | 0.8140 | 0.0508 |
| sonar | legacy | 0.7693 | 0.0793 |
| sonar | complex | 0.6253 | 0.1293 |
| sonar | standard | 0.5707 | 0.1671 |

<details>
<summary>Per-style results on the trained styles</summary>

Sample-level hold-out: the first 200 rows of each style were taken out of training.

| Style | Exact | CER |
|---|---:|---:|
| `Archy-X/Krypton/map` | 1.0000 | 0.0000 |
| `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | 1.0000 | 0.0000 |
| `irootdev/AnBot/captcha` | 0.9950 | 0.0017 |
| `haq/mapcha/map` | 0.9550 | 0.0112 |
| `GalleryCaptcha/ru-web` | 0.9250 | 0.0150 |
| `just-captcha/ProstoCaptcha/map` | 0.9150 | 0.0150 |
| `LimboFilter/digits` (unpublished) | 0.8900 | 0.0288 |
| `GalleryCaptcha/ru-symbols` | 0.8850 | 0.0400 |
| `LimboFilter/symbols` | 0.8000 | 0.0783 |
| `LagBug/XProtect/code` | 0.3600 | 0.1542 |
| `LagBug/XProtect/map` | 0.2700 | 0.1850 |
| `InstantlyMoist/Captcha/textcaptcha` | 0.2400 | 0.4220 |

</details>

## Limitations

* **Four of the twelve trained styles are fed the whole frame**, not a band. Three of them are the
  weakest: `XProtect/code` 0.36, `XProtect/map` 0.27, `textcaptcha` 0.24. The fourth,
  `AnBot/captcha`, scores 0.9950 on the frame — the input is not what makes a style hard.
* **The median is carried by the easy styles.** Seven of the twelve trained styles score 0.89 or
  better. On a style unlike the training set, read the held-out table instead: 0.57–0.98.
* **Screenshots need a cropper.** Feed a raw game frame and 2 of 6 real screenshots are read
  correctly; with the cropper, 6 of 6. The cropper ships with the code, not with these weights.
* **The micro average is mostly held-out data** (9 000 of 11 400 images), so it answers "how does
  it do on unseen plugins", not "accuracy in general".
* **It is not an API and not a solver for new plugins.** One image in, one string out; a style
  absent from training has no guarantee.

## Dataset

[`Titlehhhh/captchaocr-dataset`](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset) is
synthetic: every image is a re-render by this project's Java generators of a captcha drawn by an
open-source Minecraft plugin. The published snapshot holds 20 styles and 200 000 samples. A 21st
style, `out_ru/LimboFilter/digits`, was generated after the export and is not in the snapshot —
which is why 18 evaluated styles = 11 from the snapshot + 1 unpublished + 6 held out.

<details>
<summary>Training</summary>

* Base: `PP-OCRv6_medium_rec` (Apache-2.0). The CTC head was kept and grown from 18 710 to
  18 762 classes: rows 18 710–18 761 are 52 appended Cyrillic characters.
* Initialised from an earlier Cyrillic run of the same recipe that replayed Latin data, then
  fine-tuned on 12 styles.
* 5 epochs × 488 steps = 2 440 steps, batch 32, learning rate 8e-6 for backbone and head,
  weight decay 0.01, gradient clipping 1.0.
* 15 594 training examples: 1 300 per style after a 200-row hold-out, from a 10 000-per-style
  render (the run used `--limit-per-type 1500`).
* 33.9 min on one GTX 1080 Ti, 108 images/s, fp16.
* Whole-frame styles were trained with the frame as input; the rest with the `roi` band.
* Full command line and scripts:
  [github.com/Titlehhhh/CaptchaOCR](https://github.com/Titlehhhh/CaptchaOCR).

</details>

## License & citation

The weights are **Apache-2.0**, as a derivative of `PP-OCRv6_medium_rec`. The training data is
published under **mixed per-plugin licences** — some rows are non-commercial, so read the dataset
[LICENSE](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/blob/main/LICENSE) before
commercial use.

<details>
<summary>Version history</summary>

* `universal_v1` (2026-10-27) — current weights, 18 762 classes, no weight interpolation (α = 1.0).
  It replaced `all20`, which is no longer downloadable.
* Interpolation is off on purpose: pulling back towards the base damages the appended rows
  (`LimboFilter/symbols` 0.765 → 0.016). Replay of old data, not a weight soup, is what keeps them.

</details>
