"""Export a trained CRNN+CTC checkpoint into a self-contained Hugging Face repository.

`python train\\export_hf.py --help` is the entry point; this module holds the
argument parsing and `main()`. The three design decisions of the export (one
processor without a sub-processor, `torch.onnx.export` instead of `optimum`, and a
verification instead of an assumption) are explained at the top of
`train/export_hf.py` and where they are made.
"""

import argparse
import json
import os
import sys
from typing import Any

import torch

from .card import write_model_card
from .common import (CYRILLIC_CHARSET, DEFAULT_OUT_DIRS, LATIN_CHARSET, TRAIN_DIR, log,
                     newest_checkpoint)
from .verify import load_check, pick_samples, verify
from .writer import derive_geometry, export_onnx, write_repo


# =====================================================================================
# main
# =====================================================================================
def make_synthetic_checkpoint(path: str, charset: str, glyph_height: int = 32,
                              hidden: int = 256, step: int = 1) -> str:
    """Write a checkpoint in the *exact* format `train/train.py` writes.

    The export path has to be provable before a real training run finishes, so this
    builds a randomly initialised CRNN and stores it the way the training loop stores
    it: the model state dict, the optimiser and scheduler states, the step, the RNG
    states, the args and the charset. The exported repository is then a real,
    loadable model - it simply has no training behind it.
    """
    if TRAIN_DIR not in sys.path:
        sys.path.insert(0, TRAIN_DIR)
    from captcha_crnn import CRNN, build_encoder

    cs = build_encoder(charset)
    model = CRNN(cs.num_classes, hidden=hidden, glyph_height=glyph_height)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=1e-3, total_steps=100, pct_start=0.05)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    torch.save({
        "model": model.state_dict(),
        "optim": opt.state_dict(),
        "sched": sched.state_dict(),
        "epoch": 0,
        "step": step,
        "rng": torch.get_rng_state(),
        "cuda_rng": None,
        "aug_rng": None,
        "args": {"charset": "latin" if charset == LATIN_CHARSET else "cyrillic",
                 "glyph_height": glyph_height, "epochs": 0, "batch_size": 32, "lr": 1e-3},
        "charset": charset,
    }, path)
    return path


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--make-synthetic-checkpoint", default=None, metavar="PATH",
                   help="write a synthetic checkpoint (the format train/train.py writes) "
                        "and exit; for testing the export path before a run finishes")
    p.add_argument("--checkpoint", default=None,
                   help="the checkpoint to export (default: the newest step_*.pt under --out)")
    p.add_argument("--from-run", default=None,
                   help="the training run's directory; takes the checkpoint and the "
                        "val_report.json from it")
    p.add_argument("--out", default=None, help="the target repository directory")
    p.add_argument("--charset", choices=["latin", "cyrillic"], default="latin",
                   help="a cross-check against the charset stored in the checkpoint")
    p.add_argument("--val-report", default=None, help="the run's val_report.json")
    p.add_argument("--repo-id", default=None,
                   help="the repository id the model card refers to")
    p.add_argument("--n-verify", type=int, default=12,
                   help="how many images the verification uses")
    p.add_argument("--dataset-roots", nargs="*", default=None,
                   help="the dataset trees the verification images come from")
    p.add_argument("--skip-onnx", action="store_true")
    p.add_argument("--skip-verify", action="store_true",
                   help="write the repository without verifying it (not recommended)")
    p.add_argument("--report", default=None, help="write the verification report as JSON")
    # the child process of the fresh-process check
    p.add_argument("--_load-check", default=None, help=argparse.SUPPRESS)
    p.add_argument("--_load-check-spec", default=None, help=argparse.SUPPRESS)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args._load_check:
        return load_check(args._load_check, args._load_check_spec)
    if args.make_synthetic_checkpoint:
        cs = LATIN_CHARSET if args.charset == "latin" else CYRILLIC_CHARSET
        p = make_synthetic_checkpoint(args.make_synthetic_checkpoint, cs)
        log(f"wrote a synthetic checkpoint to {p}")
        return 0

    out_dir = os.path.abspath(args.out)
    run_dir = os.path.abspath(args.from_run) if args.from_run else None

    ckpt_path = args.checkpoint
    if ckpt_path is None:
        ckpt_path = newest_checkpoint(*( [run_dir] if run_dir else [] ), out_dir)
    if ckpt_path is None or not os.path.isfile(ckpt_path):
        log(f"no checkpoint found (looked for step_*.pt under "
            f"{run_dir or out_dir}); pass --checkpoint")
        return 2
    ckpt_path = os.path.abspath(ckpt_path)
    log(f"checkpoint: {ckpt_path}")

    val_report = None
    val_path = args.val_report
    if val_path is None and run_dir:
        candidate = os.path.join(run_dir, "val_report.json")
        val_path = candidate if os.path.isfile(candidate) else None
    if val_path and os.path.isfile(val_path):
        with open(val_path, encoding="utf-8") as f:
            val_report = json.load(f)
        log(f"val report: {val_path}")
    else:
        log("val report: none (the model card will say so)")

    state = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    ckpt_state = state["model"]
    charset = state.get("charset") or (LATIN_CHARSET if args.charset == "latin"
                                       else CYRILLIC_CHARSET)
    if args.charset == "latin" and charset != LATIN_CHARSET:
        log(f"note: the checkpoint's charset is not the Latin one ({len(charset)} characters)")
    step = int(state.get("step", 0))
    epoch = int(state.get("epoch", 0))

    geom = derive_geometry(ckpt_state)
    ckpt_args = state.get("args") or {}
    cfg = {
        "num_classes": geom["num_classes"],
        "hidden": geom["hidden"],
        "dropout": 0.1,
        "glyph_height": geom["glyph_height"],
        "min_width": 64,
        "max_width": 400,
    }
    n_params = sum(int(v.numel()) for v in ckpt_state.values()
                   if hasattr(v, "numel") and v.dtype.is_floating_point)
    log(f"architecture: {cfg['num_classes']} classes, hidden {cfg['hidden']}, "
        f"glyph height {cfg['glyph_height']}, {n_params:,} parameters")

    os.makedirs(out_dir, exist_ok=True)
    write_repo(out_dir, cfg, ckpt_state, charset)
    log(f"wrote the repository skeleton to {out_dir}")

    onnx_exporter = "skipped"
    if not args.skip_onnx:
        onnx_exporter = export_onnx(out_dir, ckpt_state, cfg, charset)
        size = os.path.getsize(os.path.join(out_dir, "onnx", "model.onnx"))
        log(f"wrote onnx/model.onnx ({size / 1e6:.1f} MB, {onnx_exporter} exporter)")

    repo_id = args.repo_id or os.path.basename(out_dir.rstrip(os.sep)) or "captcha-crnn-ctc"
    write_model_card(out_dir, cfg, charset, n_params, val_report, repo_id, ckpt_path,
                     step, epoch, onnx_exporter)
    log("wrote README.md (the model card)")

    report: dict[str, Any] = {
        "checkpoint": ckpt_path,
        "out_dir": out_dir,
        "step": step,
        "epoch": epoch,
        "charset": charset,
        "num_classes": cfg["num_classes"],
        "hidden": cfg["hidden"],
        "glyph_height": cfg["glyph_height"],
        "parameters": n_params,
        "onnx_exporter": onnx_exporter,
        "verified": False,
    }

    if args.skip_verify:
        log("verification skipped (--skip-verify)")
    else:
        roots = args.dataset_roots or DEFAULT_OUT_DIRS
        samples = pick_samples(charset, args.n_verify, roots)
        if not samples:
            log("no dataset images found - the export was NOT verified")
            report["error"] = "no dataset images for the verification"
        else:
            report = verify(out_dir, samples, ckpt_state, charset, cfg, report)
            report["verified"] = True

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        log(f"verification report -> {args.report}")
    return 0 if report.get("verified") or args.skip_verify else 1
