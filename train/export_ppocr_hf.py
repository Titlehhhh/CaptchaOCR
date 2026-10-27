import argparse

import json
import os

import torch
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file, save_file

BASE_REPO = "PaddlePaddle/PP-OCRv6_medium_rec_safetensors"

PADDLE_MEAN = (0.5, 0.5, 0.5)
PADDLE_STD = (0.5, 0.5, 0.5)

DEFAULT_SOUP_ALPHA = 0.4


def find_repo_root(start: str) -> str:
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, "train")) and os.path.isdir(os.path.join(d, "dataset")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            raise SystemExit(
                f"repository root not found above {start!r} "
                f"(expected a directory with 'train/' and 'dataset/')"
            )
        d = parent


def _from_cache(repo_id: str, filename: str):
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
    except Exception:  # pragma: no cover - very old huggingface_hub
        return None
    folder = "models--" + repo_id.replace("/", "--")
    snaps = os.path.join(HF_HUB_CACHE, folder, "snapshots")
    if not os.path.isdir(snaps):
        return None
    for snap in sorted(os.listdir(snaps)):
        path = os.path.join(snaps, snap, filename)
        if os.path.isfile(path):
            return path
    return None


def fetch(repo_id: str, filename: str) -> str:
    try:
        return hf_hub_download(repo_id, filename)
    except Exception as exc:
        cached = _from_cache(repo_id, filename)
        if cached is None:
            raise SystemExit(
                f"cannot obtain {filename!r} of {repo_id!r}: {exc}\n"
                f"download it once with network access, or put it into the hub cache."
            )
        print(f"{filename}: taken from the local cache ({cached})")
        return cached


def main():
    root = find_repo_root(os.path.dirname(os.path.abspath(__file__)))

    ap = argparse.ArgumentParser(
        description="Export a fine-tuned PP-OCRv6 checkpoint into a Hugging Face folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--ckpt", default=os.path.join(root, "train", "run_ppocr", "big", "best.pt"),
                    help="the fine-tuned checkpoint (a torch.save of {'model': state_dict, ...})")
    ap.add_argument("--out", default=None,
                    help="the output folder (default: <folder of the checkpoint>/export_hf)")
    ap.add_argument("--model", default=BASE_REPO,
                    help="the base model the fine-tune started from")
    ap.add_argument("--mean", type=float, nargs=3, default=list(PADDLE_MEAN),
                    help="normalisation mean written into preprocessor_config.json")
    ap.add_argument("--std", type=float, nargs=3, default=list(PADDLE_STD),
                    help="normalisation std written into preprocessor_config.json")
    ap.add_argument("--soup-alpha", type=float, default=DEFAULT_SOUP_ALPHA,
                    help="export the weight interpolation alpha*theta_ft + (1-alpha)*theta_base "
                         "(1.0 = the checkpoint itself, 0.0 = the pretrained base; the default "
                         "0.4 is the alpha that measured best on the held-out types)")
    args = ap.parse_args()

    ckpt = os.path.abspath(args.ckpt)
    if not os.path.isfile(ckpt):
        raise SystemExit(f"checkpoint not found: {ckpt}")
    out = os.path.abspath(args.out or os.path.join(os.path.dirname(ckpt), "export_hf"))
    os.makedirs(out, exist_ok=True)

    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    if not isinstance(ck, dict) or "model" not in ck:
        raise SystemExit(f"{ckpt}: no 'model' key - is it a fine-tune checkpoint?")
    sd = ck["model"]
    sd = {k: v.detach().clone().contiguous() for k, v in sd.items()}

    a = None if args.soup_alpha is None else float(args.soup_alpha)
    if a is not None:
        base_path = fetch(args.model, "model.safetensors")
        base = load_file(base_path)
        n_interp = 0
        n_skipped = 0
        for k, v in list(sd.items()):
            if k in base and v.is_floating_point() and base[k].is_floating_point():
                if tuple(base[k].shape) != tuple(v.shape):
                    n_skipped += 1
                    continue
                sd[k] = (a * v.float() + (1.0 - a) * base[k].float()).to(v.dtype).contiguous()
                n_interp += 1
        if n_skipped:
            print(f"soup: {n_skipped} tensors skipped (shape mismatch with the base - "
                  f"the checkpoint's own values kept, e.g. the expanded head rows)")
        print(f"soup: alpha={a} -> {n_interp} tensors interpolated with {args.model} "
              f"(the non-float buffers are taken from the checkpoint)")
    meta_alpha = a

    n_tensors = len(sd)
    n_params = sum(v.numel() for v in sd.values() if v.is_floating_point())
    n_float = sum(1 for v in sd.values() if v.is_floating_point())
    save_file(sd, os.path.join(out, "model.safetensors"), metadata={"format": "pt"})
    print(f"model.safetensors: {n_tensors} tensors ({n_float} float), "
          f"{n_params} float parameters")

    src = fetch(args.model, "config.json")
    with open(src, "rb") as f:
        config = json.load(f)
    head_out = sd.get("head.head.weight")
    if head_out is not None and head_out.shape[0] != config.get("head_out_channels"):
        config["head_out_channels"] = int(head_out.shape[0])
        print(f"config.json: head_out_channels patched to {config['head_out_channels']} "
              f"(the checkpoint's expanded head)")
    with open(os.path.join(out, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"config.json: copied from {args.model} (model_type={config.get('model_type')}, "
          f"head_out_channels={config.get('head_out_channels')})")

    src = fetch(args.model, "preprocessor_config.json")
    with open(src, encoding="utf-8") as f:
        proc = json.load(f)
    proc["image_mean"] = list(args.mean)
    proc["image_std"] = list(args.std)
    if ck.get("character_list"):
        proc["character_list"] = list(ck["character_list"])
        print(f"preprocessor_config.json: character_list taken from the checkpoint "
              f"({len(proc['character_list'])} classes, expanded charset)")
    with open(os.path.join(out, "preprocessor_config.json"), "w", encoding="utf-8") as f:
        json.dump(proc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"preprocessor_config.json: copied from {args.model}; "
          f"normalisation patched to mean={list(args.mean)} std={list(args.std)} "
          f"(the fine-tune was trained with the PaddleOCR normalisation)")

    processor_config = {
        "image_processor_type": "PPOCRV6SmallRecImageProcessor",
        "processor_class": "PPOCRV6SmallRecImageProcessor",
    }
    with open(os.path.join(out, "processor_config.json"), "w", encoding="utf-8") as f:
        json.dump(processor_config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("processor_config.json:", json.dumps(processor_config))

    cl = proc["character_list"]
    with open(os.path.join(out, "character_list.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(cl) + "\n")
    print(f"character_list.txt: {len(cl)} entries, index 0 = {cl[0]!r}, "
          f"last = {cl[-1]!r} (index {len(cl)-1})")

    meta = {
        "base_model": args.model,
        "checkpoint": ckpt,
        "epoch": ck.get("epoch", ck.get("source_epoch")),
        "step": ck.get("step", ck.get("source_step")),
        "soup_alpha": meta_alpha if meta_alpha is not None else ck.get("alpha"),
        "classes": len(cl),
        "parameters": n_params,
        "tensors": n_tensors,
        "normalisation": {"mean": list(args.mean), "std": list(args.std)},
        "transformers_class": "PPOCRV6SmallRecForTextRecognition",
        "exported_by": os.path.relpath(os.path.abspath(__file__), root),
    }
    for k in ("recipe", "source_checkpoint", "source_epoch", "source_step",
              "held_out_median_exact"):
        if k in ck:
            meta[k] = ck[k]

    with open(os.path.join(out, "finetune_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("finetune_meta.json:", json.dumps(meta, ensure_ascii=False))

    total = sum(os.path.getsize(os.path.join(out, n)) for n in os.listdir(out))
    print(f"OK -> {out}  ({len(os.listdir(out))} files, {total} bytes)")


if __name__ == "__main__":
    main()
