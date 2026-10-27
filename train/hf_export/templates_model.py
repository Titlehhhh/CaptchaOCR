"""The two Python files that make the exported repository loadable.

`configuration_captcha.py` (the config class) and `modeling_captcha.py` (the CRNN
+ CTC model) are written into the exported folder verbatim, with the charset
substituted into the config. They are plain strings, not code of this package:
what lands in the exported repository is exactly what is written here.
"""

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
from dataclasses import dataclass
from transformers import PreTrainedModel

try:  # transformers 5.x
    from transformers.utils import ModelOutput
except ImportError:  # pragma: no cover - transformers 4.x
    from transformers.modeling_outputs import ModelOutput

try:  # when this file is loaded as part of a package (the trust_remote_code path)
    from .configuration_captcha import CaptchaConfig
except ImportError:  # pragma: no cover - when it is imported directly from a directory
    from configuration_captcha import CaptchaConfig


@dataclass
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
