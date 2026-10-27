"""The model card and the licence that are written into the exported repository.

The card is a plain string with `{placeholders}`; `hf_export.card` fills them in
with the measured numbers of the run.
"""

MODEL_CARD_TEMPLATE = """---
{{
  "tags": ["captcha", "ocr", "crnn", "ctc", "minecraft"],
  "license": "mit",
  "library_name": "transformers",
  "pipeline_tag": "image-text-to-text"
}}
---

# {title}

{intro}

## What it does

The model is a **CRNN (CNN + BiLSTM) with a CTC head**, trained from scratch on
pixel-faithful re-implementations of the captchas that open-source Minecraft anti-bot
plugins draw. It reads **one string out of a captcha text band** and nothing else.

* input: a grayscale text band, scaled so the **glyph** is {glyph_height} px tall,
  normalised with `(x / 255 - 0.5) / 0.5`, right-padded;
* output: the CTC logits, decoded greedily;
* classes: {num_classes} ({num_chars} characters plus the blank).

Greedy decoding is the right decoder here: the answers are random strings, so a language
model has nothing to exploit and can only steer the decoder towards a more frequent but
wrong string.

## Intended use

* reading the code out of a **text** captcha of a known plugin, where the plugin's
  layout is known and the text band can be located;
* as the OCR half of a **solver** that also does the per-type post-processing (reverse
  the string, turn Russian number words into digits, compute an arithmetic expression);
* as a research baseline for captcha recognition on Minecraft anti-bot plugins.

## Limitations - read this before using it

* **The recogniser only reads the text band.** 29 of the 46 dataset types are *scenes*:
  a Minecraft chat log, an inventory window, an anvil dialog, in which the answer is one
  line among several. The model is given the band, never the frame. Feed it a whole
  scene and it will read the wrong line.
* **The puzzle, colour and object captchas are not OCR tasks and are not covered by
  this model.** The framed ("puzzle") captchas put the answer in turned tiles, the
  object-swatch captcha has no text at all and the answer is a colour name, the
  GUI/action captchas need grounding, and the arithmetic captchas need arithmetic. They
  are a different task and a different model.
* **The charset is {num_chars} characters** (`0-9A-Za-z`). Anything outside it - Cyrillic,
  punctuation - is out of scope. The Russian number-word family is a *Cyrillic* model
  plus a 40-line lexicon, not this one.
* **No confidence calibration.** The reported confidence is the geometric mean of the
  emission posteriors of the frames that produced a character. It is a ranking score,
  not a probability, and it is not calibrated.
* **The training data is synthetic.** Every image was rendered by this project's own
  generators, not photographed from a live server. The renders are faithful to the
  upstream algorithms, but the pixels are not a screenshot of a real session.
* **The licence of the data is not the licence of the weights.** The weights are MIT;
  the dataset is split by the licence of the upstream plugin. See "Training data".

## Training data

{training_data}

## Evaluation

{evaluation}

## How to use it

```python
import torch
from transformers import AutoModel, AutoProcessor

model = AutoModel.from_pretrained("{repo_id}", trust_remote_code=True).eval()
processor = AutoProcessor.from_pretrained("{repo_id}", trust_remote_code=True)

# `roi` is the text band: [x, y, w, h]. It comes from the caller - from the `roi`
# field of the dataset's labels.jsonl, or from a per-plugin constant.
from PIL import Image

image = Image.open("captcha.png")
inputs = processor(images=image, roi=[4, 36, 107, 46], text="AB3D", return_tensors="pt")
with torch.no_grad():
    logits = model(**inputs).logits
text, confidence = model.greedy_decode(logits)[0]
print(text, confidence)
```

`text=` is the **expected answer** and is used only to widen the input until the CTC
constraint `T >= 2L + 1` holds, exactly as the training pipeline does. It never reaches
the model. If the answer is not known, pass `label_lengths=` instead, or nothing at all
- the model still runs, on a slightly different width than it was trained on.

`AutoModel` + `AutoProcessor` is the supported load path. `AutoModelForImageTextToText`
is **not** mapped: transformers 5.x removed the `image-to-text` pipeline, and the
`image-text-to-text` pipeline needs the image inside the chat content, which is a
different interface from this model.

## The ONNX export

`onnx/model.onnx` is the same weights as a plain ONNX graph:

* input `pixel_values`: `(batch, 1, {glyph_height}, width)`, float32, normalised;
* output `logits`: `(batch, width // 4, {num_classes})`.

It needs **no torch and no `trust_remote_code`** - only `onnxruntime` and a NumPy/Pillow
preprocessing step. The graph was exported with `torch.onnx.export`; `optimum` is not
used, and cannot be: `transformers.onnx` was removed in transformers 5.x and
`optimum-onnx` 0.1.0 declares `transformers<4.58.0,>=4.36`, so the two cannot coexist.

The preprocessing for the ONNX path is the same as the processor's, and it is short
enough to inline (this is the whole thing, and it is what the processor does):

```python
import numpy as np, onnxruntime as ort
from PIL import Image

def band_to_tensor(path, roi=None, glyph_height={glyph_height}, label_length=None):
    img = Image.open(path)
    if img.mode != "L":
        img = img.convert("L")
    if roi:
        x, y, w, h = roi
        x, y = max(0, min(x, img.width - 1)), max(0, min(y, img.height - 1))
        w, h = max(1, min(w, img.width - x)), max(1, min(h, img.height - y))
        img = img.crop((x, y, x + w, y + h))
    a = np.asarray(img, dtype=np.float32)
    busy = a.std(axis=1) > 6.0
    runs, start = [], None
    for i, b in enumerate(busy):
        if b and start is None:
            start = i
        elif not b and start is not None:
            runs.append(i - start); start = None
    if start is not None:
        runs.append(len(busy) - start)
    runs = [r for r in runs if r >= 2]
    line = max(1, int(np.median(runs))) if runs else img.height
    w = max(64, int(round(img.width * glyph_height / max(1, line))))
    if label_length:
        w = max(w, 4 * (2 * label_length + 1))
    w = min(400, w)
    img = img.resize((w, glyph_height), Image.BILINEAR)
    a = (np.asarray(img, dtype=np.float32) / 255.0 - 0.5) / 0.5
    return a[None, None].astype(np.float32)

sess = ort.InferenceSession("onnx/model.onnx", providers=["CPUExecutionProvider"])
x = band_to_tensor("captcha.png", roi=[4, 36, 107, 46], label_length=4)
logits = sess.run(None, {{"pixel_values": x}})[0]
ids = logits[0].argmax(axis=-1)
text = "".join(ch for k, ch in zip(ids, "{charset}") if k != 0 and k != ids[0])
```

(The last line is a simplification: the real greedy CTC decode collapses repeats, so
use `model.greedy_decode` for the PyTorch path and the same rule for the ONNX path.)

## Reproducing

The training code, the dataset generator and the export script live in the
**CaptchaOCR** repository. The export is one command:

```powershell
.venv-gpu\\Scripts\\python.exe train\\export_hf.py --checkpoint train\\run\\ckpt\\step_*.pt --out <dir> --charset latin
```

The export script verifies itself before it writes the card: it loads the checkpoint
back, runs the training code and the exported code on the same images and compares the
decoded strings, re-loads the repository in a fresh process through `AutoModel` /
`AutoProcessor`, and runs the ONNX through `onnxruntime`. All three must agree.

### Environment

| | |
|---|---|
| Python | {python_version} |
| torch | {torch_version} |
| transformers | {transformers_version} (4.57 also supported, see below) |
| onnxruntime | {onnxruntime_version} |

`transformers` **4.57** and **5.x** are both supported: the config, the model and the
processor avoid every API that changed between them, and the processor is a single
`ProcessorMixin` with no sub-processor, which is what transformers 5.x requires.

## Licence

* **the weights, the code and the model card: MIT** (see `LICENSE`).
* **the dataset is not MIT.** It is published per licence family, because the upstream
  plugins do not share one licence. See `reports/HF_RELEASE.md` in the CaptchaOCR
  repository for the split, and the dataset repositories for the per-row provenance.
* A user of the **dataset** must comply with the licence of the plugin the row came
  from. A user of the **weights** only has to comply with MIT.
"""


MIT_LICENSE = """MIT License

Copyright (c) 2026 CaptchaOCR contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
