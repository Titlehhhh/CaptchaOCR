"""Fine-tune `microsoft/trocr-small-printed` (ViT encoder + transformer decoder) on the CapthaModel dataset.

    .venv-gpu\\Scripts\\python.exe train\\finetune_trocr.py --out train\\run\\trocr_big --epochs 4 --batch-size 8 --max-minutes 18

What this script does, in order:

1. **Loads the pretrained model** (`VisionEncoderDecoderModel`: DeiT-small ViT encoder,
   384x384 input, 12 layers / 384 hidden; 6-layer transformer decoder, d_model 256,
   cross-attention over the encoder; 61 596 672 parameters) and its own processor
   (`TrOCRProcessor`: `DeiTImageProcessor` for the pixels, `XLMRobertaTokenizer` for the
   text). The normalisation is the processor's, never a hand-rolled one.
2. **Builds the split by type**: whole plugins are held out, never random samples. The
   held-out set is byte-for-byte the one the PP-OCRv6 run used
   (`train/finetune_ppocr.py:DEFAULT_VAL_TYPES`), so the two numbers are comparable.
3. **Measures the zero step**: the pretrained model on our types *before* any training.
   TrOCR was pretrained on printed English receipts (SROIE), not on noisy captchas, so
   this number is expected to be near zero - it is the control that shows the fine-tune
   did something.
4. **Trains** with its own loop (not `transformers.Trainer`): AdamW, a linear warmup +
   cosine decay, fp16 + GradScaler (bf16 is emulated on sm_61 and must not be used),
   gradient clipping, checkpoints, `--resume`.
5. **Evaluates** per type: exact match and CER, aggregated as the **median over types** -
   the same metric code (`train/ppocr_data.py`) the PP-OCRv6 run used.

The loss is the decoder's own cross-entropy: the decoder consumes the encoder's features
autoregressively, so the label tokens are fed shifted right (`decoder_input_ids`) and the
padding is masked with `-100`. This is NOT CTC - there is no blank and no alignment.

**Preprocessing is deliberately identical to the PP-OCRv6 run** (`train/ppocr_data.py`):
crop by `roi`, and for the types without a band crop to the ink bounding box; the same
JPEG/WEBP/brightness/contrast augmentation; the same `norm()` normalisation and the same
`cer()`. Only the pixel geometry differs (384x384 instead of 48x320) because that is what
the TrOCR processor wants.
"""

import os
import sys

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# The machine's shared Hugging Face cache is read-only for child processes, so the
# cache has to point into the workspace before anything touches the hub.
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".hf-cache"))
os.environ.setdefault("HF_HUB_CACHE", os.path.join(ROOT, ".hf-cache", "hub"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
# `transformers` needs `sentencepiece` to build the XLMRobertaTokenizer out of
# `sentencepiece.bpe.model`; without it it falls back to tiktoken and fails.
_LOCAL_WHEELS = os.path.join(ROOT, "train", "run", "trocr_big", "_wheels")
if os.path.isdir(_LOCAL_WHEELS) and _LOCAL_WHEELS not in sys.path:
    sys.path.append(_LOCAL_WHEELS)

import finetune_common  # noqa: E402
from finetune_common import (DEFAULT_VAL_TYPES, GROUP_C)  # noqa: E402
from trocr_core import (DEFAULT_MODEL, aggregate, build_split,  # noqa: E402
                       is_ascii_alphabet, print_per_type)
from trocr_run import main  # noqa: E402  (the loop lives in its own module)
from ppocr_data import build_eval_items, build_items  # noqa: E402

# The TrOCR-specific pieces - the model id, the metrics and the split - are in
# `train/trocr_core.py`; they are imported here under their old names.
