"""The TrOCR fine-tune loop.

`train/finetune_trocr.py` is the entry point; the loop lives here. The dataset, the
collator and the evaluation are in `train/trocr_data.py`, the report in
`train/trocr_report.py`, and what the two fine-tunes share in
`train/finetune_common.py`.
"""

import argparse
import json
import math
import os
import sys
import time

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

from finetune_common import (DEFAULT_VAL_TYPES, open_log, pick_device,  # noqa: E402
                              runtime_block, seed_everything)
from ppocr_data import build_eval_items, build_items  # noqa: E402
from trocr_core import (DEFAULT_MODEL, aggregate, build_split,  # noqa: E402
                       print_per_type)
from trocr_data import (Collator, TrOCRDataset, charset_report, evaluate,  # noqa: E402
                        shift_tokens_right)
from trocr_report import build_report  # noqa: E402


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
    seed_everything(args.seed)

    device = pick_device(args.device)
    log, log_f = open_log(out_dir)

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
        "runtime": runtime_block(t_start, step_times, img_times,
                                 {"epochs_done": len(history)}),
    }
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    log(f"done in {result['runtime']['minutes']} min -> {out_dir}/result.json")
    log_f.close()


if __name__ == "__main__":
    main()
