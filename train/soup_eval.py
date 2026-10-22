"""Weight interpolation between the pretrained PP-OCRv6 and the fine-tuned one (WiSE-FT).

    .venv-gpu\\Scripts\\python.exe train\\soup_eval.py

    theta(alpha) = alpha * theta_finetuned + (1 - alpha) * theta_pretrained

`alpha = 0` is the pretrained model, `alpha = 1` is the fine-tuned one. Every alpha
is measured with the **same** pipeline the training run used: the same 7 held-out
types, the same 3500 images, the same crop, the same normalisation, the same
greedy CTC decoding and the same metrics (exact match on the normalised `text`,
CER, median over the 7 types, micro over the 3500 images).

The functions are imported from `train/finetune_ppocr.py` so that the pipeline
cannot drift away from the one the run used.

**Why this script exists.** The measurement it performs is the third step of the
publishing recipe: fine-tune with a gentle learning rate, **interpolate the
weights back towards the pretrained base**, and only then export. The pure
fine-tune is measurably *worse* than the untouched base (48.00 % vs 58.80 %
median exact match on the held-out types); the interpolation at alpha = 0.4 is
better than the base on **all seven** held-out types at once (63.80 % median,
61.23 % micro). See `reports/TRAINING_PPOCR_V6_BIG.md` §5-6.

**Paths.** Nothing here is hard-coded: the repository root is found by walking
up from this file until a directory with both `train/` and `dataset/` is found,
and every other path is relative to that root or to the run directory. The
defaults point at the run that produced the published numbers
(`train/run_ppocr/big`); override them with the flags below.

**Outputs** (in the run directory by default):

*   `soup.json` - the measurement of every alpha: the per-type metrics and the
    aggregates;
*   `soup_best.pt` - the weights of the winning alpha, ready to be exported
    (`train/run_ppocr/export_hf.py --ckpt ... --out ... --soup-alpha ...`).

Flags (all optional; running the script with no flags reproduces the published
measurement):

    --ckpt PATH         the fine-tuned checkpoint        (default: <run>/best.pt)
    --run-dir PATH      the run directory                 (default: train/run_ppocr/big)
    --out PATH          where to write soup.json          (default: <run>/soup.json)
    --soup-ckpt PATH    where to write soup_best.pt       (default: <run>/soup_best.pt)
    --alphas LIST       comma-separated alphas to measure (default: 0,0.25,0.4,0.5,0.6,0.75,1)
    --batch-size N      evaluation batch size             (default: 32)
    --workers N         dataloader workers                (default: 6)
    --device NAME       auto | cuda | cpu                 (default: auto)
    --limit-per-type N  limit the evaluation set (smoke tests only; default: all)
"""

import argparse
import json
import os
import sys

import torch

HERE = os.path.dirname(os.path.abspath(__file__))


def find_root(start, levels=6):
    """The repository root: the closest ancestor that holds both `train/` and `dataset/`."""
    d = os.path.abspath(start)
    for _ in range(levels):
        if os.path.isdir(os.path.join(d, "train")) and os.path.isdir(os.path.join(d, "dataset")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    # fallback: <root>/train/soup_eval.py -> <root>
    return os.path.dirname(HERE)


ROOT = find_root(HERE)
sys.path.insert(0, os.path.join(ROOT, "train"))

from finetune_ppocr import (DEFAULT_MODEL, DEFAULT_VAL_TYPES, aggregate,  # noqa: E402
                             build_split, evaluate, forward_logits, norm)
from ppocr_data import (PPOCRDataset, Vocab, build_eval_items, collate,  # noqa: E402
                         find_types, type_stats)

from torch.utils.data import DataLoader  # noqa: E402

ALPHAS = [0.0, 0.25, 0.4, 0.5, 0.6, 0.75, 1.0]
DEFAULT_RUN_DIR = os.path.join(ROOT, "train", "run_ppocr", "big")


class A:
    """The arguments the run used (see the run's log.txt)."""
    val_types = list(DEFAULT_VAL_TYPES)
    exclude_types = []
    include_types = None
    no_roi_mode = "frame"
    norm = "paddle"
    glyph_scale = "band"
    limit_per_type = None


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-dir", default=DEFAULT_RUN_DIR,
                   help="the training run's directory (default: train/run_ppocr/big)")
    p.add_argument("--ckpt", default=None,
                   help="the fine-tuned checkpoint (default: <run-dir>/best.pt)")
    p.add_argument("--out", default=None,
                   help="where to write the measurement (default: <run-dir>/soup.json)")
    p.add_argument("--soup-ckpt", default=None,
                   help="where to write the winning interpolation "
                        "(default: <run-dir>/soup_best.pt)")
    p.add_argument("--alphas", default=",".join(str(a) for a in ALPHAS),
                   help="comma-separated alphas to measure")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--device", default="auto", choices=("auto", "cuda", "cpu"))
    p.add_argument("--limit-per-type", type=int, default=None,
                   help="limit the evaluation set (smoke tests only; the published "
                        "measurement uses all of it)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    run_dir = os.path.abspath(args.run_dir)
    best = os.path.abspath(args.ckpt or os.path.join(run_dir, "best.pt"))
    out_path = os.path.abspath(args.out or os.path.join(run_dir, "soup.json"))
    soup_path = os.path.abspath(args.soup_ckpt or os.path.join(run_dir, "soup_best.pt"))
    try:
        alphas = [float(x) for x in args.alphas.split(",") if x.strip()]
    except ValueError:
        print(f"ERROR: --alphas must be a comma-separated list of numbers, got "
              f"{args.alphas!r}")
        return 2
    if not os.path.isfile(best):
        print(f"ERROR: checkpoint not found: {best}\n"
              f"pass --ckpt, or --run-dir <the run's directory>")
        return 2

    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"repo root : {ROOT}", flush=True)
    print(f"run dir   : {run_dir}", flush=True)
    print(f"checkpoint: {best}", flush=True)
    print(f"device    : {device}", flush=True)

    from transformers import PPOCRV6SmallRecForTextRecognition

    model = PPOCRV6SmallRecForTextRecognition.from_pretrained(DEFAULT_MODEL)
    base = {k: v.detach().clone().float() for k, v in model.state_dict().items()}

    ck = torch.load(best, map_location="cpu", weights_only=False)
    ft = {k: v.detach().clone().float() for k, v in ck["model"].items()}
    print(f"base checkpoint: {best}  epoch={ck.get('epoch')} step={ck.get('step')}", flush=True)

    # the model's own dictionary
    from huggingface_hub import hf_hub_download
    proc = json.load(open(hf_hub_download(DEFAULT_MODEL, "preprocessor_config.json"),
                          encoding="utf-8"))
    vocab = Vocab(proc["character_list"])

    # the split and the evaluation set - exactly as the training run built them
    roots = [os.path.join(ROOT, "dataset", "out"), os.path.join(ROOT, "dataset", "out_ru")]
    types = find_types(roots)
    stats = {s["type"]: s for s in type_stats(types)}
    train_types, val_types, dropped, _ = build_split(A, vocab)
    val_items = build_eval_items(val_types, limit_per_type=args.limit_per_type,
                                  no_roi_mode="frame")
    print(f"held-out items: {len(val_items)}  types: {len(val_types)}", flush=True)

    ds = PPOCRDataset(val_items, vocab=vocab, augment=False, norm="paddle",
                      glyph_scale="band")
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=False,
                        num_workers=args.workers, pin_memory=True,
                        persistent_workers=args.workers > 0, collate_fn=collate)

    model.to(device)
    results = {}
    best_alpha = None
    best_score = -1.0
    best_state = None
    for a in alphas:
        state = {}
        for k, v in model.state_dict().items():
            if k in ft and v.is_floating_point():
                state[k] = (a * ft[k] + (1.0 - a) * base[k]).to(v.dtype)
            else:
                state[k] = ft[k].to(v.dtype) if k in ft else v
        model.load_state_dict(state)
        per_type = evaluate(model, loader, vocab, device, amp=True)
        agg = aggregate(per_type)
        results[str(a)] = {"per_type": per_type, "aggregate": agg}
        score = agg["exact_match_median"] or 0.0
        if score > best_score:
            best_score = score
            best_alpha = a
            best_state = {k: v.detach().cpu().clone() for k, v in state.items()}
        print(f"alpha={a:<5} median exact={agg['exact_match_median']} cer={agg['cer_median']} "
              f"micro exact={agg['exact_match_micro']} cer={agg['cer_micro']}", flush=True)
        for t in sorted(per_type):
            v = per_type[t]
            print(f"    {t:45s} n={v['n']:4d} exact={v['exact_match']:.3f} cer={v['cer']:.3f}",
                  flush=True)

    # the winning interpolation, saved as a checkpoint for the export step
    torch.save({"model": best_state, "alpha": best_alpha,
                "source_checkpoint": best, "source_epoch": ck.get("epoch"),
                "source_step": ck.get("step"),
                "held_out_median_exact": best_score,
                "recipe": "theta = alpha * theta_finetuned + (1 - alpha) * theta_pretrained"},
               soup_path)
    print(f"best alpha = {best_alpha} (held-out median exact {best_score}) -> {soup_path}",
          flush=True)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"source_checkpoint": best, "epoch": ck.get("epoch"), "step": ck.get("step"),
                   "alphas": alphas, "best_alpha": best_alpha, "results": results},
                  f, ensure_ascii=False, indent=1)
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
