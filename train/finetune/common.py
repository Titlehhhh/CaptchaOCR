"""The parts that `train/finetune_ppocr.py` and `train/finetune_trocr.py` share.

The two fine-tunes differ in the model, in the loss (CTC against the decoder's own
cross-entropy) and in the flags. What they do **the same** is what the comparison
between them rests on, and that is what lives here:

* the **held-out split** - the same seven types, five whole plugins, in both runs, so
  that the two numbers are measured on the same 3 500 images;
* the **group C list** - the types that are not OCR tasks at all;
* the **normalisation** of a prediction before it is scored (`norm`);
* the **metrics** - exact match and CER per type, the MEDIAN over the types and the
  micro over the images;
* the **split builder** - the same skeleton, with the model's own "is this type
  trainable at all" rule plugged in;
* the **run's bookkeeping** - the seeding, the device, `log.txt` and the runtime block
  of `result.json`.

Nothing here imports torch-heavy model code: the module is the glue, not a framework.
`train/soup_eval.py` imports the metrics from `train/finetune_ppocr.py`, which
re-exports them from here, so the interpolation sweep is measured with exactly the
same code as the training run.
"""

import os
import random
import statistics
import time

import numpy as np
import torch

from .ppocr_data import cer, find_types, type_stats

# The held-out types: whole plugins, five plugins, seven types (Variant 1 of
# `reports/research3/DATASET_AUDIT.md`). The SAME list in both fine-tunes, so the
# PP-OCRv6 numbers and the TrOCR numbers are measured on the same 3500 images.
DEFAULT_VAL_TYPES = [
    "out/jonesdevelopment/sonar/standard",
    "out/jonesdevelopment/sonar/legacy",
    "out/jonesdevelopment/sonar/complex",
    "out_ru/BotFilter/map",
    "out_ru/CaptchaVerifyZ/map",
    "out/laforetbrut/are-you-sure/code",
    "out/JSH32/Minecaptcha/map",
]

# Types that are not OCR tasks at all (group C). They are never trained on and never
# evaluated; the reason for each is in `reports/TRAINING_PPOCR_V6.md`.
GROUP_C = [
    "out/Archy-X/Krypton/menu",                # answer = a material name, nothing is drawn
    "out/China2B2T/Captcha/wool",              # one constant answer
    "out/FeelingAlive0/AdvancedCaptcha/button",  # the band carries a phrase, not the answer
    "out/Joey61021/captcha/colorgui",          # answer = a colour name
    "out/LagBug/XProtect/color",               # answer = a colour name
    "out/LagBug/XProtect/different",           # one constant answer
    "out/LagBug/XProtect/drop",                # one constant answer
    "out/LagBug/XProtect/jump",                # one constant answer
    "out/LagBug/XProtect/slot",                # the band carries the slot number
    "out/LagBug/XProtect/sneak",               # one constant answer
    "out/Z4OLLIEZ4/reCaptcha/captchasx",       # answer = a colour name
    "out/jSdCool/minecaptcha/image",           # 63-70 characters, unreadable by construction
    "out_ru/GalleryCaptcha/ru-object-swatch",  # answer = a colour name
    "out_ru/CaptchaGUI/clickblock",           # 7 unique pictures, the answer is a slot number
    "out_ru/LimboFilter/framed2x2",           # words in rotated frames
    "out_ru/LimboFilter/framed3x3",           # words in rotated frames
]


# --------------------------------------------------------------------------- #
# the normalisation of a prediction
# --------------------------------------------------------------------------- #
def norm(s):
    """Keep letters and digits of any script plus the arithmetic operators, drop the rest.

    The same normalisation as `bench/bench_models.py`: it is what the score is
    computed on, so both fine-tunes have to use it.
    """
    if s is None:
        return ""
    return "".join(ch for ch in str(s) if ch.isalnum() or ch in "+-*/=")


# --------------------------------------------------------------------------- #
# the metrics
# --------------------------------------------------------------------------- #
def aggregate(per_type, cer_micro_over="all", empty_items=None):
    """The aggregate is the MEDIAN over types, not the mean.

    `cer_micro_over`:
      * ``all`` - the micro CER is weighted by **every** image (PP-OCRv6's rule);
      * ``cer``  - only by the images whose CER is defined (TrOCR's rule).

    `empty_items` is the value of the ``items`` key of the *empty* aggregate, or
    ``None`` when the key is not part of it.
    """
    if not per_type:
        out = {"types": 0}
        if empty_items is not None:
            out["items"] = empty_items
        out.update({"exact_match_median": None, "cer_median": None,
                    "exact_match_micro": None, "cer_micro": None})
        return out
    accs = [v["exact_match"] for v in per_type.values()]
    cers = [v["cer"] for v in per_type.values() if v["cer"] is not None]
    n = sum(v["n"] for v in per_type.values())
    ex = sum(v["exact_match"] * v["n"] for v in per_type.values())
    cn = sum(v["n"] for v in per_type.values() if v["cer"] is not None)
    cs = sum(v["cer"] * v["n"] for v in per_type.values() if v["cer"] is not None)
    if cer_micro_over == "cer":
        micro_cer = round(cs / max(cn, 1), 4) if cn else None
    else:
        micro_cer = round(cs / max(n, 1), 4)
    return {
        "types": len(per_type),
        "items": n,
        "exact_match_median": round(statistics.median(accs), 4),
        "cer_median": round(statistics.median(cers), 4) if cers else None,
        "exact_match_micro": round(ex / max(n, 1), 4),
        "cer_micro": micro_cer,
    }


def print_per_type(per_type, title, agg_fn, precision=3):
    """Print the per-type table and the aggregate; return the aggregate."""
    print(f"--- {title} ---")
    for t in sorted(per_type):
        v = per_type[t]
        c = v["cer"] if v["cer"] is not None else float("nan")
        print(f"  {t:48s} n={v['n']:4d} exact={v['exact_match']:.{precision}f} cer={c:.{precision}f}")
    agg = agg_fn(per_type)
    print(f"  MEDIAN over {agg['types']} types: exact={agg['exact_match_median']} "
          f"cer={agg['cer_median']}  (micro: exact={agg['exact_match_micro']} cer={agg['cer_micro']})")
    return agg


def accumulate_type(per_type, t, pred, gold):
    """Add one prediction to the per-type counters (the normalised comparison)."""
    p, g = norm(pred), norm(gold)
    d = per_type.setdefault(t, {"n": 0, "exact": 0, "exact_raw": 0, "cer": []})
    d["n"] += 1
    d["exact"] += int(p == g)
    d["exact_raw"] += int(pred == gold)
    c = cer(p, g)
    if c is not None:
        d["cer"].append(c)
    return d


def finalise_per_type(per_type):
    """The per-type counters -> the block that goes into `result.json`."""
    out = {}
    for t, d in per_type.items():
        out[t] = {
            "n": d["n"],
            "exact_match": round(d["exact"] / d["n"], 4),
            "exact_match_raw": round(d["exact_raw"] / d["n"], 4),
            "cer": round(statistics.fmean(d["cer"]), 4) if d["cer"] else None,
        }
    return out


# --------------------------------------------------------------------------- #
# the split
# --------------------------------------------------------------------------- #
def discover_types(roots):
    """Every dataset type under the roots, and their per-type statistics."""
    types = find_types(roots)
    stats = {s["type"]: s for s in type_stats(types)}
    return types, stats


def build_split(types, stats, args, group_c, keep_type):
    """Decide, per type, whether it is trained on, evaluated, or dropped - and why.

    `keep_type(st)` is the model's own rule: it returns ``(True, None)`` for a type
    that trains and ``(False, reason)`` for one that does not. Everything before it -
    the held-out types, the excluded types and group C - is the same in both runs.
    """
    def matches(tid, patterns):
        return any(p in tid for p in patterns)

    train_types, val_types, dropped = [], [], []
    for tid, directory in types:
        st = stats[tid]
        if matches(tid, args.val_types):
            val_types.append((tid, directory))
            continue
        if matches(tid, args.exclude_types):
            dropped.append((tid, "excluded by --exclude-types"))
            continue
        if tid in group_c:
            dropped.append((tid, "group C: not an OCR task"))
            continue
        keep, why = keep_type(st)
        if not keep:
            dropped.append((tid, why))
            continue
        train_types.append((tid, directory))
    return train_types, val_types, dropped, stats


# --------------------------------------------------------------------------- #
# the run's bookkeeping
# --------------------------------------------------------------------------- #
def seed_everything(seed):
    """Seed python, numpy and torch (CPU and CUDA) - the run has to be repeatable."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def pick_device(spec):
    """`auto` -> CUDA when it is there, `cuda`/`cpu` -> exactly that."""
    if spec == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device("cuda" if spec == "cuda" else spec)


def open_log(out_dir):
    """The run's `log.txt` and the `log()` that writes to it and to the console.

    The file is opened in append mode: a resumed run adds to the log of the run it
    continues.
    """
    log_path = os.path.join(out_dir, "log.txt")
    log_f = open(log_path, "a", encoding="utf-8")

    def log(msg):
        print(msg, flush=True)
        log_f.write(str(msg) + "\n")
        log_f.flush()

    return log, log_f


def runtime_block(t_start, step_times, img_times, extra=None):
    """The `runtime` block of `result.json` - the same four numbers in both runs."""
    out = {
        "seconds": round(time.time() - t_start, 1),
        "minutes": round((time.time() - t_start) / 60.0, 2),
        "img_per_s": round(sum(img_times) / max(sum(step_times), 1e-9), 1),
        "step_ms": round(1000 * sum(step_times) / max(len(step_times), 1), 1),
    }
    if extra:
        out.update(extra)
    return out
