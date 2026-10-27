import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from finetune.ppocr_data import *  # noqa: E402,F401,F403
from finetune.ppocr_data import (IMG_HEIGHT, MAX_WIDTH, PPOCRDataset, Vocab,  # noqa: E402,F401
                                 build_eval_items, build_items, cer, collate,
                                 find_types, read_labels, type_stats)