"""Flat re-export shim for the PP-OCRv6 fine-tune shared parts.

The code lives in `train/finetune/common.py` (moved from this path);
`train/finetune_ppocr.py` keeps importing the flat name `finetune_common`
and gets the same objects.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from finetune.common import *  # noqa: E402,F401,F403
