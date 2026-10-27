"""The `processing_captcha.py` template - the processor of the exported repository.

One `ProcessorMixin` with no sub-processor: transformers 5.x moved every processor
attribute into a single nested `processor_config.json` and stopped writing
`special_tokens_map.json` / `added_tokens.json`, so a repository that ships a
sub-processor fails to load.
"""

PROCESSING_TEMPLATE = '''"""The Captcha processor: **one** `ProcessorMixin`, with no sub-processor.

Why one class and no sub-processor: transformers 5.x moved every processor attribute
into a single nested `processor_config.json` and stopped writing
`special_tokens_map.json` / `added_tokens.json`. A repository that ships a
sub-processor therefore fails to load with *"Processor was loaded, but it is not an
instance of ProcessorMixin"* - the failure that `hongyusir/trocr-base-printed_captcha_ocr`
and `DunnBC22/trocr-base-printed_captcha_ocr` hit. This class has no sub-processor
at all: the image pipeline lives in the class itself.

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
                raise ValueError(f"expected {{n}} values, got {{len(value)}}")
            return list(value)
        return [value] * n
'''
