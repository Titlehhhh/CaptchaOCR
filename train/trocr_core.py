"""The model-specific pieces of the TrOCR fine-tune.

The aggregate, the per-type table and the split. `train/finetune_trocr.py` is the
entry point and re-exports these names; the loop is in `train/trocr_run.py`, the
dataset and the evaluation in `train/trocr_data.py`.

What the two fine-tunes share - the metrics, the split skeleton, the held-out
types - lives in `train/finetune_common.py`.
"""

import os

import finetune_common
from finetune_common import DEFAULT_VAL_TYPES, GROUP_C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_MODEL = "microsoft/trocr-small-printed"

# Characters the PP-OCRv6 run's dictionary could not express. TrOCR's tokenizer CAN
# express Cyrillic, but the PP-OCRv6 run (the model this experiment is compared against)
# trained on 13 Latin types only. To keep the comparison controlled the *same* 13 types
# are used here: the rule is "every character of every label is ASCII". The four
# Cyrillic types are the only ones it removes - exactly the four the PP-OCRv6 run
# dropped for the same reason.
def is_ascii_alphabet(alphabet):
    return all(ord(c) < 128 for c in alphabet)


LATIN_ALLOWED = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz+-*/=")


# --------------------------------------------------------------------------- #
# metrics (the same normalisation as `bench/bench_models.py` and `finetune_ppocr.py`)
# --------------------------------------------------------------------------- #
def aggregate(per_type):
    """The aggregate is the MEDIAN over types, not the mean."""
    return finetune_common.aggregate(per_type, cer_micro_over="cer", empty_items=0)


def print_per_type(per_type, title):
    """Print the per-type table and the aggregate; return the aggregate."""
    return finetune_common.print_per_type(per_type, title, aggregate, precision=4)


# --------------------------------------------------------------------------- #
# the split
# --------------------------------------------------------------------------- #
def build_split(args):
    """Decide, per type, whether it is trained on, evaluated, or dropped - and why.

    The skeleton (the held-out types, the excluded types, group C) is the one of
    `train/finetune_common.py`; the rule that is specific to this model is "the
    label has to be spellable in ASCII".
    """
    roots = [os.path.join(ROOT, "dataset", "out"), os.path.join(ROOT, "dataset", "out_ru")]
    types, stats = finetune_common.discover_types(roots)

    def keep_type(st):
        if st["n_roi"] == 0:
            return False, "no band (roi = null): not a recognition target"
        if not args.allow_cyrillic:
            if not is_ascii_alphabet(st["alphabet"]):
                outside = sorted(set(st["alphabet"]) - LATIN_ALLOWED)
                return False, ("label outside the ASCII alphabet: "
                               + "".join(c if ord(c) < 128 else f"<U+{ord(c):04X}>"
                                         for c in outside))
        return True, None

    return finetune_common.build_split(types, stats, args, GROUP_C, keep_type)
