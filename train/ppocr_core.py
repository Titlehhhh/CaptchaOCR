"""Flat re-export shim for the PP-OCRv6 model core.

The code lives in `train/finetune/ppocr_core.py` (moved from this path);
`train/finetune_ppocr.py` keeps importing the flat name `ppocr_core`
and gets the same objects.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from finetune.ppocr_core import *  # noqa: E402,F401,F403
from finetune.ppocr_core import (DEFAULT_MODEL, aggregate, build_split,  # noqa: E402,F401
                                 evaluate, forward_logits, greedy_decode,
                                 print_per_type)
