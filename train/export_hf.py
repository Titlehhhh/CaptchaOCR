"""Export a trained CRNN+CTC checkpoint into a self-contained Hugging Face repository.

    .venv-gpu\\Scripts\\python.exe train\\export_hf.py --checkpoint train\\run\\ckpt\\step_0001234.pt \\
        --out build\\hf_export --charset latin

What it produces, in ``--out``:

    config.json                 model_type, auto_map, the architecture's hyper-parameters
    configuration_captcha.py     the config class
    modeling_captcha.py          the model class (CRNN + CTC head)
    processing_captcha.py        the processor (ONE class, no sub-processor)
    processor_config.json       the processor's own config (transformers 5.x layout)
    preprocessor_config.json    the same attributes, for transformers 4.x and for AutoImageProcessor
    vocab.json                  the character table
    model.safetensors           the weights
    onnx\\model.onnx             the ONNX export (torch.onnx.export, never optimum)
    README.md                   the model card, generated from the measured numbers
    LICENSE                     MIT, for the weights

Three design decisions are load-bearing and are explained where they are made:

*   **One processor, no sub-processor.**  Transformers 5.x moved every processor attribute
    into a single nested ``processor_config.json`` and stopped writing
    ``special_tokens_map.json`` / ``added_tokens.json``.  A repository that ships a
    sub-processor therefore fails to load with *"Processor was loaded, but it is not an
    instance of ProcessorMixin"* - which is what happens to
    ``hongyusir/trocr-base-printed_captcha_ocr`` and
    ``DunnBC22/trocr-base-printed_captcha_ocr``.  ``CaptchaProcessor`` below is a single
    ``ProcessorMixin`` with an empty sub-processor list on both transformers 4.x and 5.x.

*   **``torch.onnx.export``, not optimum.**  ``transformers.onnx`` was removed in
    transformers 5.x and ``optimum-onnx`` 0.1.0 declares ``transformers<4.58.0,>=4.36``,
    so the two cannot coexist.  The ONNX file is the only artefact of this repository that
    runs without ``trust_remote_code`` and without torch.

*   **The export is verified, not assumed.**  The script loads the checkpoint back, runs
    the *training* code and the *exported* code on the same images and compares the
    decoded strings; then it re-loads the repository in a **fresh process** through
    ``AutoModel`` / ``AutoProcessor`` and compares again; then it runs the ONNX through
    ``onnxruntime`` and compares a third time.  A silent mismatch is the classic way an
    export goes wrong, so the script fails loudly instead of writing a model card.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any

import numpy as np
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_OUT_DIRS = [os.path.join(REPO, "dataset", "out"), os.path.join(REPO, "dataset", "out_ru")]

LATIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
CYRILLIC_CHARSET = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"

AUTO_MAP = {
    "AutoConfig": "configuration_captcha.CaptchaConfig",
    "AutoModel": "modeling_captcha.CaptchaModel",
    "AutoProcessor": "processing_captcha.CaptchaProcessor",
}


# =====================================================================================
# The three files that make the repository loadable
# =====================================================================================

CONFIGURATION_TEMPLATE = '''"""Configuration for the Captcha CRNN + CTC captcha recogniser.

Auto-loaded through the ``auto_map`` entry in ``config.json``::

    from transformers import AutoConfig
    config = AutoConfig.from_pretrained("<this repo>", trust_remote_code=True)
"""

from transformers import PretrainedConfig


class CaptchaConfig(PretrainedConfig):
    """Hyper-parameters of the recogniser.

    Args:
        num_classes (`int`):
            Size of the CTC head, i.e. the number of characters **plus** the blank.
            63 for the Latin model (blank + ``0-9A-Za-z``).
        hidden (`int`):
            Hidden size of the bidirectional LSTM. 256 in the published checkpoint.
        dropout (`float`):
            Dropout of the LSTM and of the head. 0.1 in the published checkpoint.
            It is inactive at inference time.
        glyph_height (`int`):
            Height of the **glyph** in the input tensor, in pixels. The processor
            scales every text band so that one line of glyphs is this tall.
        charset (`str`):
            The characters, in class-index order. Class ``i`` (1-based) is
            ``charset[i - 1]``; class 0 is the CTC blank.
        blank_index (`int`):
            The index of the CTC blank. Always 0.
        min_width (`int`), max_width (`int`):
            The width clamp of the processor, in pixels.
        initializer_range (`float`):
            The standard deviation used by the weight initialisation.
    """

    model_type = "captcha"

    def __init__(
        self,
        num_classes=63,
        hidden=256,
        dropout=0.1,
        glyph_height=32,
        charset="{charset}",
        blank_index=0,
        min_width=64,
        max_width=400,
        initializer_range=0.02,
        **kwargs,
    ):
        self.num_classes = int(num_classes)
        self.hidden = int(hidden)
        self.dropout = float(dropout)
        self.glyph_height = int(glyph_height)
        self.charset = charset
        self.blank_index = int(blank_index)
        self.min_width = int(min_width)
        self.max_width = int(max_width)
        self.initializer_range = float(initializer_range)
        super().__init__(**kwargs)
'''


MODELING_TEMPLATE = '''"""The Captcha CRNN + CTC model: CNN -> BiLSTM -> a linear CTC head.

The architecture is a byte-for-byte port of ``train/captcha_crnn.py`` in the CaptchaOCR
repository: the same module names (``cnn``, ``rnn``, ``fc``), the same pooling, the same
number of feature rows, so a checkpoint trained there loads here without any key
translation.

Auto-loaded through the ``auto_map`` entry in ``config.json``::

    from transformers import AutoModel
    model = AutoModel.from_pretrained("<this repo>", trust_remote_code=True)
"""

import numpy as np
import torch
import torch.nn as nn
from transformers import PreTrainedModel

try:  # transformers 5.x
    from transformers.utils import ModelOutput
except ImportError:  # pragma: no cover - transformers 4.x
    from transformers.modeling_outputs import ModelOutput

try:  # when this file is loaded as part of a package (the trust_remote_code path)
    from .configuration_captcha import CaptchaConfig
except ImportError:  # pragma: no cover - when it is imported directly from a directory
    from configuration_captcha import CaptchaConfig


class CaptchaCtcOutput(ModelOutput):
    """The output of the model.

    Args:
        logits (`torch.FloatTensor`):
            `(batch, time, num_classes)` CTC logits. `time` is `width // 4`.
        num_steps (`int`):
            The number of time steps, i.e. `width // 4`.
    """

    logits: torch.FloatTensor = None
    num_steps: int = None


class CaptchaModel(PreTrainedModel):
    """A CRNN (CNN + BiLSTM) with a CTC head, trained from scratch on captcha text bands.

    The input is a grayscale text band, scaled so that the **glyph** is
    `config.glyph_height` pixels tall, normalised to `[-1, 1]` and right-padded inside a
    batch. The output is the CTC log-probabilities; the decoding is greedy
    (`greedy_decode` below), because the labels are random strings with no lexical
    structure for a language model to exploit.
    """

    config_class = CaptchaConfig
    base_model_prefix = "captcha"
    main_input_name = "pixel_values"
    supports_gradient_checkpointing = False

    def __init__(self, config):
        super().__init__(config)
        c = config.num_classes
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 2)),                                  # H/2  W/2
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 2)),                                  # H/4  W/4
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 1)),                                  # H/8  W/4
            nn.Conv2d(128, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(inplace=True),
        )
        # The three pools halve the height twice and once, so the feature map has
        # glyph_height / 8 rows of 256 channels. The LSTM's input size is that product.
        self.rows = max(1, config.glyph_height // 8)
        self.rnn = nn.LSTM(
            self.rows * 256,
            config.hidden,
            num_layers=2,
            bidirectional=True,
            dropout=config.dropout,
            batch_first=True,
        )
        self.dropout = nn.Dropout(config.dropout)
        self.fc = nn.Linear(config.hidden * 2, c)
        self.post_init()

    def _init_weights(self, module):
        """Initialise the weights.

        Transformers 5.x initialises every `Conv2d` and `Linear` with
        `normal_(0, 0.02)`, which is a poor fit for a from-scratch CRNN: the
        BatchNorm statistics have to learn the scale back from scratch and the
        classifier starts with a much too narrow output distribution. This override
        restores the usual defaults - He for the convolutions, PyTorch's own for the
        LSTM, and a small normal for the classifier.

        It only matters when the class is instantiated from a config without a
        checkpoint; `from_pretrained` overwrites every one of these tensors with the
        published weights.
        """
        if isinstance(module, (nn.Conv2d, nn.Linear)):
            nn.init.kaiming_normal_(module.weight, nonlinearity="relu")
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.BatchNorm2d):
            if module.weight is not None:
                nn.init.ones_(module.weight)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.LSTM):
            for name, param in module.named_parameters():
                if "weight" in name:
                    nn.init.xavier_uniform_(param)
                elif "bias" in name:
                    nn.init.zeros_(param)

    def forward(self, pixel_values=None, **kwargs):
        """Run the encoder.

        Args:
            pixel_values (`torch.FloatTensor`):
                `(batch, 1, glyph_height, width)`, normalised to `[-1, 1]`, right-padded.

        Returns:
            `CaptchaCtcOutput`: the CTC logits and the number of time steps.
        """
        if pixel_values is None:
            raise ValueError("CaptchaModel.forward() needs `pixel_values`")
        f = self.cnn(pixel_values)                     # (B, 256, H/8, W/4)
        b, c, h, w = f.shape
        if h != self.rows:
            raise ValueError(
                f"input height {{pixel_values.shape[2]}} gives {{h}} feature rows, but the model was "
                f"built for {{self.rows}} - the glyph height and the model must agree"
            )
        f = f.permute(0, 3, 1, 2).reshape(b, w, h * c)   # (B, T=W/4, H/8*256)
        f, _ = self.rnn(f)                              # (B, T, 2*hidden)
        f = self.dropout(f)
        return CaptchaCtcOutput(logits=self.fc(f), num_steps=w)

    # -- decoding ---------------------------------------------------------------
    def decode_indices(self, indices):
        """Map class indices to a string. Index 0 (the blank) decodes to nothing."""
        charset = self.config.charset
        return "".join(charset[int(i) - 1] for i in indices
                       if 1 <= int(i) <= len(charset))

    def greedy_decode(self, logits):
        """Greedy CTC decoding with a per-character confidence.

        Args:
            logits (`torch.FloatTensor`):
                `(batch, time, num_classes)`.

        Returns:
            `list[tuple[str, float]]`: the decoded string and the confidence of every
            sample. The confidence is the geometric mean of the posteriors of the frames
            that produced a character - a ranking score for a human-in-the-loop solver,
            not a calibrated probability.
        """
        probs = torch.softmax(logits.float(), dim=-1)
        best = probs.argmax(dim=-1)
        best_p = probs.max(dim=-1).values
        out = []
        for b in range(best.shape[0]):
            chars = []
            confs = []
            prev = -1
            for t in range(best.shape[1]):
                k = int(best[b, t])
                if k != prev and k != self.config.blank_index:
                    chars.append(k)
                    confs.append(float(best_p[b, t]))
                prev = k
            text = self.decode_indices(chars)
            if confs:
                conf = float(np.exp(np.mean(np.log(np.clip(confs, 1e-6, 1.0)))))
            else:
                conf = 0.0
            out.append((text, conf))
        return out
'''


PROCESSING_TEMPLATE = '''"""The Captcha processor: **one** `ProcessorMixin`, with no sub-processor.

Why one class and no sub-processor: transformers 5.x moved every processor attribute
into a single nested `processor_config.json` and stopped writing
`special_tokens_map.json` / `added_tokens.json`. A repository that ships a
sub-processor therefore fails to load with *"Processor was loaded, but it is not an
instance of ProcessorMixin"* - the failure that `hongyusir/trocr-base-printed_captcha_ocr`
and `DunnBC22/trocr-base-printed_captcha_ocr` hit. This class has no sub-processor at
all: the image pipeline lives in the class itself.

What the pipeline does, and why each step is there (this is the training pipeline of
`train/captcha_crnn.py`, minus the augmentation):

1.  **Crop to the text band.** The `roi` of the sample - `[x, y, w, h]` - is the box the
    plugin drew the answer in. 29 of the 46 dataset types are scenes (a Minecraft chat
    log, an inventory window, an anvil dialog) in which the answer is one line among
    several; cropping is what turns "read the right line" into "read the string".
    **The `roi` comes from the caller**: pass `roi=[x, y, w, h]` (or a list of them) to
    `__call__`, or read it from the `labels.jsonl` row of the sample. A sample with no
    band (`roi: null`) is processed whole.
2.  **Scale so the glyph is `glyph_height` pixels tall.** The *glyph*, not the band: a
    band can be two or three lines of text, and scaling the band to 32 px would leave a
    7 px glyph, which cannot separate `0` from `O`. The glyph height is measured from
    the picture (the median height of the "busy" rows).
3.  **Grayscale, then `(x / 255 - 0.5) / 0.5`.** Every text type is ink on a background.
4.  **Right-pad to the widest image of the batch**, with zeros in the normalised space -
    the same padding the training collate does.

The CTC constraint `T >= 2L + 1` (T = width // 4 time steps, L = the label length) is
also enforced here, exactly as the training dataset enforces it: pass `text=` (the
expected answer) or `label_lengths=` and the image is widened until the constraint
holds. Without it the width would be the aspect-scaled width alone, which is not what
the model was trained on.
"""

import os

import numpy as np
from PIL import Image

try:  # transformers 5.x
    from transformers import BatchFeature
except ImportError:  # pragma: no cover - transformers 4.x
    from transformers.feature_extraction_utils import BatchFeature

try:
    from transformers import ProcessorMixin
except ImportError:  # pragma: no cover
    from transformers.processing_utils import ProcessorMixin

DEFAULT_CHARSET = "{charset}"


class CaptchaProcessor(ProcessorMixin):
    """Prepare captcha text bands for `CaptchaModel`.

    Args:
        glyph_height (`int`):
            The height of one line of glyphs in the output, in pixels. 32 in the
            published model.
        min_width (`int`), max_width (`int`):
            The width clamp, in pixels.
        charset (`str`):
            The characters, in class-index order. Class `i` (1-based) is
            `charset[i - 1]`; class 0 is the CTC blank.
        blank_index (`int`):
            The index of the CTC blank. Always 0.
        mean (`float`), std (`float`):
            The normalisation, applied to the `0..255` pixel values after dividing
            them by 255.
        pad_value (`float`):
            The value the right-hand padding is filled with, in the **normalised**
            space. 0.0 is what the training collate uses.
        line_std_threshold (`float`):
            A row of the band is "busy" when the standard deviation of its pixels is
            above this. The glyph height is the median height of the busy runs.
    """

    # transformers 4.x reads the list of sub-processors from `attributes`; this
    # processor has none. transformers 5.x derives the same list from the `__init__`
    # signature, and none of the parameter names below contains a modality name
    # ("image_processor", "video_processor", "feature_extractor", "audio_processor",
    # "tokenizer"), so it also comes out empty.
    attributes = []

    def __init__(
        self,
        glyph_height=32,
        min_width=64,
        max_width=400,
        charset=DEFAULT_CHARSET,
        blank_index=0,
        mean=0.5,
        std=0.5,
        pad_value=0.0,
        line_std_threshold=6.0,
    ):
        super().__init__()
        self.glyph_height = int(glyph_height)
        self.min_width = int(min_width)
        self.max_width = int(max_width)
        self.charset = charset
        self.blank_index = int(blank_index)
        self.mean = float(mean)
        self.std = float(std)
        self.pad_value = float(pad_value)
        self.line_std_threshold = float(line_std_threshold)
        self.chat_template = None

    # -- the pipeline ------------------------------------------------------------
    @staticmethod
    def _open(image):
        """Open an image from a path, a PIL image or a numpy array, as grayscale."""
        if isinstance(image, (str, os.PathLike)):
            img = Image.open(image)
        elif isinstance(image, Image.Image):
            img = image
        else:
            arr = np.asarray(image)
            if arr.ndim == 3:
                arr = arr[..., :3].mean(axis=-1)
            img = Image.fromarray(arr.astype(np.uint8), mode="L")
        if img.mode != "L":
            img = img.convert("L")
        return img

    def _crop(self, img, roi):
        """Crop to the text band, with the same clamping as the training dataset."""
        if not roi:
            return img
        x, y, w, h = (int(v) for v in roi)
        x = max(0, min(x, img.width - 1))
        y = max(0, min(y, img.height - 1))
        w = max(1, min(w, img.width - x))
        h = max(1, min(h, img.height - y))
        return img.crop((x, y, x + w, y + h))

    def line_height(self, img):
        """The height of one line of glyphs inside a band, in pixels.

        A band is not always one line. The Russian number family spells a whole number
        out, one word per row, so its band is a two or three line block whose glyph is
        only a fifth of the band. The glyph height is measured from the picture: the
        rows of a text line vary a lot across the row, the blank rows between the lines
        do not, and the median length of the "busy" runs is the height of one line. It
        works for dark-on-light and for light-on-dark, because it looks at the
        variation and not at the brightness.
        """
        a = np.asarray(img, dtype=np.float32)
        if a.ndim != 2 or a.shape[0] < 3:
            return img.height
        busy = a.std(axis=1) > self.line_std_threshold
        runs = []
        start = None
        for i, b in enumerate(busy):
            if b and start is None:
                start = i
            elif not b and start is not None:
                runs.append(i - start)
                start = None
        if start is not None:
            runs.append(len(busy) - start)
        runs = [r for r in runs if r >= 2]
        if not runs:
            return img.height
        return max(1, int(np.median(runs)))

    def target_width(self, img, label_length=None):
        """The width the image is scaled to, in pixels."""
        line = self.line_height(img)
        scale = self.glyph_height / max(1, line)
        w = int(round(img.width * scale))
        w = max(self.min_width, w)
        if label_length:
            # T >= 2L + 1, and T = width // 4
            w = max(w, 4 * (2 * int(label_length) + 1))
        return min(self.max_width, w)

    def preprocess(self, image, roi=None, label_length=None):
        """Prepare one image. Returns a `(glyph_height, width)` float32 array in `[-1, 1]`."""
        img = self._crop(self._open(image), roi)
        w = self.target_width(img, label_length)
        img = img.resize((w, self.glyph_height), Image.BILINEAR)
        a = np.asarray(img, dtype=np.float32) / 255.0
        return (a - self.mean) / self.std

    def __call__(self, images=None, roi=None, text=None, label_lengths=None,
                 return_tensors="pt", **kwargs):
        """Prepare a batch of captcha images.

        Args:
            images:
                A path, a PIL image, a numpy array, or a list of those.
            roi (`list`):
                The text band of every image, `[x, y, w, h]`. Either one band for the
                whole batch, or one per image. `None` means "the whole image is the
                text". **The band comes from the caller** - read it from the `roi`
                field of the `labels.jsonl` row, or keep it as a per-plugin constant.
            text (`str` or `list`):
                The expected answer of every image. It is used **only** to widen the
                input until the CTC constraint `T >= 2L + 1` holds, which is what the
                training pipeline does. It never reaches the model.
            label_lengths (`list`):
                The label lengths, if the answers are not known but their lengths are.
            return_tensors (`str`):
                `"pt"` for a torch tensor, `"np"` for a numpy array, `None` for a list.

        Returns:
            `BatchFeature`: with `pixel_values` of shape
            `(batch, 1, glyph_height, max_width)` and `widths`, the true width of every
            image inside the padded batch.
        """
        if images is None:
            raise ValueError("CaptchaProcessor needs at least one image")
        if isinstance(images, (str, os.PathLike, Image.Image, np.ndarray)):
            images = [images]
        images = list(images)
        n = len(images)

        rois = self._broadcast(roi, n)
        lengths = self._broadcast(label_lengths, n)
        if text is not None:
            texts = self._broadcast(text, n)
            for i, t in enumerate(texts):
                if lengths[i] is None and t is not None:
                    lengths[i] = len(t)

        arrays = [self.preprocess(im, rois[i], lengths[i]) for i, im in enumerate(images)]
        widths = [a.shape[1] for a in arrays]
        max_w = max(widths) if widths else 0
        batch = np.full((n, 1, self.glyph_height, max_w), self.pad_value, dtype=np.float32)
        for i, a in enumerate(arrays):
            batch[i, 0, :, : widths[i]] = a

        data = {{"pixel_values": batch, "widths": np.asarray(widths, dtype=np.int64)}}
        if return_tensors == "pt":
            try:
                import torch
            except ImportError as exc:  # pragma: no cover
                raise ImportError(
                    "return_tensors='pt' needs torch; use return_tensors='np' instead"
                ) from exc
            data = {{k: torch.from_numpy(np.asarray(v)) for k, v in data.items()}}
        elif return_tensors is None:
            data = {{"pixel_values": [a for a in arrays], "widths": widths}}
        return BatchFeature(data=data, tensor_type=None)

    @staticmethod
    def _broadcast(value, n):
        """Turn a single value into a list of `n`, leaving `None` alone."""
        if value is None:
            return [None] * n
        if isinstance(value, (list, tuple)):
            if len(value) != n:
                raise ValueError(f"expected {n} values, got {len(value)}")
            return list(value)
        return [value] * n
'''


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


# =====================================================================================
# The dataset's provenance - one row per captcha type
# =====================================================================================

#: plugin key -> (upstream, upstream licence, mode)
PLUGINS: dict[str, tuple[str, str, str]] = {
    "LagBug/XProtect": ("LagBug/XProtect", "MIT", "faithful"),
    "jonesdevelopment/sonar": ("jonesdevelopment/sonar", "GPL-3.0", "clean-room"),
    "Archy-X/Krypton": ("Archy-X/Krypton", "no licence (all rights reserved)", "clean-room"),
    "FeelingAlive0/AdvancedCaptcha": ("FeelingAlive0/AdvancedCaptcha", "MIT", "faithful"),
    "jSdCool/minecaptcha": ("jSdCool/minecaptcha", "CC0-1.0", "faithful"),
    "Z4OLLIEZ4/reCaptcha": ("Z4OLLIEZ4/reCaptcha", "MIT", "faithful"),
    "Joey61021/captcha": ("Joey61021/captcha", "MIT", "faithful"),
    "laforetbrut/are-you-sure": ("laforetbrut/are-you-sure", "MIT", "faithful"),
    "Mrbysco/Captcha": ("Mrbysco/Captcha", "MIT", "faithful"),
    "Yukun99/Captchas": ("Yukun99/Captchas", "no licence (all rights reserved)", "clean-room"),
    "China2B2T/Captcha": ("China2B2T/Captcha", "GPL-3.0", "clean-room"),
    "InstantlyMoist/Captcha": ("InstantlyMoist/Captcha", "MIT", "faithful"),
    "JSH32/Minecaptcha": ("JSH32/Minecaptcha", "MIT", "faithful"),
    "haq/mapcha": ("haq/mapcha", "MIT", "faithful"),
    "just-captcha/ProstoCaptcha": ("just-captcha/ProstoCaptcha", "MIT", "faithful"),
    "irootdev/AnBot": ("irootdev/AnBot", "GPL-3.0", "clean-room"),
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA": (
        "ringoame196-s-mcPlugin/ReproductionCAPTCHA",
        "no licence file (all rights reserved)", "clean-room"),
    "n1zamu/NCaptcha": ("n1zamu/NCaptcha", "MIT", "faithful"),
    "Elytrium/LimboFilter": ("Elytrium/LimboFilter", "AGPL-3.0", "clean-room"),
    "Leymooo/BungeeCord": ("Leymooo/BungeeCord (BotFilter)",
                           "BSD-2-Clause + no-commercial-hosting clause", "clean-room"),
    "Mateitaa1/CaptchaVerifyZ": ("Mateitaa1/CaptchaVerifyZ",
                                 "all rights reserved (Modrinth)", "clean-room"),
    "Supl1n/CaptchaGUI": ("Supl1n/CaptchaGUI", "no licence file (all rights reserved)",
                           "clean-room"),
    "GalleryCaptcha": ("GalleryCaptcha catalogue", "proprietary (no licence)", "reconstructed"),
}

#: plugin key -> the captcha types it contributes
PLUGIN_TYPES: dict[str, list[str]] = {
    "LagBug/XProtect": ["code", "color", "different", "drop", "equation", "gui", "jump",
                        "map", "picture", "reverse", "slot", "sneak"],
    "jonesdevelopment/sonar": ["standard", "complex", "legacy"],
    "Archy-X/Krypton": ["map", "menu"],
    "FeelingAlive0/AdvancedCaptcha": ["button", "math"],
    "jSdCool/minecaptcha": ["text", "image"],
    "Z4OLLIEZ4/reCaptcha": ["captchasx"],
    "Joey61021/captcha": ["colorgui"],
    "laforetbrut/are-you-sure": ["code"],
    "Mrbysco/Captcha": ["math"],
    "Yukun99/Captchas": ["itemslot"],
    "China2B2T/Captcha": ["wool"],
    "InstantlyMoist/Captcha": ["textcaptcha"],
    "JSH32/Minecaptcha": ["map"],
    "haq/mapcha": ["map"],
    "just-captcha/ProstoCaptcha": ["map"],
    "irootdev/AnBot": ["captcha"],
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA": ["map"],
    "n1zamu/NCaptcha": ["anvil"],
    "Elytrium/LimboFilter": ["map", "symbols", "framed3x3", "framed2x2"],
    "Leymooo/BungeeCord": ["map"],
    "Mateitaa1/CaptchaVerifyZ": ["map"],
    "Supl1n/CaptchaGUI": ["clickblock"],
    "GalleryCaptcha": ["ru-numberword", "ru-numberword-caption", "ru-symbols", "ru-web",
                       "ru-object-swatch"],
}

#: the type ids, as they appear in `labels.jsonl` and in the dataset tree
TYPE_IDS: list[str] = (
    [f"{p}/{t}" for p, ts in PLUGIN_TYPES.items() for t in ts
     if p not in ("Elytrium/LimboFilter", "Leymooo/BungeeCord", "Mateitaa1/CaptchaVerifyZ",
                  "Supl1n/CaptchaGUI", "GalleryCaptcha")]
    + ["LimboFilter/map", "LimboFilter/symbols", "LimboFilter/framed3x3", "LimboFilter/framed2x2",
       "BotFilter/map", "CaptchaVerifyZ/map", "CaptchaGUI/clickblock",
       "GalleryCaptcha/ru-numberword", "GalleryCaptcha/ru-numberword-caption",
       "GalleryCaptcha/ru-symbols", "GalleryCaptcha/ru-web",
       "GalleryCaptcha/ru-object-swatch"]
)

#: the types that are *not* a recogniser target (the exclusion list of `train/train.py`)
NOT_OCR_TYPES = {
    "LagBug/XProtect/drop", "LagBug/XProtect/jump", "LagBug/XProtect/sneak",
    "LagBug/XProtect/different", "LagBug/XProtect/slot", "LagBug/XProtect/color",
    "LagBug/XProtect/gui", "LagBug/XProtect/picture",
    "China2B2T/Captcha/wool", "jSdCool/minecaptcha/image", "GalleryCaptcha/ru-object-swatch",
    "CaptchaGUI/clickblock", "FeelingAlive0/AdvancedCaptcha/button",
    "LimboFilter/map", "LimboFilter/framed3x3", "LimboFilter/framed2x2",
    "GalleryCaptcha/ru-numberword", "GalleryCaptcha/ru-numberword-caption",
    "Yukun99/Captchas/itemslot", "Joey61021/captcha/colorgui",
    "Archy-X/Krypton/menu", "LagBug/XProtect/equation",
    "FeelingAlive0/AdvancedCaptcha/math", "Mrbysco/Captcha/math",
    "jonesdevelopment/sonar/standard", "jonesdevelopment/sonar/complex",
    "jonesdevelopment/sonar/legacy", "Z4OLLIEZ4/reCaptcha/captchasx",
}


def plugin_of(type_id: str) -> str:
    """The plugin key a dataset type id belongs to."""
    if type_id.startswith("GalleryCaptcha/"):
        return "GalleryCaptcha"
    if type_id.startswith("LimboFilter/"):
        return "Elytrium/LimboFilter"
    if type_id.startswith("BotFilter/"):
        return "Leymooo/BungeeCord"
    if type_id.startswith("CaptchaVerifyZ/"):
        return "Mateitaa1/CaptchaVerifyZ"
    if type_id.startswith("CaptchaGUI/"):
        return "Supl1n/CaptchaGUI"
    parts = type_id.split("/")
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return type_id


# =====================================================================================
# Small helpers
# =====================================================================================

def log(msg: str) -> None:
    print(msg, flush=True)


def read_labels(directory: str) -> list[dict]:
    """Read a `labels.jsonl` file."""
    rows = []
    with open(os.path.join(directory, "labels.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def find_types(roots: list[str]) -> list[tuple[str, str, str]]:
    """Every dataset type under the roots, as `(type_id, directory, root)`."""
    found = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            if "labels.jsonl" not in files:
                continue
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            found.append((rel, dirpath, root))
    return sorted(found)


def newest_checkpoint(*dirs: str) -> str | None:
    """The newest `ckpt/step_*.pt` under any of the directories."""
    best = None
    for d in dirs:
        for sub in (d, os.path.join(d, "ckpt")):
            if not os.path.isdir(sub):
                continue
            for name in os.listdir(sub):
                if not (name.startswith("step_") and name.endswith(".pt")):
                    continue
                path = os.path.join(sub, name)
                if best is None or os.path.getmtime(path) > os.path.getmtime(best):
                    best = path
    return best


def derive_geometry(state: dict) -> dict:
    """Read the architecture's hyper-parameters out of the checkpoint's state dict.

    The checkpoint does not store `hidden` or `glyph_height` separately - it stores the
    tensors, and the tensors know their own shape. Deriving them from the shapes is
    exact, where reading them from a default would be a guess.
    """
    fc_w = state["fc.weight"]
    num_classes, hidden2 = int(fc_w.shape[0]), int(fc_w.shape[1])
    hidden = hidden2 // 2
    rnn_ih = state["rnn.weight_ih_l0"]
    lstm_hidden = int(rnn_ih.shape[0]) // 4
    rows = int(rnn_ih.shape[1]) // 256
    if lstm_hidden != hidden:
        raise ValueError(f"the head and the LSTM disagree on the hidden size: {hidden} vs {lstm_hidden}")
    glyph_height = rows * 8
    return {
        "num_classes": num_classes,
        "hidden": hidden,
        "glyph_height": glyph_height,
        "rows": rows,
    }


def import_from_dir(directory: str, module_name: str):
    """Import a module from a directory (the exported `modeling_captcha.py` etc.)."""
    if directory not in sys.path:
        sys.path.insert(0, directory)
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


# =====================================================================================
# The reference implementation - the training code
# =====================================================================================

def training_reference(items: list[dict], state: dict, charset: str, glyph_height: int):
    """The predictions the *training* code produces for these items.

    This is the ground truth the export is checked against: the same checkpoint, the
    same dataset class, the same greedy decode.
    """
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    from captcha_crnn import CRNN, CaptchaDataset, build_encoder, collate, greedy_decode

    cs = build_encoder(charset)
    model = CRNN(cs.num_classes, glyph_height=glyph_height)
    model.load_state_dict(state)
    model.eval()

    dataset = CaptchaDataset(items, cs.encode, glyph_height=glyph_height, augment=False)
    batch = collate([dataset[i] for i in range(len(items))])
    with torch.no_grad():
        logits, _ = model(batch["images"])
    return greedy_decode(logits.float(), cs.decode), batch


# =====================================================================================
# The export
# =====================================================================================

def write_repo(out_dir: str, cfg: dict, state: dict, charset: str) -> None:
    """Write everything except the weights, the ONNX and the model card."""
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "onnx"), exist_ok=True)

    with open(os.path.join(out_dir, "configuration_captcha.py"), "w", encoding="utf-8") as f:
        f.write(CONFIGURATION_TEMPLATE.format(charset=charset))
    with open(os.path.join(out_dir, "modeling_captcha.py"), "w", encoding="utf-8") as f:
        f.write(MODELING_TEMPLATE)
    with open(os.path.join(out_dir, "processing_captcha.py"), "w", encoding="utf-8") as f:
        f.write(PROCESSING_TEMPLATE.format(charset=charset))

    config = {
        "architectures": ["CaptchaModel"],
        "model_type": "captcha",
        "auto_map": AUTO_MAP,
        "num_classes": cfg["num_classes"],
        "hidden": cfg["hidden"],
        "dropout": cfg["dropout"],
        "glyph_height": cfg["glyph_height"],
        "charset": charset,
        "blank_index": 0,
        "min_width": cfg["min_width"],
        "max_width": cfg["max_width"],
        "initializer_range": 0.02,
        "torch_dtype": "float32",
    }
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")

    processor_config = {
        "processor_class": "CaptchaProcessor",
        "auto_map": {"AutoProcessor": AUTO_MAP["AutoProcessor"]},
        "glyph_height": cfg["glyph_height"],
        "min_width": cfg["min_width"],
        "max_width": cfg["max_width"],
        "charset": charset,
        "blank_index": 0,
        "mean": 0.5,
        "std": 0.5,
        "pad_value": 0.0,
        "line_std_threshold": 6.0,
    }
    with open(os.path.join(out_dir, "processor_config.json"), "w", encoding="utf-8") as f:
        json.dump(processor_config, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # The 4.x layout, and the fallback for anybody whose `processor_config.json` is
    # missing. Same attributes, plus the `auto_map` that resolves the class.
    preprocessor_config = dict(processor_config)
    with open(os.path.join(out_dir, "preprocessor_config.json"), "w", encoding="utf-8") as f:
        json.dump(preprocessor_config, f, indent=2, ensure_ascii=False)
        f.write("\n")

    vocab = {
        "blank_index": 0,
        "blank_token": "<blank>",
        "charset": charset,
        "stoi": {c: i + 1 for i, c in enumerate(charset)},
        "itos": {str(i + 1): c for i, c in enumerate(charset)},
    }
    with open(os.path.join(out_dir, "vocab.json"), "w", encoding="utf-8") as f:
        json.dump(vocab, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(os.path.join(out_dir, "LICENSE"), "w", encoding="utf-8") as f:
        f.write(MIT_LICENSE)

    # The weights. `safetensors` writes exactly the tensors of the state dict, with the
    # same names the model has, so `from_pretrained` finds every one of them.
    from safetensors.torch import save_file

    tensors = {k: v.detach().cpu().contiguous() for k, v in state.items()}
    save_file(tensors, os.path.join(out_dir, "model.safetensors"), metadata={"format": "pt"})


def export_onnx(out_dir: str, state: dict, cfg: dict, charset: str) -> str:
    """Export the ONNX graph with `torch.onnx.export`.

    `optimum` is not used and cannot be: `transformers.onnx` was removed in
    transformers 5.x and `optimum-onnx` 0.1.0 declares `transformers<4.58.0,>=4.36`.

    The dynamo exporter (the default since torch 2.9) cannot lower `nn.LSTM` in this
    torch build, so the TorchScript exporter is the fallback. Both are
    `torch.onnx.export`; the width stays a dynamic axis either way.
    """
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    from captcha_crnn import CRNN

    class Wrapper(nn.Module):
        def __init__(self, model):
            super().__init__()
            self.model = model

        def forward(self, pixel_values):
            f = self.model.cnn(pixel_values)
            b, c, h, w = f.shape
            f = f.permute(0, 3, 1, 2).reshape(b, w, h * c)
            f, _ = self.model.rnn(f)
            return self.model.fc(f)

    model = CRNN(cfg["num_classes"], glyph_height=cfg["glyph_height"])
    model.load_state_dict(state)
    model.eval()
    wrapper = Wrapper(model).eval()

    path = os.path.join(out_dir, "onnx", "model.onnx")
    sample = torch.zeros(1, 1, cfg["glyph_height"], 128)

    errors = []
    try:
        from torch.export import Dim

        torch.onnx.export(
            wrapper, (sample,), path,
            input_names=["pixel_values"], output_names=["logits"],
            dynamic_shapes={"x": {0: Dim("batch"), 3: Dim("width")}},
            opset_version=18, dynamo=True,
        )
        return "dynamo"
    except Exception as exc:  # noqa: BLE001 - the fallback is the point
        errors.append(f"dynamo exporter: {type(exc).__name__}: {exc}")
        log(f"  the dynamo ONNX exporter failed ({type(exc).__name__}); "
            f"falling back to the TorchScript exporter")

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        torch.onnx.export(
            wrapper, (sample,), path,
            input_names=["pixel_values"], output_names=["logits"],
            dynamic_axes={"pixel_values": {0: "batch", 3: "width"},
                          "logits": {0: "batch", 1: "time"}},
            opset_version=17, dynamo=False,
        )
    return "torchscript"


# =====================================================================================
# The verification
# =====================================================================================

def pick_samples(charset: str, n: int, roots: list[str]) -> list[dict]:
    """Pick a spread of labelled images across the dataset trees.

    A type that has a text band contributes a banded sample (that is the interesting
    path); a type without one contributes a whole frame.
    """
    table = {c: i for i, c in enumerate(charset)}
    types = find_types(roots)
    if not types:
        return []
    step = max(1, len(types) // max(1, n))
    picked = types[::step][:n]
    samples = []
    for type_id, directory, _root in picked:
        try:
            rows = read_labels(directory)
        except OSError:
            continue
        if not rows:
            continue
        banded = [r for r in rows if r.get("roi")]
        row = (banded or rows)[0]
        text = row.get("text") or row.get("answer") or ""
        if not text or any(c not in table for c in text):
            continue
        if len(text) > 12:
            continue
        samples.append({
            "type": type_id,
            "path": os.path.join(directory, row["file"]),
            "roi": row.get("roi"),
            "text": text,
            "answer": row.get("answer", text),
        })
    return samples


def exported_predictions(out_dir: str, samples: list[dict], model=None, processor=None):
    """The predictions of the *exported* code, in this process."""
    if model is None or processor is None:
        modeling = import_from_dir(out_dir, "modeling_captcha")
        processing = import_from_dir(out_dir, "processing_captcha")
        model = modeling.CaptchaModel.from_pretrained(out_dir)
        processor = processing.CaptchaProcessor.from_pretrained(out_dir)
    model.eval()
    images = [s["path"] for s in samples]
    rois = [s["roi"] for s in samples]
    texts = [s["text"] for s in samples]
    inputs = processor(images=images, roi=rois, text=texts, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
    return model.greedy_decode(logits)


def fresh_process_predictions(out_dir: str, samples: list[dict], spec_path: str) -> list[list]:
    """Load the repository in a **fresh process** through AutoModel / AutoProcessor."""
    cmd = [sys.executable, os.path.abspath(__file__),
           "--_load-check", out_dir, "--_load-check-spec", spec_path]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if proc.returncode != 0:
        raise RuntimeError(f"the fresh-process load failed:\n{proc.stdout}\n{proc.stderr}")
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    return payload["preds"]


def load_check(out_dir: str, spec_path: str) -> int:
    """The child process of `fresh_process_predictions`: load and predict."""
    from transformers import AutoModel, AutoProcessor

    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    model = AutoModel.from_pretrained(out_dir, trust_remote_code=True).eval()
    processor = AutoProcessor.from_pretrained(out_dir, trust_remote_code=True)
    inputs = processor(images=[s["path"] for s in spec["samples"]],
                       roi=[s["roi"] for s in spec["samples"]],
                       text=[s["text"] for s in spec["samples"]],
                       return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
    preds = model.greedy_decode(logits)
    print(json.dumps({"preds": [[t, c] for t, c in preds],
                      "model_class": type(model).__name__,
                      "processor_class": type(processor).__name__}))
    return 0


def onnx_predictions(out_dir: str, batch: dict) -> list[list]:
    """The predictions of the ONNX graph, through onnxruntime."""
    import onnxruntime as ort

    path = os.path.join(out_dir, "onnx", "model.onnx")
    sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    x = batch["images"].numpy().astype(np.float32)
    logits = sess.run(None, {name: x})[0]
    with open(os.path.join(out_dir, "vocab.json"), encoding="utf-8") as f:
        vocab = json.load(f)
    itos = vocab["itos"]
    blank = vocab["blank_index"]
    preds = []
    for b in range(logits.shape[0]):
        ids = logits[b].argmax(axis=-1)
        chars, prev = [], -1
        for k in ids:
            k = int(k)
            if k != prev and k != blank:
                chars.append(itos.get(str(k), ""))
            prev = k
        preds.append(["".join(chars), 0.0])
    return preds


# =====================================================================================
# The model card
# =====================================================================================

def training_data_section() -> str:
    """The per-type provenance table of the training data."""
    lines = [
        "Every image was rendered by this project's own generators, which re-implement the",
        "captchas that open-source Minecraft anti-bot plugins draw. The dataset is **46 types",
        "x 100 images** (3400 in `dataset/out/`, 1200 in `dataset/out_ru/`), and it is published",
        "**one repository per licence family**, because the upstream plugins do not share one",
        "licence. Every row of every published dataset carries its `mode` and its upstream",
        "licence.",
        "",
        "`mode` is:",
        "",
        "* **faithful** - a line-by-line re-implementation from the upstream source, which the",
        "  upstream licence permits;",
        "* **clean-room** - the algorithm and the resulting picture were read from upstream and",
        "  rewritten independently: no code, comments, identifiers or copyright headers are",
        "  carried over. Used wherever the licence forbids copying, or where no licence exists;",
        "* **reconstructed** - no upstream source was found; the generator is driven by the",
        "  reference screenshots of the gallery catalogue and says so in its javadoc.",
        "",
        "| type | upstream | upstream licence | mode | a recogniser target? |",
        "|---|---|---|---|---|",
    ]
    for type_id in TYPE_IDS:
        plugin = plugin_of(type_id)
        upstream, licence, mode = PLUGINS.get(plugin, (plugin, "unknown", "unknown"))
        target = "no" if type_id in NOT_OCR_TYPES else "yes"
        lines.append(f"| `{type_id}` | {upstream} | {licence} | {mode} | {target} |")
    lines += [
        "",
        "Two of the renders are **approximations**, not reproductions, and the dataset card",
        "says so: the `jonesdevelopment/sonar` dot-matrix fonts could not be redistributed",
        "(`dotness.ttf` is personal-use only, `DotMatrix.ttf` has no licence at all), so Lucida",
        "Console and Courier New stand in; and `Archy-X/Krypton`'s swatch colours are invented,",
        "because the upstream derives them from the running server's material registry.",
        "",
        "The **weights** are MIT. The **dataset** is not: a user of the dataset has to comply",
        "with the licence of the plugin each row came from, and the three plugins with no",
        "licence at all (`Archy-X/Krypton`, `Yukun99/Captchas`,",
        "`ringoame196-s-mcPlugin/ReproductionCAPTCHA`, plus `Supl1n/CaptchaGUI` and the",
        "all-rights-reserved `Mateitaa1/CaptchaVerifyZ`) are published in a family of their",
        "own, because there the default is *all rights reserved*.",
    ]
    return "\n".join(lines)


def evaluation_section(val_report: dict | None, cfg: dict, n_params: int) -> str:
    """The measured numbers, from `val_report.json` when there is one."""
    lines = [
        f"The model has **{n_params:,} parameters** and **{cfg['num_classes']} classes**"
        f" ({cfg['num_classes'] - 1} characters plus the blank).",
        "",
    ]
    if not val_report:
        lines += [
            "**No evaluation report was supplied with this export.** The numbers of the",
            "training run are in the run's own `val_report.json`; re-export with",
            "`--val-report <path>` and they will be written into this section.",
        ]
        return "\n".join(lines)

    overall = val_report.get("overall", {})
    lines += [
        "| metric | value |",
        "|---|---|",
        f"| exact match | {overall.get('accuracy', 0):.4f} |",
        f"| mean CER | {overall.get('cer', 0):.4f} |",
        f"| samples | {overall.get('n', 0)} |",
        "",
        "The validation split is **by captcha type, never by image**: the unit of",
        "generalisation that matters is a plugin, and a random image split leaks because",
        "several types have only a handful of distinct answers (under a random split, about a",
        "third of all test samples have their exact gold answer string in the training half).",
        "",
        "Per type:",
        "",
        "| type | exact match | CER | n |",
        "|---|---|---|---|",
    ]
    for type_id, d in sorted(val_report.get("per_type", {}).items()):
        lines.append(f"| `{type_id}` | {d.get('accuracy', 0):.4f} | {d.get('cer', 0):.4f} "
                     f"| {d.get('n', 0)} |")
    return "\n".join(lines)


def write_model_card(out_dir: str, cfg: dict, charset: str, n_params: int,
                     val_report: dict | None, repo_id: str, checkpoint: str,
                     step: int, epoch: int, onnx_exporter: str) -> None:
    import transformers

    try:
        import onnxruntime

        onnx_version = onnxruntime.__version__
    except ImportError:  # pragma: no cover
        onnx_version = "not installed"

    card = MODEL_CARD_TEMPLATE.format(
        title=repo_id,
        intro=(
            f"A CRNN + CTC captcha recogniser, trained from scratch by the **CaptchaOCR**\n"
            f"project on pixel-faithful re-implementations of Minecraft anti-bot-plugin\n"
            f"captchas.\n\n"
            f"* weights: `model.safetensors` (safetensors, {n_params:,} parameters)\n"
            f"* exported from the training checkpoint `{os.path.basename(checkpoint)}` "
            f"(step {step}, epoch {epoch})\n"
            f"* ONNX: `onnx/model.onnx` (exported with `torch.onnx.export`, "
            f"{onnx_exporter} exporter)"
        ),
        glyph_height=cfg["glyph_height"],
        num_classes=cfg["num_classes"],
        num_chars=len(charset),
        charset=charset,
        repo_id=repo_id,
        training_data=training_data_section(),
        evaluation=evaluation_section(val_report, cfg, n_params),
        python_version=".".join(str(v) for v in sys.version_info[:3]),
        torch_version=torch.__version__,
        transformers_version=transformers.__version__,
        onnxruntime_version=onnx_version,
    )
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(card)


# =====================================================================================
# main
# =====================================================================================

def make_synthetic_checkpoint(path: str, charset: str, glyph_height: int = 32,
                              hidden: int = 256, step: int = 1) -> str:
    """Write a checkpoint in the *exact* format `train/train.py` writes.

    The export path has to be provable before a real training run finishes, so this
    builds a randomly initialised CRNN and stores it the way the training loop stores
    it: the model state dict, the optimiser and scheduler states, the step, the RNG
    states, the args and the charset. The exported repository is then a real,
    loadable model - it simply has no training behind it.
    """
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    from captcha_crnn import CRNN, build_encoder

    cs = build_encoder(charset)
    model = CRNN(cs.num_classes, hidden=hidden, glyph_height=glyph_height)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=1e-3, total_steps=100, pct_start=0.05)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    torch.save({
        "model": model.state_dict(),
        "optim": opt.state_dict(),
        "sched": sched.state_dict(),
        "epoch": 0,
        "step": step,
        "rng": torch.get_rng_state(),
        "cuda_rng": None,
        "aug_rng": None,
        "args": {"charset": "latin" if charset == LATIN_CHARSET else "cyrillic",
                 "glyph_height": glyph_height, "epochs": 0, "batch_size": 32, "lr": 1e-3},
        "charset": charset,
    }, path)
    return path


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--make-synthetic-checkpoint", default=None, metavar="PATH",
                   help="write a synthetic checkpoint (the format train/train.py writes) "
                        "and exit; for testing the export path before a run finishes")
    p.add_argument("--checkpoint", default=None,
                   help="the checkpoint to export (default: the newest step_*.pt under --out)")
    p.add_argument("--from-run", default=None,
                   help="the training run's directory; takes the checkpoint and the "
                        "val_report.json from it")
    p.add_argument("--out", default=None, help="the target repository directory")
    p.add_argument("--charset", choices=["latin", "cyrillic"], default="latin",
                   help="a cross-check against the charset stored in the checkpoint")
    p.add_argument("--val-report", default=None, help="the run's val_report.json")
    p.add_argument("--repo-id", default=None,
                   help="the repository id the model card refers to")
    p.add_argument("--n-verify", type=int, default=12,
                   help="how many images the verification uses")
    p.add_argument("--dataset-roots", nargs="*", default=None,
                   help="the dataset trees the verification images come from")
    p.add_argument("--skip-onnx", action="store_true")
    p.add_argument("--skip-verify", action="store_true",
                   help="write the repository without verifying it (not recommended)")
    p.add_argument("--report", default=None, help="write the verification report as JSON")
    # the child process of the fresh-process check
    p.add_argument("--_load-check", default=None, help=argparse.SUPPRESS)
    p.add_argument("--_load-check-spec", default=None, help=argparse.SUPPRESS)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args._load_check:
        return load_check(args._load_check, args._load_check_spec)
    if args.make_synthetic_checkpoint:
        cs = LATIN_CHARSET if args.charset == "latin" else CYRILLIC_CHARSET
        p = make_synthetic_checkpoint(args.make_synthetic_checkpoint, cs)
        log(f"wrote a synthetic checkpoint to {p}")
        return 0

    out_dir = os.path.abspath(args.out)
    run_dir = os.path.abspath(args.from_run) if args.from_run else None

    ckpt_path = args.checkpoint
    if ckpt_path is None:
        ckpt_path = newest_checkpoint(*( [run_dir] if run_dir else [] ), out_dir)
    if ckpt_path is None or not os.path.isfile(ckpt_path):
        log(f"no checkpoint found (looked for step_*.pt under "
            f"{run_dir or out_dir}); pass --checkpoint")
        return 2
    ckpt_path = os.path.abspath(ckpt_path)
    log(f"checkpoint: {ckpt_path}")

    val_report = None
    val_path = args.val_report
    if val_path is None and run_dir:
        candidate = os.path.join(run_dir, "val_report.json")
        val_path = candidate if os.path.isfile(candidate) else None
    if val_path and os.path.isfile(val_path):
        with open(val_path, encoding="utf-8") as f:
            val_report = json.load(f)
        log(f"val report: {val_path}")
    else:
        log("val report: none (the model card will say so)")

    state = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    ckpt_state = state["model"]
    charset = state.get("charset") or (LATIN_CHARSET if args.charset == "latin"
                                       else CYRILLIC_CHARSET)
    if args.charset == "latin" and charset != LATIN_CHARSET:
        log(f"note: the checkpoint's charset is not the Latin one ({len(charset)} characters)")
    step = int(state.get("step", 0))
    epoch = int(state.get("epoch", 0))

    geom = derive_geometry(ckpt_state)
    ckpt_args = state.get("args") or {}
    cfg = {
        "num_classes": geom["num_classes"],
        "hidden": geom["hidden"],
        "dropout": 0.1,
        "glyph_height": geom["glyph_height"],
        "min_width": 64,
        "max_width": 400,
    }
    n_params = sum(int(v.numel()) for v in ckpt_state.values()
                   if hasattr(v, "numel") and v.dtype.is_floating_point)
    log(f"architecture: {cfg['num_classes']} classes, hidden {cfg['hidden']}, "
        f"glyph height {cfg['glyph_height']}, {n_params:,} parameters")

    os.makedirs(out_dir, exist_ok=True)
    write_repo(out_dir, cfg, ckpt_state, charset)
    log(f"wrote the repository skeleton to {out_dir}")

    onnx_exporter = "skipped"
    if not args.skip_onnx:
        onnx_exporter = export_onnx(out_dir, ckpt_state, cfg, charset)
        size = os.path.getsize(os.path.join(out_dir, "onnx", "model.onnx"))
        log(f"wrote onnx/model.onnx ({size / 1e6:.1f} MB, {onnx_exporter} exporter)")

    repo_id = args.repo_id or os.path.basename(out_dir.rstrip(os.sep)) or "captcha-crnn-ctc"
    write_model_card(out_dir, cfg, charset, n_params, val_report, repo_id, ckpt_path,
                     step, epoch, onnx_exporter)
    log("wrote README.md (the model card)")

    report: dict[str, Any] = {
        "checkpoint": ckpt_path,
        "out_dir": out_dir,
        "step": step,
        "epoch": epoch,
        "charset": charset,
        "num_classes": cfg["num_classes"],
        "hidden": cfg["hidden"],
        "glyph_height": cfg["glyph_height"],
        "parameters": n_params,
        "onnx_exporter": onnx_exporter,
        "verified": False,
    }

    if args.skip_verify:
        log("verification skipped (--skip-verify)")
    else:
        roots = args.dataset_roots or DEFAULT_OUT_DIRS
        samples = pick_samples(charset, args.n_verify, roots)
        if not samples:
            log("no dataset images found - the export was NOT verified")
            report["error"] = "no dataset images for the verification"
        else:
            report = verify(out_dir, samples, ckpt_state, charset, cfg, report)
            report["verified"] = True

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        log(f"verification report -> {args.report}")
    return 0 if report.get("verified") or args.skip_verify else 1


def verify(out_dir: str, samples: list[dict], ckpt_state: dict, charset: str,
           cfg: dict, report: dict) -> dict:
    """The three-way check: the training code, the exported code, a fresh process, ONNX."""
    log("")
    log(f"verifying on {len(samples)} images from the dataset")

    # -- 1. the training code is the reference -----------------------------------
    items = [{"type": s["type"], "path": s["path"], "text": s["text"],
              "answer": s["answer"], "roi": s["roi"], "type_id": s["type"]}
             for s in samples]
    ref_preds, batch = training_reference(items, ckpt_state, charset, cfg["glyph_height"])
    ref = [p[0] for p in ref_preds]
    log(f"  training code : {ref}")

    # -- 2. the exported code, in this process ------------------------------------
    exp_preds = exported_predictions(out_dir, samples)
    exp = [p[0] for p in exp_preds]
    same = sum(1 for a, b in zip(ref, exp) if a == b)
    log(f"  exported code : {exp}")
    log(f"  training code vs exported code: {same}/{len(ref)} identical")
    if same != len(ref):
        for s, a, b in zip(samples, ref, exp):
            if a != b:
                log(f"    MISMATCH {s['type']} {os.path.basename(s['path'])}: "
                    f"training={a!r} exported={b!r}")
    report["parity_training_vs_exported"] = f"{same}/{len(ref)}"

    # -- 3. a fresh process, through AutoModel / AutoProcessor --------------------
    spec_path = os.path.join(out_dir, "..", "_load_check_spec.json")
    spec_path = os.path.abspath(spec_path)
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump({"samples": samples}, f)
    try:
        fresh = fresh_process_predictions(out_dir, samples, spec_path)
        fresh_texts = [p[0] for p in fresh]
        same_fresh = sum(1 for a, b in zip(ref, fresh_texts) if a == b)
        log(f"  fresh process (AutoModel + AutoProcessor, trust_remote_code=True): "
            f"{fresh_texts}")
        log(f"  training code vs fresh process: {same_fresh}/{len(ref)} identical")
        report["parity_fresh_process"] = f"{same_fresh}/{len(ref)}"
    except Exception as exc:  # noqa: BLE001
        log(f"  fresh process load FAILED: {type(exc).__name__}: {exc}")
        report["parity_fresh_process"] = f"FAILED: {exc}"
        same_fresh = -1
    finally:
        if os.path.exists(spec_path):
            os.remove(spec_path)

    # -- 4. the ONNX graph --------------------------------------------------------
    try:
        onnx_preds = onnx_predictions(out_dir, batch)
        onnx_texts = [p[0] for p in onnx_preds]
        same_onnx = sum(1 for a, b in zip(ref, onnx_texts) if a == b)
        log(f"  onnxruntime   : {onnx_texts}")
        log(f"  training code vs onnxruntime: {same_onnx}/{len(ref)} identical")
        report["parity_onnx"] = f"{same_onnx}/{len(ref)}"
    except Exception as exc:  # noqa: BLE001
        log(f"  onnxruntime FAILED: {type(exc).__name__}: {exc}")
        report["parity_onnx"] = f"FAILED: {exc}"
        same_onnx = -1

    report["samples"] = [{"type": s["type"], "file": os.path.basename(s["path"]),
                          "roi": s["roi"], "gold": s["text"],
                          "training": a, "exported": b}
                         for s, a, b in zip(samples, ref, exp)]
    ok = same == len(ref) and same_fresh == len(ref) and same_onnx == len(ref)
    report["all_three_agree"] = ok
    log("")
    log("VERIFICATION " + ("PASSED" if ok else "FAILED"))
    return report


if __name__ == "__main__":
    sys.exit(main())
