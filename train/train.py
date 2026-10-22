"""Train the captcha CRNN on the generated dataset.

    python train/train.py --quick            # a smoke run, minutes
    python train/train.py --epochs 60        # the real thing

The run is checkpointed as it goes, so it can be stopped at any point and
resumed later - including from a different machine, as long as the dataset folder
is the same one the run was started from (the generated pixels depend on the
machine's font mapping, so the dataset is an artefact, not a function).

Resuming:

    python train/train.py --resume            # picks up the newest checkpoint
"""

import argparse
import json
import os
import random
import sys
import time

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from captcha_crnn import (BLANK, CHARSET, CYRILLIC, CaptchaDataset, CRNN, build_encoder,
                          build_items, cer, collate, find_types, greedy_decode, read_labels)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIRS = [os.path.join(REPO, "dataset", "out"), os.path.join(REPO, "dataset", "out_ru")]

# Types whose answer is not the text in the picture, or is constant, or cannot be
# recovered at all. They teach a recogniser nothing and leak on any random split.
EXCLUDE = [
    "LagBug/XProtect/drop",
    "LagBug/XProtect/jump",
    "LagBug/XProtect/sneak",
    "LagBug/XProtect/different",
    "China2B2T/Captcha/wool",
    "jSdCool/minecaptcha/image",
    "GalleryCaptcha/ru-object-swatch",
    "CaptchaGUI/clickblock",
    "LagBug/XProtect/slot",
    # The band holds a phrase that is not the answer and cannot be made to be:
    # "[Tap] button in red" versus the answer "[Tap] in red color", and a row of
    # sprite cells versus a list of sprite ids.
    "FeelingAlive0/AdvancedCaptcha/button",
    "jSdCool/minecaptcha/image",
    # The Russian number family spells a whole number out, one word per row, so its
    # band is a two or three line block whose glyph is only a fifth of the band. A
    # single-pass recogniser cannot read that: scaling the band to 32 px leaves a 7 px
    # glyph, and the words of adjacent rows touch each other, so the rows cannot even
    # be separated by projection. These three types are a solver-side task - read the
    # block with a per-line cropper, then turn the words into digits with the lexicon.
    "LimboFilter/map",
    "GalleryCaptcha/ru-numberword",
    "GalleryCaptcha/ru-numberword-caption",
]

# The types a quick run should use: clean text images, digits and Latin letters,
# no scene cropping needed. Two of them are held out for validation.
QUICK_TYPES = [
    "BotFilter/map",
    "GalleryCaptcha/ru-web",
    "irootdev/AnBot/captcha",
    "InstantlyMoist/Captcha/textcaptcha",
    "jSdCool/minecaptcha/text",
    "Archy-X/Krypton/map",
]
QUICK_VAL = ["InstantlyMoist/Captcha/textcaptcha", "haq/mapcha/map"]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--quick", action="store_true", help="small smoke run")
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=3e-3)
    p.add_argument("--head-lr", type=float, default=None,
                   help="learning rate for the head (default: lr / 10)")
    p.add_argument("--glyph-height", type=int, default=32)
    p.add_argument("--charset", choices=["latin", "cyrillic"], default="latin")
    p.add_argument("--types", nargs="*", default=None,
                   help="substring filters on the type id")
    p.add_argument("--val-types", nargs="*", default=None)
    p.add_argument("--limit-per-type", type=int, default=None)
    p.add_argument("--out", default=os.path.join(REPO, "train", "run"))
    p.add_argument("--save-every", type=int, default=200, help="steps between checkpoints")
    p.add_argument("--log-every", type=int, default=50)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--no-augment", action="store_true")
    p.add_argument("--augment-affine", action="store_true",
                   help="also apply a small rotation/shift/scale to the band. Off by "
                        "default: the JPEG/WebP/brightness pass is the documented "
                        "augmentation. Measured: without it the model memorises the "
                        "training styles instead of learning the glyphs")
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--threads", type=int, default=0)
    p.add_argument("--device", default="auto",
                   help="auto | cuda | cpu | cuda:0")
    p.add_argument("--amp", action="store_true", default=True,
                   help="mixed precision on the GPU (default on)")
    p.add_argument("--no-amp", dest="amp", action="store_false")
    p.add_argument("--workers", type=int, default=0,
                   help="dataloader workers; on a GPU the image decoding is the bottleneck")
    p.add_argument("--trees", choices=["out", "out_ru", "both"], default="both",
                   help="which dataset tree to train on")
    p.add_argument("--allow-no-roi", action="store_true",
                   help="also train on types that have no text band. Off by default: a type "
                        "without a band is the ill-posed 'find the string somewhere in this "
                        "picture' task, and training on it teaches the model to read the "
                        "wrong line")
    p.add_argument("--exclude-types", nargs="*", default=None,
                   help="extra type ids to leave out, on top of the built-in list")
    return p.parse_args()


def pick_device(spec):
    if spec == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dev = torch.device(spec)
    if dev.type == "cuda" and not torch.cuda.is_available():
        print(f"warning: {spec} requested but CUDA is not available - falling back to CPU",
              file=sys.stderr)
        return torch.device("cpu")
    return dev


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def split_types(types, val_types, quick):
    """Split the type list into train and validation.

    The split is by *type*, never by image: the unit of generalisation that
    matters is a plugin, and a random split leaks because several types have
    only a handful of distinct answers.
    """
    val_types = val_types or []
    if quick:
        train_ids = [t for t in QUICK_TYPES if t not in val_types]
        val_ids = [t for t in (val_types or QUICK_VAL)]
    else:
        val_set = set(val_types)
        train_ids = [t for t in types if t not in val_set]
        val_ids = [t for t in types if t in val_set]
    return train_ids, val_ids


def select(types, ids):
    """The subset of `types` whose id is in `ids` - always as (id, directory) pairs.

    The empty case used to return the list unchanged, which is a list of
    (id, directory, root) triples, and `build_items` then failed with
    "too many values to unpack" whenever a run had no `--val-types`.
    """
    keep = set(ids) if ids else None
    return [(tid, d) for tid, d, _r in types if keep is None or tid in keep]


def main():
    args = parse_args()
    if args.threads:
        torch.set_num_threads(args.threads)
    set_seed(args.seed)
    device = pick_device(args.device)
    if device.type == "cuda":
        print(f"device: {torch.cuda.get_device_name(0)} "
              f"({torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB)")
    else:
        print("device: cpu")

    charset = CHARSET if args.charset == "latin" else CYRILLIC
    cs = build_encoder(charset)
    encode, decode, num_classes = cs.encode, cs.decode, cs.num_classes

    all_types = find_types(OUT_DIRS, wanted=args.types, exclude=EXCLUDE)
    if args.trees != "both":
        want = "out_ru" if args.trees == "out_ru" else "out"
        all_types = [(t, d, r) for t, d, r in all_types if r.endswith(want)]
    if args.exclude_types:
        all_types = [(t, d, r) for t, d, r in all_types
                     if not any(e in t for e in args.exclude_types)]

    # Two kinds of type are left out of a run by default:
    #
    #  - a type with **no text band** is the ill-posed task: the answer is somewhere in
    #    the picture and the model is invited to learn which line to read;
    #  - a type whose label does not survive the charset is **poison**: a CTC target
    #    that is empty teaches the model nothing and costs the run its loss. That
    #    happens when a type draws in an alphabet the model does not have - the
    #    Cyrillic families against the Latin charset, for instance. Those types belong
    #    to the other model.
    #
    # A third case is a type that carries a band on *some* of its samples: the ones
    # without a band would be shown the whole frame, so they are dropped instead of
    # being trained on.
    kept = []
    dropped_band = []
    dropped_partial_band = []
    dropped_charset = []
    keep_files = {}
    for t, d, r in all_types:
        rows = read_labels(d)
        with_roi = [row for row in rows if row.get("roi")]
        if not args.allow_no_roi:
            if not with_roi:
                dropped_band.append(t)
                continue
            if len(with_roi) < len(rows):
                dropped_partial_band.append((t, len(rows) - len(with_roi)))
                keep_files[t] = {row["file"] for row in with_roi}
        # The charset check looks at EVERY row, not at the first five. A label with a
        # character outside the charset is poison: `Charset.encode` drops the unknown
        # character silently, so the label no longer matches the picture and the
        # model is taught to read a string that is not there.
        bad = 0
        for row in rows:
            text = row.get("text") or row.get("answer") or ""
            if len(cs.encode(text)) != len(text):
                bad += 1
        if bad:
            dropped_charset.append((t, bad))
            continue
        kept.append((t, d, r))
    if dropped_band:
        print("no text band, not training on: " + ", ".join(dropped_band))
    if dropped_partial_band:
        print("samples without a text band, dropped: "
              + ", ".join(f"{t} ({n})" for t, n in dropped_partial_band))
    if dropped_charset:
        print(f"labels are not in the {args.charset} charset, not training on: "
              + ", ".join(f"{t} ({n} rows)" for t, n in dropped_charset))
    all_types = kept
    if args.quick:
        all_types = [(t, d, r) for t, d, r in all_types
                     if t in set(QUICK_TYPES + QUICK_VAL)]
    train_ids, val_ids = split_types([t for t, _, _ in all_types], args.val_types, args.quick)
    train_types = select(all_types, train_ids)
    val_types = select(all_types, val_ids)

    if not train_types:
        print("no training types selected - check --types / --quick", file=sys.stderr)
        return 1

    train_items = build_items(train_types, limit_per_type=args.limit_per_type, keep=keep_files)
    val_items = build_items(val_types, limit_per_type=args.limit_per_type, keep=keep_files)
    print(f"train types {len(train_ids)}  samples {len(train_items)}")
    print(f"val   types {len(val_ids)}  samples {len(val_items)}")
    if val_ids:
        print(f"  held out: {', '.join(val_ids)}")

    train_ds = CaptchaDataset(train_items, encode, glyph_height=args.glyph_height,
                              augment=not args.no_augment, seed=args.seed,
                              affine=args.augment_affine)
    val_ds = CaptchaDataset(val_items, encode, glyph_height=args.glyph_height,
                            augment=False)

    loader = torch.utils.data.DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                                         collate_fn=collate, num_workers=args.workers,
                                         drop_last=False, persistent_workers=args.workers > 0)
    # The validation loader decodes the same PNGs as the training one, and with
    # zero workers it was slower than the training loop itself: the evaluation
    # of 1000 validation images took longer than 30 training steps.
    val_loader = torch.utils.data.DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                                             collate_fn=collate, num_workers=args.workers,
                                             persistent_workers=args.workers > 0) if val_items else None

    model = CRNN(num_classes, glyph_height=args.glyph_height)
    model.to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"model: {num_classes} classes, {n_params:,} parameters")

    head_lr = args.head_lr if args.head_lr is not None else args.lr / 10
    cnn_params = list(model.cnn.parameters()) + list(model.rnn.parameters())
    head_params = list(model.fc.parameters())
    opt = torch.optim.AdamW(
        [{"params": cnn_params, "lr": args.lr}, {"params": head_params, "lr": head_lr}],
        weight_decay=1e-2)
    steps_per_epoch = max(1, len(loader))
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=[args.lr, head_lr], total_steps=args.epochs * steps_per_epoch,
        pct_start=0.05)
    ctc = nn.CTCLoss(blank=BLANK, zero_infinity=True)

    os.makedirs(args.out, exist_ok=True)
    ckpt_dir = os.path.join(args.out, "ckpt")
    os.makedirs(ckpt_dir, exist_ok=True)

    start_epoch, step = 0, 0
    if args.resume:
        ckpts = sorted(
            (f for f in os.listdir(ckpt_dir) if f.startswith("step_") and f.endswith(".pt")),
            key=lambda f: int(f[5:-3]))
        if ckpts:
            path = os.path.join(ckpt_dir, ckpts[-1])
            state = torch.load(path, map_location="cpu", weights_only=False)
            model.load_state_dict(state["model"])
            opt.load_state_dict(state["optim"])
            sched.load_state_dict(state["sched"])
            start_epoch = state["epoch"]
            step = state["step"]
            torch.set_rng_state(state["rng"])
            if state.get("cuda_rng") and torch.cuda.is_available():
                torch.cuda.set_rng_state_all(state["cuda_rng"])
            if state.get("aug_rng"):
                train_ds.rng.setstate(state["aug_rng"])
            print(f"resumed from {path} (epoch {start_epoch}, step {step})")
        else:
            print("no checkpoint found, starting fresh")

    def save(tag):
        path = os.path.join(ckpt_dir, f"step_{step:07d}.pt")
        torch.save({
            "model": model.state_dict(),
            "optim": opt.state_dict(),
            "sched": sched.state_dict(),
            "epoch": start_epoch,
            "step": step,
            "rng": torch.get_rng_state(),
            "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
            "aug_rng": train_ds.rng.getstate(),
            "args": vars(args),
            "charset": charset,
        }, path)
        # keep the two newest
        keep = sorted((f for f in os.listdir(ckpt_dir) if f.startswith("step_")),
                      key=lambda f: int(f[5:-3]))
        for f in keep[:-2]:
            os.remove(os.path.join(ckpt_dir, f))
        print(f"  checkpoint -> {os.path.basename(path)}", flush=True)

    def evaluate(loader_):
        if loader_ is None:
            return None
        model.eval()
        per_type = {}
        total_exact, total_cer, n = 0, 0.0, 0
        with torch.no_grad():
            for batch in loader_:
                logits, t = model(batch["images"].to(device))
                preds = greedy_decode(logits.float().cpu(), decode)
                offset = 0
                for i, (pred, conf) in enumerate(preds):
                    gold = batch["labels"][offset:offset + int(batch["lengths"][i])]
                    gold_text = decode(gold.tolist())
                    typ = batch["types"][i]
                    d = per_type.setdefault(typ, {"n": 0, "exact": 0, "cer": 0.0})
                    d["n"] += 1
                    if pred == gold_text:
                        d["exact"] += 1
                    c = cer(pred, gold_text)
                    if c is not None:
                        d["cer"] += c
                    offset += int(batch["lengths"][i])
                    total_exact += int(pred == gold_text)
                    total_cer += c or 0.0
                    n += 1
        model.train()
        for d in per_type.values():
            d["accuracy"] = d["exact"] / max(1, d["n"])
            d["cer"] = d["cer"] / max(1, d["n"])
        return {"overall": {"n": n, "accuracy": total_exact / max(1, n),
                            "cer": total_cer / max(1, n)}, "per_type": per_type}

    model.train()
    use_amp = args.amp and device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    t0 = time.time()
    t_log = t0
    for epoch in range(start_epoch, args.epochs):
        running, seen, tloss = 0.0, 0, 0.0
        t_epoch0 = time.time()
        for batch in loader:
            images = batch["images"].to(device, non_blocking=True)
            labels = batch["labels"].to(device)
            lengths = batch["lengths"].to(device)
            with torch.amp.autocast("cuda", enabled=use_amp):
                logits, t = model(images)
                # the time axis is the width / 4 the model produced
                log_probs = logits.log_softmax(dim=-1).permute(1, 0, 2)   # (T, B, C)
                input_lengths = torch.full((logits.shape[0],), t, dtype=torch.long,
                                          device=device)
                loss = ctc(log_probs, labels, input_lengths, lengths)
            opt.zero_grad(set_to_none=True)
            if torch.isfinite(loss):
                scaler.scale(loss).backward()
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(opt)
                scaler.update()
                sched.step()
            running += float(loss.detach()) * images.shape[0]
            tloss += float(loss.detach())
            seen += images.shape[0]
            step += 1
            if step % args.log_every == 0:
                now = time.time()
                rate = seen / max(1e-6, now - t_log)
                print(f"  step {step:6d}  loss {running / max(1, seen):.4f}  "
                      f"{rate:.1f} img/s  elapsed {(now - t0) / 60:.1f} min", flush=True)
                running, seen = 0.0, 0
                t_log = now
            if step % args.save_every == 0:
                save("periodic")

        t_eval0 = time.time()
        report = evaluate(val_loader)
        t_eval = time.time() - t_eval0
        line = f"epoch {epoch + 1}/{args.epochs}  train loss {tloss / max(1, len(loader)):.4f}"
        if report:
            o = report["overall"]
            line += f"  VAL acc {o['accuracy']:.3f}  CER {o['cer']:.3f}"
        print(line, flush=True)
        if report:
            for typ, d in sorted(report["per_type"].items()):
                print(f"      {typ:46s} acc {d['accuracy']:.3f}  cer {d['cer']:.3f}  n={d['n']}")
            with open(os.path.join(args.out, "val_report.json"), "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=1)
        t_save0 = time.time()
        save("epoch")
        print(f"      [train {time.time() - t_epoch0:.1f}s  eval {t_eval:.1f}s  "
              f"checkpoint {time.time() - t_save0:.1f}s]", flush=True)

    print(f"done in {(time.time() - t0) / 60:.1f} min; model in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
