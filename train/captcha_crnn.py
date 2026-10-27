"""Flat re-export shim for the CRNN+CTC recogniser.

The code lives in `train/crnn/model.py` (moved from this path); external code
(`webapp/backends.py`, `bench/export_onnx.py`, `train/train.py`,
`train/eval_ckpt.py`, the `train/diagnostics/` scripts, `train/export/hf_export/`)
keeps importing the flat name `captcha_crnn` and gets the same objects.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from crnn.model import *  # noqa: E402,F401,F403
from crnn.model import (BLANK, CHARSET, CYRILLIC, Charset, CaptchaDataset, CRNN,  # noqa: E402,F401
                        build_encoder, build_items, cer, collate, find_types,
                        greedy_decode, read_labels)
