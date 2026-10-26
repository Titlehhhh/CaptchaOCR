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

import argparse
import json
import os
import random
import statistics
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# The machine's shared Hugging Face cache is read-only for child processes, so the
# cache has to point into the workspace before anything touches the hub.
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".hf-cache"))
os.environ.setdefault("HF_HUB_CACHE", os.path.join(ROOT, ".hf-cache", "hub"))

from ppocr_data import (MAX_WIDTH, PPOCRDataset, Vocab, build_eval_items,  # noqa: E402
                        build_items, cer, collate, find_types, levenshtein, read_labels,
                        type_stats)

DEFAULT_MODEL = "PaddlePaddle/PP-OCRv6_medium_rec_safetensors"

# The held-out types: whole plugins, five plugins, seven types (Variant 1 of
# `reports/research3/DATASET_AUDIT.md`).
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
    "out_ru/GalleryCaptcha/ru-object-swatch",     # answer = a colour name
    "out_ru/CaptchaGUI/clickblock",           # 7 unique pictures, the answer is a slot number
    "out_ru/LimboFilter/framed2x2",           # words in rotated frames
    "out_ru/LimboFilter/framed3x3",           # words in rotated frames
]


# --------------------------------------------------------------------------- #
# metrics (the same normalisation as `bench/bench_models.py`)
# --------------------------------------------------------------------------- #
def norm(s):
    """Keep letters and digits of any script plus the arithmetic operators, drop the rest."""
    if s is None:
        return ""
    return "".join(ch for ch in str(s) if ch.isalnum() or ch in "+-*/=")


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
        if st["n_roi"] == 0 and not args.train_frames:
            dropped.append((tid, "no band (roi = null): not a recognition target "
                                 "(pass --train-frames to train them as full frames)"))
            continue
        alphabet = st["alphabet"]
        missing = sorted(set(alphabet) - set(vocab.table))
        if missing:
            dropped.append((tid, "label outside the model dictionary: " + "".join(missing)))
            continue
        train_types.append((tid, directory))
    return train_types, val_types, dropped, stats


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
            gold = item["text"]
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


def aggregate(per_type):
    """The aggregate is the MEDIAN over types, not the mean."""
    if not per_type:
        return {"types": 0, "exact_match_median": None, "cer_median": None,
                "exact_match_micro": None, "cer_micro": None}
    accs = [v["exact_match"] for v in per_type.values()]
    cers = [v["cer"] for v in per_type.values() if v["cer"] is not None]
    n = sum(v["n"] for v in per_type.values())
    ex = sum(v["exact_match"] * v["n"] for v in per_type.values())
    cs = sum(v["cer"] * v["n"] for v in per_type.values() if v["cer"] is not None)
    return {
        "types": len(per_type),
        "items": n,
        "exact_match_median": round(statistics.median(accs), 4),
        "cer_median": round(statistics.median(cers), 4) if cers else None,
        "exact_match_micro": round(ex / max(n, 1), 4),
        "cer_micro": round(cs / max(n, 1), 4),
    }


def print_per_type(per_type, title):
    print(f"--- {title} ---")
    for t in sorted(per_type):
        v = per_type[t]
        print(f"  {t:48s} n={v['n']:4d} exact={v['exact_match']:.3f} "
              f"cer={(v['cer'] if v['cer'] is not None else float('nan')):.3f}")
    agg = aggregate(per_type)
    print(f"  MEDIAN over {agg['types']} types: exact={agg['exact_match_median']} "
          f"cer={agg['cer_median']}  (micro: exact={agg['exact_match_micro']} cer={agg['cer_micro']})")
    return agg


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4, help="backbone learning rate")
    ap.add_argument("--head-lr", type=float, default=1e-4, help="head learning rate")
    ap.add_argument("--weight-decay", type=float, default=0.01)
    ap.add_argument("--grad-clip", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit-per-type", type=int, default=None)
    ap.add_argument("--out", default=os.path.join("train", "run_ppocr", "run"))
    ap.add_argument("--val-types", nargs="*", default=DEFAULT_VAL_TYPES)
    ap.add_argument("--exclude-types", nargs="*", default=[])
    ap.add_argument("--include-types", nargs="*", default=None)
    ap.add_argument("--eval-types", nargs="*", default=None,
                    help="types to evaluate (default: the held-out ones plus the trained ones)")
    ap.add_argument("--no-roi-mode", choices=("frame", "content", "skip"), default="frame",
                    help="how a type without a band is evaluated (the bench used 'frame')")
    ap.add_argument("--holdout-per-type", type=int, default=0,
                    help="0 = off. When N > 0, the FIRST N items of every trained type go to the "
                         "evaluation set and the type still trains on the rest: the evaluation is "
                         "per unseen SAMPLE, nearly all images train")
    ap.add_argument("--train-frames", action="store_true",
                    help="do not drop the types without a band: train them on the whole frame "
                         "(the same crop build_eval_items(no_roi_mode='frame') uses). Group C is "
                         "still dropped")
    ap.add_argument("--norm", choices=("paddle", "imagenet"), default="paddle")
    ap.add_argument("--glyph-scale", choices=("band", "glyph"), default="band")
    ap.add_argument("--no-augment", action="store_true")
    ap.add_argument("--no-amp", action="store_true")
    ap.add_argument("--save-every", type=int, default=100, help="checkpoint every N steps")
    ap.add_argument("--eval-every", type=int, default=2, help="evaluate every N epochs")
    ap.add_argument("--max-minutes", type=float, default=None, help="stop after this many minutes")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--init-from", default=None,
                    help="start from the weights of this checkpoint (model only; a fresh "
                         "optimiser and a fresh OneCycleLR schedule are created). Use it to "
                         "continue a finished run with a new, gentler schedule.")
    ap.add_argument("--expand-charset", action="store_true",
                    help="expand the CTC dictionary with the characters missing from the "
                         "pretrained one (the Cyrillic) found in the training labels, and grow "
                         "the head's output layer accordingly - so the previously dropped Cyrillic "
                         "types become trainable")
    ap.add_argument("--zero-step", action="store_true", help="only measure the pretrained model")
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--device", default="auto")
    args = ap.parse_args()

    t_start = time.time()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)

    device = torch.device("cuda" if (args.device == "auto" and torch.cuda.is_available())
                          else ("cuda" if args.device == "cuda" else args.device))
    out_dir = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    ckpt_dir = os.path.join(out_dir, "ckpt")
    os.makedirs(ckpt_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "log.txt")
    log_f = open(log_path, "a", encoding="utf-8")

    def log(msg):
        print(msg, flush=True)
        log_f.write(str(msg) + "\n")
        log_f.flush()

    log(f"=== PP-OCRv6 fine-tune === {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"args: {vars(args)}")
    log(f"device: {device}  torch {torch.__version__}")

    # -- model ---------------------------------------------------------------- #
    from transformers import PPOCRV6SmallRecForTextRecognition, __version__ as tfm_version

    model = PPOCRV6SmallRecForTextRecognition.from_pretrained(args.model)
    n_params = sum(p.numel() for p in model.parameters())
    log(f"model: {args.model}  class=PPOCRV6SmallRecForTextRecognition  transformers {tfm_version}")
    log(f"params: {n_params}  model_type={model.config.model_type} "
        f"hidden_size={model.config.hidden_size} head_out_channels={model.config.head_out_channels} "
        f"backbone={model.config.backbone_config.model_type}")

    ckpt_char_list = None
    if args.init_from:
        # start from the weights of another checkpoint (model only); the optimiser and the
        # OneCycleLR schedule are created fresh. The zero step below then measures THAT model.
        init_ck = torch.load(args.init_from, map_location="cpu", weights_only=False)
        # a checkpoint may carry a larger head than the pretrained config (an --expand-charset
        # run): grow the model's head to match BEFORE load_state_dict, so the rows land in.
        init_w = init_ck["model"].get("head.head.weight")
        if init_w is not None:
            old_head = model.head.head
            if init_w.shape[0] != old_head.out_features:
                grown = nn.Linear(old_head.in_features, init_w.shape[0], bias=True)
                model.head.head = grown
        model.load_state_dict(init_ck["model"])
        ckpt_char_list = init_ck.get("character_list")
        log(f"initialised the weights from {args.init_from} "
            f"(epoch={init_ck.get('epoch')} step={init_ck.get('step')})")

    # -- the model's own dictionary ------------------------------------------- #
    from huggingface_hub import hf_hub_download
    proc_path = hf_hub_download(args.model, "preprocessor_config.json")
    proc = json.load(open(proc_path, encoding="utf-8"))
    vocab = Vocab(proc["character_list"])
    if ckpt_char_list is not None:
        # a checkpoint may carry the dictionary it was trained with (`character_list`)
        vocab = Vocab(ckpt_char_list)
    log(f"dictionary: {len(vocab)} classes, blank index={vocab.blank}, "
        f"space index={vocab.table.get(' ')}")
    log(f"processor: size={proc.get('size')} pad_size={proc.get('pad_size')} "
        f"max_image_width={proc.get('max_image_width')} "
        f"normalisation={args.norm} glyph_scale={args.glyph_scale} bgr=True")

    # -- charset expansion (`--expand-charset`) ------------------------------- #
    added_chars = []
    if args.expand_charset:
        # every character of the training labels that the dictionary does not know yet
        missing_chars = set()
        for _tid, directory in find_types([os.path.join(ROOT, "dataset", "out"),
                                           os.path.join(ROOT, "dataset", "out_ru")]):
            for r in read_labels(directory):
                text = r.get("text") or r.get("answer") or ""
                missing_chars.update(ch for ch in text if ch not in vocab.table)
        added_chars = sorted(missing_chars)
        k_added = len(added_chars)
        log(f"--expand-charset: {k_added} characters missing from the dictionary: "
            + " ".join(repr(ch) for ch in added_chars))
        if k_added:
            vocab = Vocab.from_extended(vocab.character_list, added_chars)
            log(f"--expand-charset: dictionary extended to {len(vocab)} classes")
            # grow the head's output layer: copy the pretrained rows, initialise the new ones
            old_head = model.head.head
            new_head = nn.Linear(old_head.in_features, old_head.out_features + k_added, bias=True)
            with torch.no_grad():
                new_head.weight.copy_(torch.cat(
                    [old_head.weight, torch.zeros((k_added, old_head.in_features),
                                                  dtype=old_head.weight.dtype)], dim=0))
                new_head.bias.copy_(torch.cat(
                    [old_head.bias, torch.zeros((k_added,), dtype=old_head.bias.dtype)]))
                mean_row = new_head.weight[:old_head.out_features].mean(dim=0, keepdim=True)
                gen = torch.Generator()
                gen.manual_seed(int(args.seed))
                noise = torch.randn((k_added, old_head.in_features), generator=gen,
                                    dtype=old_head.weight.dtype) * 0.02
                new_head.weight[old_head.out_features:] = mean_row + noise
                new_head.bias[old_head.out_features:] = 0.0
            model.head.head = new_head
            log(f"--expand-charset: head output layer replaced, now {new_head.out_features} classes")
    save_char_list = bool(args.expand_charset) or ckpt_char_list is not None

    # -- split ---------------------------------------------------------------- #
    train_types, val_types, dropped, stats = build_split(args, vocab)
    if args.include_types:
        train_types = [t for t in train_types if any(p in t[0] for p in args.include_types)]
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

    # Banded types train on the band crop (`build_items`); with `--train-frames` the
    # types without a band train on the whole frame - the very same crop the
    # evaluation uses for them (`build_eval_items(..., no_roi_mode="frame")`).
    frame_types = [(t, d) for t, d in train_types if stats[t]["n_roi"] == 0]
    banded_types = [(t, d) for t, d in train_types if stats[t]["n_roi"] > 0]
    train_items = build_items(banded_types, limit_per_type=args.limit_per_type)
    if frame_types:
        train_items += build_eval_items(frame_types, limit_per_type=args.limit_per_type,
                                        no_roi_mode="frame")
        log(f"--train-frames: {len(frame_types)} band-less types trained as full frames: "
            + ", ".join(t for t, _ in frame_types))

    # Sample-level hold-out: the first N items of EVERY trained type go to the
    # evaluation set, the type itself still trains on the rest of its items. The unit
    # of generalisation is still the sample, not the plugin (see train/AGENTS.md).
    heldout_items = []
    heldout_per_type = {}
    if args.holdout_per_type and args.holdout_per_type > 0:
        n = args.holdout_per_type
        by_type = {}
        for it in train_items:
            by_type.setdefault(it["type"], []).append(it)
        kept = []
        for t, lst in by_type.items():
            held = lst[:n]
            kept.extend(lst[n:])
            heldout_per_type[t] = len(held)
            # same item shape the eval builder produces (band crop or the frame)
            heldout_items.extend(dict(it, has_roi=bool(it["roi"])) for it in held)
        train_items = kept
        short = {t: k for t, k in heldout_per_type.items() if k < n}
        log(f"HELD-OUT samples (first {n} per type): {len(heldout_items)} items over "
            f"{len(heldout_per_type)} types")
        for t in sorted(heldout_per_type):
            log(f"   {t:48s} held-out={heldout_per_type[t]:4d} "
                f"train={len(by_type[t]) - heldout_per_type[t]:4d} "
                f"of {len(by_type[t])}")
        if short:
            log(f"   WARNING: {len(short)} types had fewer than {n} items to hold out: "
                + ", ".join(sorted(short)))

    eval_types = val_types
    if args.eval_types:
        wanted = set(args.eval_types)
        eval_types = [(t, d) for t, d in (val_types + train_types) if t in wanted]
    # The whole-type held-out set (`--val-types`) plus the held-out samples. The same
    # type may appear in both train and eval when `--holdout-per-type` is used.
    eval_items = build_eval_items(eval_types, limit_per_type=args.limit_per_type,
                                  no_roi_mode=args.no_roi_mode) + heldout_items
    eval_sample_types = sorted({it["type"] for it in eval_items})
    # The "held-out median" is taken over the types present in the eval set.
    heldout_type_ids = {t for t, _ in eval_types} | set(heldout_per_type)
    val_items = [it for it in eval_items if it["type"] in heldout_type_ids]
    log(f"train items: {len(train_items)}   eval items: {len(eval_items)}   "
        f"held-out items: {len(val_items)}")
    log(f"eval covers {len(eval_sample_types)} types "
        f"({len({t for t, _ in val_types})} from --val-types, "
        f"{len(heldout_per_type)} with held-out samples): "
        + ", ".join(eval_sample_types))
    log(f"held-out aggregate: {len(heldout_type_ids)} types "
        f"(of which on eval loader: {len(val_items)})")

    ds_kw = dict(vocab=vocab, norm=args.norm, glyph_scale=args.glyph_scale)
    train_ds = PPOCRDataset(train_items, augment=not args.no_augment, seed=args.seed, **ds_kw)
    eval_ds = PPOCRDataset(eval_items, augment=False, **ds_kw)

    loader_kw = dict(num_workers=args.workers, pin_memory=True, collate_fn=collate,
                     persistent_workers=args.workers > 0)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                              drop_last=False, **loader_kw)
    eval_loader = DataLoader(eval_ds, batch_size=args.batch_size, shuffle=False, **loader_kw)

    model.to(device)
    model.train()

    # -- zero step ------------------------------------------------------------ #
    zero = None
    if not args.eval_only or args.zero_step:
        t0 = time.time()
        per_type = evaluate(model, eval_loader, vocab, device, amp=not args.no_amp)
        zero = {"per_type": per_type,
                "held_out": aggregate({t: v for t, v in per_type.items()
                                       if t in heldout_type_ids}),
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
    backbone_params = list(model.model.parameters())
    head_params = list(model.head.parameters())
    optimizer = torch.optim.AdamW(
        [{"params": backbone_params, "lr": args.lr},
         {"params": head_params, "lr": args.head_lr}],
        weight_decay=args.weight_decay)
    steps_per_epoch = max(1, len(train_loader))
    total_steps = steps_per_epoch * args.epochs
    sched = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=[args.lr, args.head_lr], total_steps=total_steps,
        pct_start=0.05, anneal_strategy="cos")
    scaler = torch.amp.GradScaler("cuda", enabled=not args.no_amp and device.type == "cuda")
    ctc = nn.CTCLoss(blank=vocab.blank, zero_infinity=True)
    ctc_raw = nn.CTCLoss(blank=vocab.blank, zero_infinity=False)

    start_epoch = 0
    global_step = 0
    if args.resume:
        cks = sorted([f for f in os.listdir(ckpt_dir)
                      if (f.startswith("step_") or f == "final.pt") and f.endswith(".pt")])
        if cks:
            ck = torch.load(os.path.join(ckpt_dir, cks[-1]), map_location="cpu", weights_only=False)
            if ck.get("character_list"):
                vocab = Vocab(ck["character_list"])
                log(f"dictionary from checkpoint {cks[-1]} 'character_list': {len(vocab)} classes")
            model.load_state_dict(ck["model"])
            optimizer.load_state_dict(ck["optimizer"])
            sched.load_state_dict(ck["sched"])
            scaler.load_state_dict(ck["scaler"])
            start_epoch = ck["epoch"] + 1
            global_step = ck["step"]
            log(f"resumed from {cks[-1]} (epoch {start_epoch}, step {global_step})")
        else:
            log(f"--resume: no checkpoint in {ckpt_dir}, starting from the pretrained model")

    log(f"training: {args.epochs} epochs x {steps_per_epoch} steps = {total_steps} steps, "
        f"lr={args.lr}/{args.head_lr}, batch={args.batch_size}, amp={not args.no_amp}")
    best = {"score": -1.0, "epoch": -1, "step": -1}
    history = []
    infeasible = 0
    step_times = []
    img_times = []
    stop = False
    last_epoch = start_epoch - 1

    for epoch in range(start_epoch, args.epochs):
        t_ep = time.time()
        last_epoch = epoch
        running, nb = 0.0, 0
        for batch in train_loader:
            px = batch["images"].to(device, non_blocking=True)
            labels = batch["labels"].to(device, non_blocking=True)
            lengths = batch["lengths"].to(device, non_blocking=True)
            bs = px.shape[0]
            t0 = time.time()
            with torch.autocast("cuda", dtype=torch.float16,
                                enabled=not args.no_amp and device.type == "cuda"):
                logits = forward_logits(model, px)
            logp = F.log_softmax(logits.float(), dim=-1).permute(1, 0, 2)
            t_steps = logp.shape[0]
            input_lengths = torch.full((bs,), t_steps, dtype=torch.long, device=device)
            loss = ctc(logp, labels, input_lengths, lengths)
            with torch.no_grad():
                raw = ctc_raw(logp, labels, input_lengths, lengths)
            infeasible += int((raw == float("inf")).any().item())
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            scale_before = scaler.get_scale()
            scaler.step(optimizer)
            scaler.update()
            # GradScaler skips the optimizer step when the gradients overflow; the
            # scheduler must not advance in that case, otherwise the LR schedule
            # drifts and PyTorch warns about `lr_scheduler.step()` before
            # `optimizer.step()`.
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
                ckpt = {"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                        "sched": sched.state_dict(), "scaler": scaler.state_dict(),
                        "epoch": epoch, "step": global_step, "args": vars(args)}
                if save_char_list:
                    ckpt["character_list"] = list(vocab.character_list)
                torch.save(ckpt, os.path.join(ckpt_dir, f"step_{global_step:06d}.pt"))
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
            per_type = evaluate(model, eval_loader, vocab, device, amp=not args.no_amp)
            val_per = {t: v for t, v in per_type.items() if t in heldout_type_ids}
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
                best_state = {"model": model.state_dict(), "epoch": epoch, "step": global_step,
                              "args": vars(args)}
                if save_char_list:
                    best_state["character_list"] = list(vocab.character_list)
                torch.save(best_state, os.path.join(out_dir, "best.pt"))
                log(f"  new best held-out median exact={score} -> {out_dir}/best.pt")
        if stop:
            break

    # A complete, resumable state: model + optimiser + scheduler + scaler + step.
    # Written at the end of every run so that the next session can continue with
    # `--resume` even if no `--save-every` checkpoint was reached.
    final_state = {"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                   "sched": sched.state_dict(), "scaler": scaler.state_dict(),
                   "epoch": last_epoch, "step": global_step,
                   "args": vars(args)}
    if save_char_list:
        final_state["character_list"] = list(vocab.character_list)
    torch.save(final_state, os.path.join(ckpt_dir, "final.pt"))
    log(f"resumable checkpoint written: {ckpt_dir}/final.pt (epoch {final_state['epoch']}, "
        f"step {final_state['step']})")

    # -- final evaluation of the best checkpoint ------------------------------ #
    final = None
    best_path = os.path.join(out_dir, "best.pt")
    if os.path.isfile(best_path):
        ck = torch.load(best_path, map_location="cpu", weights_only=False)
        if ck.get("character_list"):
            vocab = Vocab(ck["character_list"])
            log(f"dictionary from checkpoint {best_path} 'character_list': {len(vocab)} classes")
        model.load_state_dict(ck["model"])
        per_type = evaluate(model, eval_loader, vocab, device, amp=not args.no_amp)
        val_per = {t: v for t, v in per_type.items() if t in heldout_type_ids}
        final = {"per_type": per_type, "held_out": aggregate(val_per),
                 "all": aggregate(per_type), "epoch": ck["epoch"], "step": ck["step"]}
        print_per_type(per_type, f"FINAL (best checkpoint, epoch {ck['epoch']})")
    else:
        per_type = evaluate(model, eval_loader, vocab, device, amp=not args.no_amp)
        val_per = {t: v for t, v in per_type.items() if t in heldout_type_ids}
        final = {"per_type": per_type, "held_out": aggregate(val_per),
                 "all": aggregate(per_type), "epoch": None, "step": None}
        print_per_type(per_type, "FINAL (last epoch, no best checkpoint)")

    result = {
        "config": vars(args),
        "model": {"repo": args.model, "params": n_params,
                  "transformers": tfm_version, "torch": torch.__version__,
                  "classes": len(vocab), "blank_index": vocab.blank,
                  "head": "pretrained head kept (not replaced)"},
        "split": {"train_types": [t for t, _ in train_types],
                  "frame_train_types": [t for t, _ in frame_types],
                  "held_out_types": [t for t, _ in val_types],
                  "holdout_per_type": heldout_per_type,
                  "held_out_types_total": sorted(heldout_type_ids),
                  "items": {"train": len(train_items), "eval": len(eval_items),
                            "held_out": len(val_items)},
                  "dropped": {t: w for t, w in dropped}},
        "zero_step": zero,
        "final": final,
        "history": history,
        "runtime": {"seconds": round(time.time() - t_start, 1),
                    "minutes": round((time.time() - t_start) / 60.0, 2),
                    "img_per_s": round(sum(img_times) / max(sum(step_times), 1e-9), 1),
                    "step_ms": round(1000 * sum(step_times) / max(len(step_times), 1), 1),
                    "ctc_infeasible_batches": infeasible},
    }
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    log(f"done in {result['runtime']['minutes']} min -> {out_dir}/result.json")
    log_f.close()


if __name__ == "__main__":
    main()
