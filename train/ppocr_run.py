"""Flat re-export shim for the PP-OCRv6 run loop.

The code lives in `train/finetune/ppocr_run.py` (moved from this path);
`train/finetune_ppocr.py` keeps importing the flat name `ppocr_run`
and gets the same objects.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from finetune.ppocr_run import *  # noqa: E402,F401,F403
from finetune.ppocr_run import main  # noqa: E402,F401
