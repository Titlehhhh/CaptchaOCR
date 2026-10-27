"""Fine-tune `PaddlePaddle/PP-OCRv6_medium_rec_safetensors` on the CapthaModel dataset.

    .venv-gpu\\Scripts\\python.exe train\\finetune_ppocr.py --epochs 2 --limit-per-type 20 \
        --out train\\run_ppocr\\smoke

What this script does, in order:

1. **Loads the pretrained model** (`PPOCRV6SmallRecForTextRecognition` - transformers 5.19
   has no `pp_ocrv6_medium_rec` class, the medium model is loaded through the small
   class because that is what its `config.json` declares) and keeps its **pretrained
   head** (18 710 classes, index 0 = blank). Replacing the head would throw away the
   pretrained output layer and the zero-step baseline with it, so it is not replaced.
2. **Builds the split by type**: whole plugins are held out, never random samples.
3. **Measures the zero step**: the pretrained model on our types *before* any training.
   If this number is far below the 0.40-0.55 that the archived bench measured, the
   input pipeline is wrong and no training is done until it is fixed.
4. **Trains** with its own loop (not `transformers.Trainer`): AdamW, separate learning
   rates for the backbone and the head, OneCycleLR, fp16 + GradScaler (bf16 is emulated
   on sm_61 and must not be used), gradient clipping, checkpoints, `--resume`.
5. **Evaluates** per type: exact match and CER, aggregated as the **median over types**.

The CTC loss is ours: the transformers class has no loss and no `labels` argument, so
`torch.nn.CTCLoss(blank=0, zero_infinity=True)` is applied to the log-softmax of the
head logits, which are recomputed from the model's own modules (the public `forward`
returns a softmax, which is not what CTC wants).
"""

import os
import sys

import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# The machine's shared Hugging Face cache is read-only for child processes, so the
# cache has to point into the workspace before anything touches the hub.
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".hf-cache"))
os.environ.setdefault("HF_HUB_CACHE", os.path.join(ROOT, ".hf-cache", "hub"))

import finetune_common  # noqa: E402
from finetune_common import (DEFAULT_VAL_TYPES, GROUP_C, norm)  # noqa: E402
from ppocr_core import (DEFAULT_MODEL, aggregate, build_split, evaluate,  # noqa: E402
                       forward_logits, greedy_decode, print_per_type)
from ppocr_run import main  # noqa: E402  (the loop lives in its own module)
from ppocr_data import (PPOCRDataset, Vocab, build_eval_items, build_items,  # noqa: E402
                        collate, find_types, read_labels)

# The held-out types (`DEFAULT_VAL_TYPES`) and the group C list live in
# `train/finetune_common.py`: they are the same in the PP-OCRv6 and the TrOCR run,
# which is what makes the two numbers comparable.
#
# The model-specific pieces - the head's logits, the greedy CTC decoding, the split,
# the evaluation and the metrics - are in `train/ppocr_core.py`; the loop is in
# `train/ppocr_run.py`. They are imported here under their old names, so that
# `train/soup_eval.py` and `reports/HTML/make_scoreboard.py` keep working.
