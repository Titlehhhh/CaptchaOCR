""

import argparse
import json
import os
import sys

import torch

HERE = os.path.dirname(os.path.abspath(__file__))


def find_root(start, levels=6):
    d = os.path.abspath(start)
    for _ in range(levels):
        if os.path.isdir(os.path.join(d, "train")) and os.path.isdir(os.path.join(d, "dataset")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent

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
    val_types = list(DEFAULT_VAL_TYPES)
    exclude_types = []
    include_types = None
    no_roi_mode = "frame"
    norm = "paddle"
    glyph_scale = "band"
    limit_per_type = None


    train_frames = False
    holdout_per_type = 0


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



    ft_w = ft.get("head.head.weight")
    if ft_w is not None and tuple(ft_w.shape) != tuple(model.head.head.weight.shape):
        import torch.nn as nn
        old = model.head.head
        model.head.head = nn.Linear(old.in_features, ft_w.shape[0], bias=True)



    from huggingface_hub import hf_hub_download
    proc = json.load(open(hf_hub_download(DEFAULT_MODEL, "preprocessor_config.json"),
                          encoding="utf-8"))
    char_list = ck.get("character_list") or proc["character_list"]
    vocab = Vocab(char_list)


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
            if k in ft and v.is_floating_point() and tuple(base[k].shape) == tuple(ft[k].shape):



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


    torch.save({"model": best_state, "alpha": best_alpha,
                "source_checkpoint": best, "source_epoch": ck.get("epoch"),
                "source_step": ck.get("step"),
                "character_list": list(char_list),
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
