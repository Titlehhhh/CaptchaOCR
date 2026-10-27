import argparse
import json
import os
import time

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .common import (DEFAULT_VAL_TYPES, open_log, pick_device,  # noqa: E402
                     runtime_block, seed_everything)
from .ppocr_core import (DEFAULT_MODEL, aggregate, build_split, evaluate,  # noqa: E402
                         forward_logits, print_per_type)
from .ppocr_data import PPOCRDataset, Vocab, build_eval_items, build_items, collate  # noqa: E402
from .ppocr_data import find_types, read_labels  # noqa: E402


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
    seed_everything(args.seed)

    device = pick_device(args.device)
    out_dir = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    ckpt_dir = os.path.join(out_dir, "ckpt")
    os.makedirs(ckpt_dir, exist_ok=True)
    log, log_f = open_log(out_dir)

    log(f"=== PP-OCRv6 fine-tune === {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"args: {vars(args)}")
    log(f"device: {device}  torch {torch.__version__}")

    from transformers import PPOCRV6SmallRecForTextRecognition, __version__ as tfm_version

    model = PPOCRV6SmallRecForTextRecognition.from_pretrained(args.model)
    n_params = sum(p.numel() for p in model.parameters())
    log(f"model: {args.model}  class=PPOCRV6SmallRecForTextRecognition  transformers {tfm_version}")
    log(f"params: {n_params}  model_type={model.config.model_type} "
        f"hidden_size={model.config.hidden_size} head_out_channels={model.config.head_out_channels} "
        f"backbone={model.config.backbone_config.model_type}")

    ckpt_char_list = None
    if args.init_from:
        init_ck = torch.load(args.init_from, map_location="cpu", weights_only=False)
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

    from huggingface_hub import hf_hub_download
    proc_path = hf_hub_download(args.model, "preprocessor_config.json")
    proc = json.load(open(proc_path, encoding="utf-8"))
    vocab = Vocab(proc["character_list"])
    if ckpt_char_list is not None:
        vocab = Vocab(ckpt_char_list)
    log(f"dictionary: {len(vocab)} classes, blank index={vocab.blank}, "
        f"space index={vocab.table.get(' ')}")
    log(f"processor: size={proc.get('size')} pad_size={proc.get('pad_size')} "
        f"max_image_width={proc.get('max_image_width')} "
        f"normalisation={args.norm} glyph_scale={args.glyph_scale} bgr=True")

    added_chars = []
    if args.expand_charset:
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

    frame_types = [(t, d) for t, d in train_types if stats[t]["n_roi"] == 0]
    banded_types = [(t, d) for t, d in train_types if stats[t]["n_roi"] > 0]
    train_items = build_items(banded_types, limit_per_type=args.limit_per_type)
    if frame_types:
        train_items += build_eval_items(frame_types, limit_per_type=args.limit_per_type,
                                        no_roi_mode="frame")
        log(f"--train-frames: {len(frame_types)} band-less types trained as full frames: "
            + ", ".join(t for t, _ in frame_types))

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
    eval_items = build_eval_items(eval_types, limit_per_type=args.limit_per_type,
                                  no_roi_mode=args.no_roi_mode) + heldout_items
    eval_sample_types = sorted({it["type"] for it in eval_items})
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

    final_state = {"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                   "sched": sched.state_dict(), "scaler": scaler.state_dict(),
                   "epoch": last_epoch, "step": global_step,
                   "args": vars(args)}
    if save_char_list:
        final_state["character_list"] = list(vocab.character_list)
    torch.save(final_state, os.path.join(ckpt_dir, "final.pt"))
    log(f"resumable checkpoint written: {ckpt_dir}/final.pt (epoch {final_state['epoch']}, "
        f"step {final_state['step']})")

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
        "runtime": runtime_block(t_start, step_times, img_times,
                                 {"ctc_infeasible_batches": infeasible}),
    }
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    log(f"done in {result['runtime']['minutes']} min -> {out_dir}/result.json")
    log_f.close()


if __name__ == "__main__":
    main()
