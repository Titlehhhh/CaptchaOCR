"""Flat re-export shim for the PP-OCRv6 dataset + charset helpers.

The code lives in `train/finetune/ppocr_data.py` (moved from this path);
external code (`webapp/pipeline.py`, `reports/HTML/make_scoreboard.py`,
`train/soup_eval.py`) keeps importing the flat name `ppocr_data` and gets the
same objects.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from finetune.ppocr_data import *  # noqa: E402,F401,F403
from finetune.ppocr_data import (IMG_HEIGHT, MAX_WIDTH, PPOCRDataset, Vocab,  # noqa: E402,F401
                                 build_eval_items, build_items, cer, collate,
                                 find_types, read_labels, type_stats)
