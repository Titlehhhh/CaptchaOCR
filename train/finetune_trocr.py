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

import argparse
import json
import math
import os
import random
import statistics
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

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

from ppocr_data import (PPOCRDataset, build_eval_items, build_items, cer, find_types,  # noqa: E402
                        read_labels, type_stats)


def norm(s):
    """Keep letters and digits of any script plus the arithmetic operators, drop the rest.

    Copied verbatim from `train/finetune_ppocr.py` so that the two runs score the
    strings with exactly the same normalisation.
    """
    if s is None:
        return ""
    return "".join(ch for ch in str(s) if ch.isalnum() or ch in "+-*/=")

DEFAULT_MODEL = "microsoft/trocr-small-printed"

# The held-out types: whole plugins, five plugins, seven types. This is the SAME list as
# `train/finetune_ppocr.py` (Variant 1 of `reports/research3/DATASET_AUDIT.md`), so the
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

# Types that are not OCR tasks at all (group C). Never trained on, never evaluated.
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
    if not per_type:
        return {"types": 0, "items": 0, "exact_match_median": None, "cer_median": None,
                "exact_match_micro": None, "cer_micro": None}
    accs = [v["exact_match"] for v in per_type.values()]
    cers = [v["cer"] for v in per_type.values() if v["cer"] is not None]
    n = sum(v["n"] for v in per_type.values())
    ex = sum(v["exact_match"] * v["n"] for v in per_type.values())
    cn = sum(v["n"] for v in per_type.values() if v["cer"] is not None)
    cs = sum(v["cer"] * v["n"] for v in per_type.values() if v["cer"] is not None)
    return {
        "types": len(per_type),
        "items": n,
        "exact_match_median": round(statistics.median(accs), 4),
        "cer_median": round(statistics.median(cers), 4) if cers else None,
        "exact_match_micro": round(ex / max(n, 1), 4),
        "cer_micro": round(cs / max(cn, 1), 4) if cn else None,
    }


def print_per_type(per_type, title):
    print(f"--- {title} ---")
    for t in sorted(per_type):
        v = per_type[t]
        c = v["cer"] if v["cer"] is not None else float("nan")
        print(f"  {t:48s} n={v['n']:4d} exact={v['exact_match']:.4f} cer={c:.4f}")
    agg = aggregate(per_type)
    print(f"  MEDIAN over {agg['types']} types: exact={agg['exact_match_median']} "
          f"cer={agg['cer_median']}  (micro: exact={agg['exact_match_micro']} cer={agg['cer_micro']})")
    return agg


# --------------------------------------------------------------------------- #
# the split
# --------------------------------------------------------------------------- #
def build_split(args):
    """Decide, per type, whether it is trained on, evaluated, or dropped - and why."""
    roots = [os.path.join(ROOT, "dataset", "out"), os.path.join(ROOT, "dataset", "out_ru")]
    types = find_types(roots)
    stats = {s["type"]: s for s in type_stats(types)}

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
        if tid in GROUP_C:
            dropped.append((tid, "group C: not an OCR task"))
            continue
        if st["n_roi"] == 0:
            dropped.append((tid, "no band (roi = null): not a recognition target"))
            continue
        if not args.allow_cyrillic:
            if not is_ascii_alphabet(st["alphabet"]):
                outside = sorted(set(st["alphabet"]) - LATIN_ALLOWED)
                dropped.append((tid, "label outside the ASCII alphabet: "
                                + "".join(c if ord(c) < 128 else f"<U+{ord(c):04X}>"
                                          for c in outside)))
                continue
        train_types.append((tid, directory))
    return train_types, val_types, dropped, stats


def charset_report(types, tokenizer):
    """How much of the dataset the model's own vocabulary can actually spell.

    A character the tokenizer cannot represent is silently dropped by the tokenizer, so
    the model would be taught to emit nothing for it. The number is reported, not hidden.
    """
    rows = []
    ok_chars, bad_chars = 0, 0
    for tid, directory in types:
        rowsl = read_labels(directory)
        texts = [(r.get("text") or "") for r in rowsl]
        bad = set()
        n_bad_labels = 0
        for t in texts:
            if not t:
                continue
            # round-trip: does the tokenizer spell the string back exactly?
            ids = tokenizer(t)["input_ids"]
            if tokenizer.decode(ids, skip_special_tokens=True) != t:
                n_bad_labels += 1
                bad.update(c for c in t if ord(c) >= 128)
        for t in texts:
            for c in t:
                ok_chars += 1
                bad_chars += int(ord(c) >= 128)
        rows.append({"type": tid, "n": len(texts), "labels_not_roundtripping": n_bad_labels,
                     "non_latin_chars": "".join(sorted(bad))})
    return {
        "per_type": rows,
        "chars_total": ok_chars,
        "chars_non_latin": bad_chars,
        "fraction_latin": round((ok_chars - bad_chars) / max(ok_chars, 1), 6),
        "note": ("TrOCR's tokenizer is the checkpoint's own XLMRobertaTokenizer (64 002 "
                 "sentencepiece pieces); it can spell Cyrillic as well, but the four "
                 "Cyrillic types are excluded to keep the training set identical to the "
                 "PP-OCRv6 run, whose dictionary has no Cyrillic at all."),
    }


# --------------------------------------------------------------------------- #
# the dataset
# --------------------------------------------------------------------------- #
class TrOCRDataset(torch.utils.data.Dataset):
    """Band crop -> (optional augmentation) -> the processor's own image processor.

    The crop and the augmentation are the ones of `train/ppocr_data.py` (re-used, not
    re-implemented): crop by `roi`; for a sample without a band crop to the ink bounding
    box; JPEG / WEBP recompression and brightness / contrast jitter on the training set.
    Only the last step - the resize to 384x384 and the normalisation - is TrOCR's.
    """

    def __init__(self, items, processor, augment=False, seed=0, strip_bos=True):
        self.items = items
        self.processor = processor
        self.augment = augment
        self.helpers = PPOCRDataset(items, vocab=None, augment=augment, seed=seed)
        self.seed = seed
        self.strip_bos = strip_bos

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        item = self.items[i]
        img = PPOCRDataset._load(item["path"], item["roi"])
        if item.get("roi") is None:
            x, y, w, h = PPOCRDataset.ink_bbox(img)
            img = img.crop((x, y, x + w, y + h))
        if self.augment:
            img = self.helpers._augment(img)
        # The image processor runs on the whole batch in the collate (one call instead
        # of one call per image): it is 4x faster that way and it is the same processor.
        return {"image": img, "type": item["type"], "index": i, "text": item["text"]}


def collate(batch, pad_token_id):
    """Deprecated helper kept for reference; the live path is `Collator` below."""
    px = torch.stack([b["pixel_values"] for b in batch])
    n = max(len(b["input_ids"]) for b in batch)
    ids = torch.full((len(batch), n), pad_token_id, dtype=torch.long)
    for i, b in enumerate(batch):
        ids[i, :len(b["input_ids"])] = b["input_ids"]
    labels = ids.masked_fill(ids == pad_token_id, -100)
    return {
        "pixel_values": px,
        "input_ids": ids,
        "labels": labels,
        "types": [b["type"] for b in batch],
        "indices": [b["index"] for b in batch],
    }


class Collator:
    """A picklable `collate_fn` (a lambda cannot be pickled by the DataLoader workers).

    The image processor and the tokenizer both run here, on the whole batch at once.
    """

    def __init__(self, pad_token_id, image_processor, tokenizer, strip_bos=True):
        self.pad_token_id = pad_token_id
        self.image_processor = image_processor
        self.tokenizer = tokenizer
        self.strip_bos = strip_bos
        self.bos_id = tokenizer.bos_token_id

    def __call__(self, batch):
        px = self.image_processor(images=[b["image"] for b in batch],
                                  return_tensors="pt")["pixel_values"]
        texts = [b["text"] for b in batch]
        enc = self.tokenizer(texts, padding=True, return_tensors="pt")["input_ids"]
        ids = enc.tolist()
        if self.strip_bos:
            # The pretrained TrOCR decoder starts with `decoder_start_token_id` and then
            # produces the text tokens directly - the measured zero-step generation of
            # this checkpoint is `[2, <text>, 2]`, i.e. no <s> in the label sequence.
            # The tokenizer adds one, so it is stripped: the fine-tuning target then
            # matches the convention the checkpoint was pretrained with.
            for i, row in enumerate(ids):
                if len(row) > 1 and row[0] == self.bos_id:
                    ids[i] = row[1:]
        n = max(len(r) for r in ids)
        padded = torch.full((len(batch), n), self.pad_token_id, dtype=torch.long)
        for i, row in enumerate(ids):
            padded[i, :len(row)] = torch.tensor(row, dtype=torch.long)
        labels = padded.masked_fill(padded == self.pad_token_id, -100)
        return {
            "pixel_values": px,
            "input_ids": padded,
            "labels": labels,
            "types": [b["type"] for b in batch],
            "indices": [b["index"] for b in batch],
        }


def shift_tokens_right(input_ids, decoder_start_token_id, pad_token_id):
    """Label tokens shifted right for the decoder; -100 becomes the pad token."""
    shifted = input_ids.new_zeros(input_ids.shape)
    shifted[:, 1:] = input_ids[:, :-1].clone()
    shifted[:, 0] = decoder_start_token_id
    shifted[shifted == -100] = pad_token_id
    return shifted


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
@torch.no_grad()
def _generate(model, px, device, amp, max_new_tokens, tokenizer, sub_bs=8):
    """`model.generate` in sub-batches; on OOM the sub-batch is halved.

    The card is shared with other trainings, so an OOM here must never take somebody
    else's run down. The sub-batches are decoded one by one: the generated sequences
    have different lengths, so they cannot be concatenated into one tensor.
    """
    texts = []
    i = 0
    while i < px.shape[0]:
        chunk = px[i:i + sub_bs]
        while True:
            try:
                with torch.autocast("cuda", dtype=torch.float16,
                                    enabled=amp and device.type == "cuda"):
                    g = model.generate(pixel_values=chunk, max_new_tokens=max_new_tokens,
                                       do_sample=False, num_beams=1)
                break
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if chunk.shape[0] == 1:
                    raise
                chunk = chunk[:max(1, chunk.shape[0] // 2)]
                sub_bs = chunk.shape[0]
        texts.extend(tokenizer.batch_decode(g, skip_special_tokens=True))
        i += chunk.shape[0]
    return texts


@torch.no_grad()
def evaluate(model, loader, tokenizer, device, amp=True, max_new_tokens=24, sub_bs=8):
    """Per type: exact match and CER (both on the normalised strings)."""
    model.eval()
    per_type = {}
    for batch in loader:
        px = batch["pixel_values"].to(device, non_blocking=True)
        preds = _generate(model, px, device, amp, max_new_tokens, tokenizer, sub_bs=sub_bs)
        for i, t in enumerate(batch["types"]):
            gold = loader.dataset.items[batch["indices"][i]]["text"]
            p, g = norm(preds[i]), norm(gold)
            d = per_type.setdefault(t, {"n": 0, "exact": 0, "exact_raw": 0, "cer": []})
            d["n"] += 1
            d["exact"] += int(p == g)
            d["exact_raw"] += int(preds[i] == gold)
            c = cer(p, g)
            if c is not None:
                d["cer"].append(c)
    out = {}
    for t, d in per_type.items():
        out[t] = {
            "n": d["n"],
            "exact_match": round(d["exact"] / d["n"], 4),
            "exact_match_raw": round(d["exact_raw"] / d["n"], 4),
            "cer": round(statistics.fmean(d["cer"]), 4) if d["cer"] else None,
        }
    model.train()
    return out


# --------------------------------------------------------------------------- #
# the report (merges this run with the PP-OCRv6 run of the same held-out types)
# --------------------------------------------------------------------------- #
def read_ppocr_numbers(log_path, result_path):
    """The PP-OCRv6 numbers of `train/run_ppocr/big`, read from the files of that run."""
    out = {"source": None, "zero_step": None, "final": None}
    if os.path.isfile(result_path):
        with open(result_path, encoding="utf-8") as f:
            res = json.load(f)
        out["source"] = result_path
        out["model"] = res.get("model")
        out["runtime"] = res.get("runtime")
        out["train_items"] = res.get("split", {}).get("train_types")
        for key in ("zero_step", "final"):
            blk = res.get(key)
            if not blk:
                out[key] = None
                continue
            out[key] = {"held_out": blk.get("held_out"), "all": blk.get("all"),
                        "per_type": blk.get("per_type"),
                        "epoch": blk.get("epoch"), "step": blk.get("step"),
                        "seconds": blk.get("seconds")}
        out["history"] = res.get("history")
        return out
    if os.path.isfile(log_path):
        out["source"] = log_path
        zeros, finals = [], []
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("zero step:"):
                    zeros.append(line.strip())
                if line.startswith("epoch ") and "held-out median exact=" in line:
                    finals.append(line.strip())
        out["zero_step_log_lines"] = zeros
        out["final_log_lines"] = finals
    return out


def build_report(result_path, ppocr_log, ppocr_result, out_path, extra_eval=None):
    """Write `reports/TRAINING_TROCR_BIG.json`: TrOCR zero-step / fine-tuned next to PP-OCRv6."""
    with open(result_path, encoding="utf-8") as f:
        res = json.load(f)
    pp = read_ppocr_numbers(ppocr_log, ppocr_result)
    val_set = set(res["split"]["held_out_types"])
    # The evaluation of the first epoch (the best TrOCR checkpoint), produced by
    # `--eval-checkpoint`; the `result.json` of the run that followed it holds the
    # *second* epoch, which is worse.
    ep0 = None
    if extra_eval and os.path.isfile(extra_eval):
        with open(extra_eval, encoding="utf-8") as f:
            ep0 = json.load(f)

    def pct(x):
        return None if x is None else round(100.0 * x, 2)

    def table(per_type):
        rows = []
        for t in sorted(per_type):
            v = per_type[t]
            rows.append({"type": t, "n": v["n"],
                         "exact_match_pct": pct(v["exact_match"]),
                         "cer_pct": pct(v["cer"])})
        return rows

    def agg_block(agg):
        if not agg:
            return None
        return {"types": agg["types"], "items": agg["items"],
                "exact_match_median_pct": pct(agg["exact_match_median"]),
                "cer_median_pct": pct(agg["cer_median"]),
                "exact_match_micro_pct": pct(agg["exact_match_micro"]),
                "cer_micro_pct": pct(agg["cer_micro"])}

    trocr_zero = res["zero_step"]
    trocr_final = res["final"]
    # The best TrOCR checkpoint: the first epoch if it was evaluated separately,
    # otherwise the last run's final block.
    best_block = ep0 if ep0 else trocr_final
    best_per_type = (ep0 or {}).get("per_type") or trocr_final.get("per_type") or {}
    best_agg = (ep0 or {}).get("held_out") or trocr_final.get("held_out")
    pp_zero = (pp.get("zero_step") or {}).get("per_type") or {}
    pp_final = (pp.get("final") or {}).get("per_type") or {}

    side = []
    for t in res["split"]["held_out_types"]:
        tz = trocr_zero["per_type"].get(t, {})
        tf = best_per_type.get(t, {})
        pz = pp_zero.get(t, {})
        pf = pp_final.get(t, {})
        side.append({
            "type": t,
            "trocr_zero_step": {"exact_match_pct": pct(tz.get("exact_match")),
                                "cer_pct": pct(tz.get("cer"))},
            "trocr_finetuned": {"exact_match_pct": pct(tf.get("exact_match")),
                                "cer_pct": pct(tf.get("cer"))},
            "ppocr_v6_zero_step": {"exact_match_pct": pct(pz.get("exact_match")),
                                    "cer_pct": pct(pz.get("cer"))},
            "ppocr_v6_finetuned": {"exact_match_pct": pct(pf.get("exact_match")),
                                   "cer_pct": pct(pf.get("cer"))},
        })

    def agg_of(blk, key):
        if not blk:
            return None
        a = blk.get(key) or {}
        return {"types": a.get("types"), "items": a.get("items"),
                "exact_match_median_pct": pct(a.get("exact_match_median")),
                "cer_median_pct": pct(a.get("cer_median")),
                "exact_match_micro_pct": pct(a.get("exact_match_micro")),
                "cer_micro_pct": pct(a.get("cer_micro"))}

    report = {
        "title": "TrOCR-small-printed vs PP-OCRv6-medium-rec on the same 7 held-out captcha types",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "held_out_types": res["split"]["held_out_types"],
        "train_types": res["split"]["train_types"],
        "dropped_types": res["split"]["dropped"],
        "train_items": res["split"]["train_items"],
        "held_out_items": res["split"]["held_out_items"],
        "model": res["model"],
        "charset": res["charset"],
        "trocr_zero_step": {
            "held_out": agg_block(trocr_zero["held_out"]),
            "per_type": table(trocr_zero["per_type"]),
            "seconds": trocr_zero["seconds"],
        },
        "trocr_finetuned": {
            "held_out": agg_block(best_agg),
            "per_type": table(best_per_type),
            "epoch": (ep0 or {}).get("epoch", trocr_final.get("epoch")),
            "step": (ep0 or {}).get("step", trocr_final.get("step")),
            "checkpoint": (ep0 or {}).get("checkpoint") or "train/run/trocr_big/best.pt",
            "note": ("the BEST TrOCR checkpoint (epoch 0). The second epoch is worse - "
                     "see trocr_finetuned_epoch1."),
        },
        "trocr_finetuned_epoch1": {
            "held_out": agg_block(trocr_final["held_out"]),
            "per_type": table(trocr_final.get("per_type") or {}),
            "epoch": trocr_final.get("epoch"),
            "step": trocr_final.get("step"),
            "note": "the continuation run (--resume --epochs 2): one more epoch, worse",
        },
        "ppocr_v6": {
            "source": pp.get("source"),
            "runtime": pp.get("runtime"),
            "zero_step": {"held_out": agg_of(pp.get("zero_step"), "held_out"),
                          "per_type": table(pp_zero),
                          "seconds": (pp.get("zero_step") or {}).get("seconds")},
            "finetuned": {"held_out": agg_of(pp.get("final"), "held_out"),
                          "per_type": table(pp_final),
                          "epoch": (pp.get("final") or {}).get("epoch"),
                          "step": (pp.get("final") or {}).get("step")},
            "history": pp.get("history"),
        },
        "side_by_side_per_type": side,
        "runtime": res["runtime"],
        "history": res["history"],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    return report


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--eval-batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4, help="encoder learning rate")
    ap.add_argument("--decoder-lr", type=float, default=None,
                    help="decoder learning rate (default: same as --lr)")
    ap.add_argument("--weight-decay", type=float, default=0.01)
    ap.add_argument("--warmup-frac", type=float, default=0.05)
    ap.add_argument("--grad-clip", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit-per-type", type=int, default=None)
    ap.add_argument("--out", default=os.path.join("train", "run", "trocr_big"))
    ap.add_argument("--val-types", nargs="*", default=DEFAULT_VAL_TYPES)
    ap.add_argument("--exclude-types", nargs="*", default=[])
    ap.add_argument("--eval-types", nargs="*", default=None)
    ap.add_argument("--allow-cyrillic", action="store_true",
                    help="also train on the four Cyrillic types (NOT comparable to the PP-OCRv6 run)")
    ap.add_argument("--no-roi-mode", choices=("frame", "skip"), default="frame")
    ap.add_argument("--no-augment", action="store_true")
    ap.add_argument("--no-amp", action="store_true")
    ap.add_argument("--save-every", type=int, default=50, help="checkpoint every N steps")
    ap.add_argument("--eval-every", type=int, default=1, help="evaluate every N epochs")
    ap.add_argument("--max-minutes", type=float, default=None, help="stop after this many minutes")
    ap.add_argument("--max-new-tokens", type=int, default=24)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--fresh-sched", action="store_true",
                    help="with --resume: rebuild the LR schedule instead of restoring it")
    ap.add_argument("--skip-zero-step", action="store_true",
                    help="reuse the zero-step numbers of a previous run of this directory")
    ap.add_argument("--skip-final-eval", action="store_true",
                    help="do not re-evaluate the best checkpoint; reuse the last epoch's numbers")
    ap.add_argument("--eval-checkpoint", default=None,
                    help="evaluate this checkpoint on the held-out types and exit")
    ap.add_argument("--eval-out", default=None, help="where the --eval-checkpoint JSON goes")
    ap.add_argument("--zero-step", action="store_true", help="only measure the pretrained model")
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--report-only", action="store_true",
                    help="do not train; rebuild the report JSON from an existing run")
    ap.add_argument("--ppocr-log", default=os.path.join("train", "run_ppocr", "big", "log.txt"))
    ap.add_argument("--ppocr-result", default=os.path.join("train", "run_ppocr", "big", "result.json"))
    ap.add_argument("--report-json", default=os.path.join("reports", "TRAINING_TROCR_BIG.json"))
    args = ap.parse_args()

    def rooted(p):
        return p if os.path.isabs(p) else os.path.join(ROOT, p)

    out_dir = rooted(args.out)
    ckpt_dir = os.path.join(out_dir, "ckpt")
    os.makedirs(ckpt_dir, exist_ok=True)

    # -- report-only mode ----------------------------------------------------- #
    if args.report_only:
        rp = build_report(os.path.join(out_dir, "result.json"), rooted(args.ppocr_log),
                          rooted(args.ppocr_result), rooted(args.report_json),
                          extra_eval=os.path.join(out_dir, "eval_epoch0.json"))
        print(json.dumps({"trocr_zero_step": rp["trocr_zero_step"]["held_out"],
                          "trocr_finetuned": rp["trocr_finetuned"]["held_out"],
                          "ppocr_source": rp["ppocr_v6"].get("source")}, indent=1))
        print(f"written: {rooted(args.report_json)}")
        return

    t_start = time.time()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)

    device = torch.device("cuda" if (args.device == "auto" and torch.cuda.is_available())
                          else ("cuda" if args.device == "cuda" else args.device))
    log_path = os.path.join(out_dir, "log.txt")
    log_f = open(log_path, "a", encoding="utf-8")

    def log(msg):
        print(msg, flush=True)
        log_f.write(str(msg) + "\n")
        log_f.flush()

    log(f"=== TrOCR fine-tune === {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"args: {vars(args)}")
    log(f"device: {device}  torch {torch.__version__}")

    # -- model and processor -------------------------------------------------- #
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel, __version__ as tfm_version

    processor = TrOCRProcessor.from_pretrained(args.model)
    model = VisionEncoderDecoderModel.from_pretrained(args.model)
    tokenizer = processor.tokenizer
    # The checkpoint's own image processor. The torchvision backend is the same maths
    # (bicubic resize to 384x384, rescale, normalise with mean=std=0.5) and is ~4x
    # faster; the maximum difference against the PIL backend is 1/255 of a pixel step.
    image_processor = processor.image_processor
    try:
        from transformers import AutoImageProcessor
        fast_ip = AutoImageProcessor.from_pretrained(args.model, backend="torchvision")
        image_processor = fast_ip
        log("image processor: torchvision backend (the PIL backend is 4x slower)")
    except Exception as e:
        log(f"image processor: PIL backend ({e})")
    n_params = sum(p.numel() for p in model.parameters())
    pad_id = tokenizer.pad_token_id
    log(f"model: {args.model}  class=VisionEncoderDecoderModel  transformers {tfm_version}")
    log(f"params: {n_params}  encoder={model.config.encoder.model_type} "
        f"hidden={model.config.encoder.hidden_size} layers={model.config.encoder.num_hidden_layers} "
        f"image_size={model.config.encoder.image_size}  "
        f"decoder d_model={model.config.decoder.d_model} layers={model.config.decoder.decoder_layers} "
        f"vocab={model.config.decoder.vocab_size}")
    log(f"processor: {type(processor.image_processor).__name__} size="
        f"{processor.image_processor.size} mean={processor.image_processor.image_mean} "
        f"std={processor.image_processor.image_std}")
    log(f"tokenizer: {type(tokenizer).__name__} vocab={tokenizer.vocab_size} "
        f"pad={pad_id} bos={tokenizer.bos_token_id} eos={tokenizer.eos_token_id} "
        f"decoder_start={model.config.decoder.decoder_start_token_id}")

    # -- split ---------------------------------------------------------------- #
    train_types, val_types, dropped, stats = build_split(args)
    log("")
    log(f"TRAIN types ({len(train_types)}):")
    for tid, _ in train_types:
        log(f"   {tid:48s} n={stats[tid]['n_roi']:4d} alphabet={stats[tid]['alphabet'][:40]}")
    log(f"HELD-OUT types ({len(val_types)}):")
    for tid, _ in val_types:
        log(f"   {tid:48s} n={stats[tid]['n']:4d} with band={stats[tid]['n_roi']}")
    log(f"DROPPED types ({len(dropped)}):")
    for tid, why in dropped:
        log(f"   {tid:48s} {why}")
    log("")

    charset = charset_report(train_types + val_types, tokenizer)
    log(f"charset: {charset['chars_total']} label characters, "
        f"{charset['chars_non_latin']} outside the Latin alphabet "
        f"({charset['fraction_latin'] * 100:.2f}% Latin); "
        f"tokenizer round-trip failures: "
        f"{sum(r['labels_not_roundtripping'] for r in charset['per_type'])}")
    for r in charset["per_type"]:
        if r["labels_not_roundtripping"]:
            log(f"   NOT ROUND-TRIPPING: {r['type']:44s} n={r['n']} "
                f"bad={r['labels_not_roundtripping']} non_latin={r['non_latin_chars']!r}")

    train_items = build_items(train_types, limit_per_type=args.limit_per_type)
    eval_types = val_types
    if args.eval_types:
        wanted = set(args.eval_types)
        eval_types = [(t, d) for t, d in (val_types + train_types) if t in wanted]
    eval_items = build_eval_items(eval_types, limit_per_type=args.limit_per_type,
                                  no_roi_mode=args.no_roi_mode)
    val_items = build_eval_items(val_types, limit_per_type=args.limit_per_type,
                                 no_roi_mode=args.no_roi_mode)
    log(f"train items: {len(train_items)}   eval items: {len(eval_items)}   "
        f"held-out items: {len(val_items)}")

    train_ds = TrOCRDataset(train_items, processor, augment=not args.no_augment, seed=args.seed)
    eval_ds = TrOCRDataset(eval_items, processor, augment=False, seed=args.seed)

    def make_loader(ds, bs, shuffle):
        kw = dict(num_workers=args.workers, pin_memory=True, persistent_workers=args.workers > 0,
                  collate_fn=Collator(pad_id, image_processor, tokenizer))
        try:
            return DataLoader(ds, batch_size=bs, shuffle=shuffle, **kw)
        except Exception as e:  # pickling of the processor failed -> run in the main process
            log(f"DataLoader with {args.workers} workers failed ({e}); falling back to 0 workers")
            kw["num_workers"] = 0
            kw["persistent_workers"] = False
            return DataLoader(ds, batch_size=bs, shuffle=shuffle, **kw)

    train_loader = make_loader(train_ds, args.batch_size, True)
    eval_loader = make_loader(eval_ds, args.eval_batch_size, False)

    model.to(device)
    model.train()

    # -- evaluate one checkpoint and exit ------------------------------------- #
    if args.eval_checkpoint:
        ck = torch.load(rooted(args.eval_checkpoint), map_location="cpu", weights_only=False)
        state = ck.get("model", ck) if isinstance(ck, dict) else ck
        model.load_state_dict(state)
        model.eval()
        t0 = time.time()
        per_type = evaluate(model, eval_loader, tokenizer, device, amp=not args.no_amp,
                            max_new_tokens=args.max_new_tokens)
        val_per = {t: v for t, v in per_type.items() if t in {x[0] for x in val_types}}
        agg = aggregate(val_per)
        print_per_type(per_type, f"CHECKPOINT {args.eval_checkpoint}")
        out = {"checkpoint": os.path.abspath(rooted(args.eval_checkpoint)),
               "epoch": ck.get("epoch") if isinstance(ck, dict) else None,
               "step": ck.get("step") if isinstance(ck, dict) else None,
               "held_out": agg, "all": aggregate(per_type), "per_type": per_type,
               "seconds": round(time.time() - t0, 1)}
        if args.eval_out:
            with open(rooted(args.eval_out), "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=1)
            log(f"written: {rooted(args.eval_out)}")
        log(f"checkpoint eval: {out['seconds']}s  held-out median exact="
            f"{agg['exact_match_median']} cer={agg['cer_median']} "
            f"micro exact={agg['exact_match_micro']}")
        return

    # -- zero step ------------------------------------------------------------ #
    zero = None
    if args.skip_zero_step:
        prev = os.path.join(out_dir, "result.json")
        prev_zero = None
        if os.path.isfile(prev):
            with open(prev, encoding="utf-8") as f:
                prev_zero = json.load(f).get("zero_step")
        if prev_zero is None:
            zf = os.path.join(out_dir, "zero_step.json")
            if os.path.isfile(zf):
                with open(zf, encoding="utf-8") as f:
                    prev_zero = json.load(f).get("zero_step")
        zero = prev_zero
        log(f"zero step: reused from a previous run of this directory: "
            f"held-out median exact={zero['held_out']['exact_match_median']} "
            f"cer={zero['held_out']['cer_median']}" if zero else "zero step: nothing to reuse")
    elif not args.eval_only or args.zero_step:
        t0 = time.time()
        per_type = evaluate(model, eval_loader, tokenizer, device, amp=not args.no_amp,
                            max_new_tokens=args.max_new_tokens)
        zero = {"per_type": per_type,
                "held_out": aggregate({t: v for t, v in per_type.items()
                                       if t in {x[0] for x in val_types}}),
                "all": aggregate(per_type),
                "seconds": round(time.time() - t0, 1)}
        print_per_type(per_type, "ZERO STEP (pretrained, before any training)")
        log(f"zero step: {zero['seconds']}s  held-out median exact="
            f"{zero['held_out']['exact_match_median']} cer={zero['held_out']['cer_median']}")

    if args.zero_step and not args.eval_only:
        json.dump({"zero_step": zero}, open(os.path.join(out_dir, "zero_step.json"), "w",
                                            encoding="utf-8"), ensure_ascii=False, indent=1)
        log("zero step only - stopping.")
        return

    # -- training ------------------------------------------------------------- #
    dec_lr = args.decoder_lr if args.decoder_lr is not None else args.lr
    enc_params = list(model.encoder.parameters())
    dec_params = list(model.decoder.parameters())
    optimizer = torch.optim.AdamW(
        [{"params": enc_params, "lr": args.lr},
         {"params": dec_params, "lr": dec_lr}],
        weight_decay=args.weight_decay)
    steps_per_epoch = max(1, len(train_loader))
    total_steps = steps_per_epoch * args.epochs
    warmup = max(1, int(total_steps * args.warmup_frac))

    def lr_lambda(step):
        if step < warmup:
            return (step + 1) / warmup
        prog = (step - warmup) / max(1, total_steps - warmup)
        return max(0.0, 0.5 * (1.0 + math.cos(math.pi * min(1.0, prog))))

    sched = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    scaler = torch.amp.GradScaler("cuda", enabled=not args.no_amp and device.type == "cuda")

    start_epoch = 0
    global_step = 0
    if args.resume:
        cks = sorted([f for f in os.listdir(ckpt_dir)
                      if (f.startswith("step_") or f == "final.pt") and f.endswith(".pt")])
        if cks:
            ck = torch.load(os.path.join(ckpt_dir, cks[-1]), map_location="cpu", weights_only=False)
            model.load_state_dict(ck["model"])
            optimizer.load_state_dict(ck["optimizer"])
            if args.fresh_sched:
                log("resumed with a FRESH learning-rate schedule (the restored one had "
                    "already annealed to zero)")
            else:
                sched.load_state_dict(ck["sched"])
            scaler.load_state_dict(ck["scaler"])
            start_epoch = ck["epoch"] + 1
            global_step = ck["step"]
            log(f"resumed from {cks[-1]} (epoch {start_epoch}, step {global_step})")
        else:
            log(f"--resume: no checkpoint in {ckpt_dir}, starting from the pretrained model")

    log(f"training: {args.epochs} epochs x {steps_per_epoch} steps = {total_steps} steps, "
        f"lr={args.lr}/{dec_lr}, batch={args.batch_size}, amp={not args.no_amp}, "
        f"warmup={warmup}")
    best = {"score": -1.0, "epoch": -1, "step": -1}
    history = []
    step_times = []
    img_times = []
    stop = False
    oom = 0
    last_epoch = start_epoch - 1

    for epoch in range(start_epoch, args.epochs):
        t_ep = time.time()
        last_epoch = epoch
        running, nb = 0.0, 0
        for batch in train_loader:
            px = batch["pixel_values"].to(device, non_blocking=True)
            labels = batch["labels"].to(device, non_blocking=True)
            dec_in = shift_tokens_right(labels, model.config.decoder.decoder_start_token_id, pad_id)
            bs = px.shape[0]
            t0 = time.time()
            try:
                with torch.autocast("cuda", dtype=torch.float16,
                                    enabled=not args.no_amp and device.type == "cuda"):
                    out = model(pixel_values=px, decoder_input_ids=dec_in)
                logits = out.logits
                loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)).float(),
                                       labels.reshape(-1), ignore_index=-100)
                optimizer.zero_grad(set_to_none=True)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
                scale_before = scaler.get_scale()
                scaler.step(optimizer)
                scaler.update()
            except torch.cuda.OutOfMemoryError as e:
                # The card is shared: never kill another agent's run. Give the memory
                # back, wait a moment and try the next batch with a smaller one.
                oom += 1
                log(f"  OOM at step {global_step} (batch {bs}): {str(e)[:200]}")
                optimizer.zero_grad(set_to_none=True)
                del px, dec_in, labels
                torch.cuda.empty_cache()
                time.sleep(20)
                if oom >= 3:
                    log("  3 OOMs in a row - stopping the training loop")
                    stop = True
                    break
                continue
            if scaler.get_scale() >= scale_before:
                sched.step()
            global_step += 1
            running += float(loss.item())
            nb += 1
            step_times.append(time.time() - t0)
            img_times.append(bs)
            if global_step % 20 == 0:
                el = time.time() - t_ep
                log(f"  epoch {epoch} step {global_step}/{total_steps} loss={running/max(nb,1):.4f} "
                    f"lr={sched.get_last_lr()[0]:.2e} {el:.1f}s "
                    f"img/s={sum(img_times)/max(sum(step_times),1e-9):.1f}")
            if global_step % args.save_every == 0:
                torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                            "sched": sched.state_dict(), "scaler": scaler.state_dict(),
                            "epoch": epoch, "step": global_step, "args": vars(args)},
                           os.path.join(ckpt_dir, f"step_{global_step:06d}.pt"))
            if args.max_minutes and (time.time() - t_start) / 60.0 > args.max_minutes:
                log(f"  time budget reached ({args.max_minutes} min) - stopping")
                stop = True
                break

        ep_time = time.time() - t_ep
        avg_loss = running / max(nb, 1)
        ips = sum(img_times) / max(sum(step_times), 1e-9)
        log(f"epoch {epoch}: loss={avg_loss:.4f}  {ep_time:.1f}s  {ips:.1f} img/s  "
            f"step={step_times[-1]*1000 if step_times else 0:.0f}ms")

        last = (epoch == args.epochs - 1) or stop or (epoch + 1) % args.eval_every == 0
        if last:
            per_type = evaluate(model, eval_loader, tokenizer, device, amp=not args.no_amp,
                                max_new_tokens=args.max_new_tokens)
            val_per = {t: v for t, v in per_type.items() if t in {x[0] for x in val_types}}
            agg = aggregate(val_per)
            print_per_type(per_type, f"EPOCH {epoch} (held-out types are the {len(val_per)} marked ones)")
            log(f"epoch {epoch}: held-out median exact={agg['exact_match_median']} "
                f"cer={agg['cer_median']}  micro exact={agg['exact_match_micro']}")
            history.append({"epoch": epoch, "step": global_step, "loss": round(avg_loss, 5),
                            "held_out": agg, "per_type": per_type,
                            "epoch_seconds": round(ep_time, 1)})
            score = agg["exact_match_median"] or 0.0
            if score > best["score"]:
                best = {"score": score, "epoch": epoch, "step": global_step}
                torch.save({"model": model.state_dict(), "epoch": epoch, "step": global_step,
                            "args": vars(args)}, os.path.join(out_dir, "best.pt"))
                log(f"  new best held-out median exact={score} -> {out_dir}/best.pt")
        if stop:
            break

    # A complete, resumable state: model + optimiser + scheduler + scaler + step.
    final_state = {"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                   "sched": sched.state_dict(), "scaler": scaler.state_dict(),
                   "epoch": last_epoch, "step": global_step,
                   "args": vars(args)}
    torch.save(final_state, os.path.join(ckpt_dir, "final.pt"))
    log(f"resumable checkpoint written: {ckpt_dir}/final.pt (epoch {final_state['epoch']}, "
        f"step {final_state['step']})")

    # -- final evaluation of the best checkpoint ------------------------------ #
    final = None
    if args.skip_final_eval and history:
        h = history[-1]
        final = {"per_type": h["per_type"], "held_out": h["held_out"],
                 "all": aggregate(h["per_type"]), "epoch": h["epoch"], "step": h["step"]}
        print_per_type(h["per_type"], f"FINAL (last epoch {h['epoch']}, --skip-final-eval)")
    else:
        best_path = os.path.join(out_dir, "best.pt")
        if os.path.isfile(best_path):
            ck = torch.load(best_path, map_location="cpu", weights_only=False)
            model.load_state_dict(ck["model"])
            per_type = evaluate(model, eval_loader, tokenizer, device, amp=not args.no_amp,
                                max_new_tokens=args.max_new_tokens)
            val_per = {t: v for t, v in per_type.items() if t in {x[0] for x in val_types}}
            final = {"per_type": per_type, "held_out": aggregate(val_per),
                     "all": aggregate(per_type), "epoch": ck["epoch"], "step": ck["step"]}
            print_per_type(per_type, f"FINAL (best checkpoint, epoch {ck['epoch']})")
        else:
            per_type = evaluate(model, eval_loader, tokenizer, device, amp=not args.no_amp,
                                max_new_tokens=args.max_new_tokens)
            val_per = {t: v for t, v in per_type.items() if t in {x[0] for x in val_types}}
            final = {"per_type": per_type, "held_out": aggregate(val_per),
                     "all": aggregate(per_type), "epoch": None, "step": None}
            print_per_type(per_type, "FINAL (last epoch, no best checkpoint)")

    result = {
        "config": vars(args),
        "model": {"repo": args.model, "params": n_params,
                  "transformers": tfm_version, "torch": torch.__version__,
                  "decoder_vocab": model.config.decoder.vocab_size,
                  "tokenizer_vocab": tokenizer.vocab_size,
                  "pad_id": pad_id,
                  "decoder_start_token_id": model.config.decoder.decoder_start_token_id,
                  "input": "384x384 RGB, the processor's own DeiTImageProcessor"},
        "split": {"train_types": [t for t, _ in train_types],
                  "held_out_types": [t for t, _ in val_types],
                  "dropped": {t: w for t, w in dropped},
                  "train_items": len(train_items),
                  "held_out_items": len(val_items)},
        "charset": charset,
        "zero_step": zero,
        "final": final,
        "history": history,
        "runtime": {"seconds": round(time.time() - t_start, 1),
                    "minutes": round((time.time() - t_start) / 60.0, 2),
                    "img_per_s": round(sum(img_times) / max(sum(step_times), 1e-9), 1),
                    "step_ms": round(1000 * sum(step_times) / max(len(step_times), 1), 1),
                    "epochs_done": len(history)},
    }
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    log(f"done in {result['runtime']['minutes']} min -> {out_dir}/result.json")
    log_f.close()


if __name__ == "__main__":
    main()
