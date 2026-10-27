"""The model-specific parts of the PP-OCRv6 fine-tune.

The head's logits (without the softmax the public `forward` applies), the greedy CTC
decoding, the split, the evaluation and the metrics. `train/finetune_ppocr.py` is
the entry point and re-exports these names, so that `train/soup_eval.py` and
`reports/HTML/make_scoreboard.py` keep importing them from there.
"""

import os

import torch
import torch.nn.functional as F

from . import common as finetune_common  # noqa: E402
from .common import (DEFAULT_VAL_TYPES, GROUP_C, accumulate_type,  # noqa: E402
                     finalise_per_type, norm)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_MODEL = "PaddlePaddle/PP-OCRv6_medium_rec_safetensors"


def forward_logits(model, pixel_values):
    """The head logits, without the softmax the public `forward` applies.

    Verified: `model(x).last_hidden_state == softmax(head.head(head.encoder(model(x))))`
    with a max absolute difference of 0.
    """
    h = model.model(pixel_values).last_hidden_state
    enc = model.head.encoder(h).last_hidden_state
    return model.head.head(enc)


def greedy_decode(logp, vocab):
    """Greedy CTC decode of a (B, T, C) log-probability tensor."""
    best = logp.argmax(dim=-1)
    out = []
    for b in range(best.shape[0]):
        chars = []
        prev = -1
        for t in range(best.shape[1]):
            k = int(best[b, t])
            if k != prev and k != vocab.blank:
                chars.append(k)
            prev = k
        out.append(vocab.decode(chars))
    return out


# --------------------------------------------------------------------------- #
# the split
# --------------------------------------------------------------------------- #
def build_split(args, vocab):
    """Decide, per type, whether it is trained on, evaluated, or dropped - and why.

    The skeleton (the held-out types, the excluded types, group C) is the one of
    `train/finetune_common.py`; the rule that is specific to this model is "the
    label has to be expressible in the model's own dictionary".
    """
    roots = [os.path.join(ROOT, "dataset", "out"), os.path.join(ROOT, "dataset", "out_ru")]
    types, stats = finetune_common.discover_types(roots)

    def keep_type(st):
        if st["n_roi"] == 0 and not args.train_frames:
            return False, ("no band (roi = null): not a recognition target "
                           "(pass --train-frames to train them as full frames)")
        alphabet = st["alphabet"]
        missing = sorted(set(alphabet) - set(vocab.table))
        if missing:
            return False, "label outside the model dictionary: " + "".join(missing)
        return True, None

    return finetune_common.build_split(types, stats, args, GROUP_C, keep_type)


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
@torch.no_grad()
def evaluate(model, loader, vocab, device, amp=True):
    """Per type: exact match and CER (both on the normalised strings)."""
    model.eval()
    per_type = {}
    for batch in loader:
        px = batch["images"].to(device, non_blocking=True)
        with torch.autocast("cuda", dtype=torch.float16, enabled=amp and device.type == "cuda"):
            logits = forward_logits(model, px)
        logp = F.log_softmax(logits.float(), dim=-1)
        preds = greedy_decode(logp, vocab)
        for i, (idx, t) in enumerate(zip(batch["indices"], batch["types"])):
            item = loader.dataset.items[idx]
            accumulate_type(per_type, t, preds[i], item["text"])
    out = finalise_per_type(per_type)
    model.train()
    return out


def aggregate(per_type):
    """The aggregate is the MEDIAN over types, not the mean."""
    return finetune_common.aggregate(per_type, cer_micro_over="all")


def print_per_type(per_type, title):
    """Print the per-type table and the aggregate; return the aggregate."""
    return finetune_common.print_per_type(per_type, title, aggregate, precision=3)
