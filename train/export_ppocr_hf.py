"""Export a fine-tuned PP-OCRv6 checkpoint into a self-contained Hugging Face folder.

**This is the tracked version of `train/run_ppocr/export_hf.py`.** The whole
`train/run_ppocr/` directory is ignored by `.gitignore` (line 14), so the script that
produced the published weights of `Titlehhhh/captchaocr-ppocrv6` was invisible to git.
This copy lives next to the other tracked scripts of `train/` and is the one to use
from a fresh clone. The original file is kept as it is - the two are the same tool.

    .venv-gpu\\Scripts\\python.exe train\\export_ppocr_hf.py \\
        --ckpt train\\run_ppocr\\big\\best.pt \\
        --out  train\\run_ppocr\\big\\export_soup

By default it exports the **weight interpolation** (WiSE-FT, "model soup") of the
fine-tuned checkpoint with the pretrained base model:

    theta(alpha) = alpha * theta_finetuned + (1 - alpha) * theta_pretrained

with ``alpha = 0.4`` - the value that was measured as the best one on the held-out
captcha types (see ``reports/TRAINING_PPOCR_V6_BIG.md``). ``--soup-alpha 1.0`` exports
the checkpoint unchanged, ``--soup-alpha 0.0`` exports the pretrained base model.
The formula is the same as in ``train/run_ppocr/big/soup_eval.py``, so an exported soup
is the model that was measured there.

What goes into the folder:

* ``model.safetensors`` - the weights (the architecture is unchanged, so the base
  repository's ``config.json`` stays valid);
* ``config.json`` - **copied from the base repository**
  (``PaddlePaddle/PP-OCRv6_medium_rec_safetensors``), not synthesised: the fine-tune
  changes no hyper-parameter of the architecture. The upstream ``model_type`` is
  ``pp_ocrv6_small_rec`` for the medium model - that is an upstream metadata quirk
  and it is the class that actually loads these weights;
* ``preprocessor_config.json`` - copied from the base repository as well: the input
  geometry (48 x 320), the padding and the ``character_list`` are the model's own.
  **One field is patched**: the normalisation. ``PPOCRV6SmallRecImageProcessor``
  falls back to the ImageNet statistics (mean 0.485/0.456/0.406, std
  0.229/0.224/0.225) when the file does not say otherwise, but the fine-tune was
  trained with the PaddleOCR normalisation ``(x / 255 - 0.5) / 0.5`` (``--norm
  paddle``, the default of ``train/finetune_ppocr.py``). Without this patch the
  exported weights would be fed pixels they have never seen, so the normalisation
  is written out explicitly;
* ``processor_config.json`` - tells ``AutoProcessor`` which class to build
  (``PPOCRV6SmallRecImageProcessor``);
* ``character_list.txt`` - the same dictionary as a text file, one character per
  line, index 0 = ``blank`` (18 709 characters + the blank);
* ``finetune_meta.json`` - the provenance of this export (checkpoint, epoch, step,
  alpha).

The base files are taken from the hub; when the network is not reachable the local
``huggingface_hub`` cache is used instead, so the export works offline.
"""

import argparse
import json
import os

import torch
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file, save_file

BASE_REPO = "PaddlePaddle/PP-OCRv6_medium_rec_safetensors"

# The image processor of `transformers` falls back to the ImageNet statistics; the
# fine-tune was done with the PaddleOCR ones (see the module docstring).
PADDLE_MEAN = (0.5, 0.5, 0.5)
PADDLE_STD = (0.5, 0.5, 0.5)

# The alpha that was measured as the best one on the held-out captcha types.
DEFAULT_SOUP_ALPHA = 0.4


def find_repo_root(start: str) -> str:
    """The repository root: the nearest ancestor that holds `train/` and `dataset/`."""
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
    """A file of ``repo_id`` from the local ``huggingface_hub`` cache, or None."""
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
    """A file of ``repo_id``: from the hub, or from the local cache when offline."""
    try:
        return hf_hub_download(repo_id, filename)
    except Exception as exc:  # network down / not cached
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

    # -- the weights --------------------------------------------------------- #
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
        for k, v in list(sd.items()):
            if k in base and v.is_floating_point() and base[k].is_floating_point():
                sd[k] = (a * v.float() + (1.0 - a) * base[k].float()).to(v.dtype).contiguous()
                n_interp += 1
        print(f"soup: alpha={a} -> {n_interp} tensors interpolated with {args.model} "
              f"(the non-float buffers are taken from the checkpoint)")
    meta_alpha = a

    n_tensors = len(sd)
    n_params = sum(v.numel() for v in sd.values() if v.is_floating_point())
    n_float = sum(1 for v in sd.values() if v.is_floating_point())
    save_file(sd, os.path.join(out, "model.safetensors"), metadata={"format": "pt"})
    print(f"model.safetensors: {n_tensors} tensors ({n_float} float), "
          f"{n_params} float parameters")

    # -- the architecture ---------------------------------------------------- #
    src = fetch(args.model, "config.json")
    with open(src, "rb") as f:
        config = json.load(f)
    with open(os.path.join(out, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"config.json: copied from {args.model} (model_type={config.get('model_type')}, "
          f"head_out_channels={config.get('head_out_channels')})")

    # -- the processor ------------------------------------------------------- #
    src = fetch(args.model, "preprocessor_config.json")
    with open(src, encoding="utf-8") as f:
        proc = json.load(f)
    proc["image_mean"] = list(args.mean)
    proc["image_std"] = list(args.std)
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

    # -- the dictionary ------------------------------------------------------ #
    cl = proc["character_list"]
    with open(os.path.join(out, "character_list.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(cl) + "\n")
    print(f"character_list.txt: {len(cl)} entries, index 0 = {cl[0]!r}, "
          f"last = {cl[-1]!r} (index {len(cl)-1})")

    # -- the provenance ------------------------------------------------------ #
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
