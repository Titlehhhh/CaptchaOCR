import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import finetune_common  # noqa: E402
from finetune_common import (DEFAULT_VAL_TYPES, GROUP_C, norm)  # noqa: E402
from ppocr_core import (DEFAULT_MODEL, aggregate, build_split, evaluate,  # noqa: E402
                        forward_logits, greedy_decode, print_per_type)
from ppocr_run import main  # noqa: E402  (the loop lives in its own module)
from ppocr_data import (PPOCRDataset, Vocab, build_eval_items, build_items,  # noqa: E402
                        collate, find_types, read_labels)



if __name__ == "__main__":
    sys.exit(main())
