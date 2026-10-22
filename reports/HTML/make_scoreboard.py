"""Measure the PUBLISHED model on ALL 46 captcha types -> `reports/model_scoreboard.json`.

    .venv-gpu\\Scripts\\python.exe reports\\HTML\\make_scoreboard.py            # full run
    .venv-gpu\\Scripts\\python.exe reports\\HTML\\make_scoreboard.py --limit 5  # smoke test

What is measured
----------------
The model is the **published** one: `train/run_ppocr/big/export_soup/` (PP-OCRv6_medium_rec
+ WiSE-FT interpolation, alpha = 0.4, epoch 7 / step 1632) - the same weights that were
uploaded to `Titlehhhh/captchaocr-ppocrv6` (commit 43a65582).

The pipeline is **not** re-implemented here: it is imported from the training code, so the
numbers cannot drift from the ones that produced the published numbers.

* `train/ppocr_data.py`   - dataset discovery, band crop, the ink-box crop for the frames
                            without a band, scaling to 48 px, the BGR swap, the Paddle
                            normalisation `(x/255 - 0.5)/0.5`, the 48x320 tensor, the CER.
* `train/finetune_ppocr.py` - `norm()` (the metric normalisation) and `aggregate()`
                            (micro / median over types) - the very functions that produced
                            the published 0.638 median / 0.6123 micro on the 7 held-out types.

The decoding is the one of the released model: `AutoProcessor.from_pretrained(<export>)`
and `processor.post_process_text_recognition(out)` (the field is `last_hidden_state`, not
`.logits`). As a guard against a silent drift, the first batches are additionally decoded
with the pipeline's own `greedy_decode()` and the two decodings are compared.

Rules
-----
* `dataset/**` is read-only; nothing is written outside `reports/`.
* The reference screenshots (`real_shots/`) are never touched: the type discovery of
  `train/ppocr_data.py` walks the trees and only picks the directories that hold a
  `labels.jsonl`; the `real_shots` folders hold no labels, and the guard below refuses
  any path that contains them.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "train"))

os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".hf-cache"))
os.environ.setdefault("HF_HUB_CACHE", os.path.join(ROOT, ".hf-cache", "hub"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402

from finetune_ppocr import aggregate, greedy_decode, norm  # noqa: E402
from ppocr_data import (MAX_WIDTH, PPOCRDataset, Vocab, build_eval_items, cer,  # noqa: E402
                         collate, find_types, read_labels)

#: the published model (byte-identical to the files uploaded to the Hugging Face model repo)
EXPORT_DIR = os.path.join(ROOT, "train", "run_ppocr", "big", "export_soup")
#: where the measured numbers go
OUT_JSON = os.path.join(ROOT, "reports", "model_scoreboard.json")
#: the roots of the dataset
DATASET_ROOTS = [os.path.join(ROOT, "dataset", "out"), os.path.join(ROOT, "dataset", "out_ru")]
#: the 7 held-out types the published numbers were measured on (`train/finetune_ppocr.py`)
HELD_OUT = [
    "out/jonesdevelopment/sonar/standard",
    "out/jonesdevelopment/sonar/legacy",
    "out/jonesdevelopment/sonar/complex",
    "out_ru/BotFilter/map",
    "out_ru/CaptchaVerifyZ/map",
    "out/laforetbrut/are-you-sure/code",
    "out/JSH32/Minecaptcha/map",
]
#: the numbers that were published with the model (AGENTS.md, section 6)
PUBLISHED = {"median_exact": 0.638, "micro_exact": 0.6123,
             "median_cer": 0.1503, "micro_cer": 0.2004,
             "types": 7, "images": 3500}
#: how many examples per type are kept in the JSON
N_EXAMPLES = 6


def guard(path: str) -> str:
    """The reference screenshots of other people never go anywhere."""
    if "real_shots" in path.replace(os.sep, "/").split("/"):
        raise RuntimeError(f"refusing to touch a real_shots path: {path}")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="auto", choices=("auto", "cuda", "cpu"))
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None,
                    help="only the first N samples of every type (smoke test)")
    ap.add_argument("--no-amp", action="store_true")
    ap.add_argument("--out", default=OUT_JSON)
    ap.add_argument("--examples-pass", action="store_true",
                    help="only re-measure the 6 gallery samples of every type and write them "
                         "into the existing scoreboard JSON")
    args = ap.parse_args()

    device = torch.device("cuda" if (args.device == "auto" and torch.cuda.is_available())
                          else ("cuda" if args.device == "cuda" else args.device))
    print(f"device: {device}   torch {torch.__version__}", flush=True)

    # -- the dataset --------------------------------------------------------- #
    types = find_types(DATASET_ROOTS)
    print(f"types found: {len(types)}", flush=True)
    for tid, d in types:
        guard(d)
    items = build_eval_items(types, label_field="text", limit_per_type=args.limit,
                              no_roi_mode="content")
    print(f"evaluation items: {len(items)}", flush=True)

    # -- the model ------------------------------------------------------------ #
    from huggingface_hub import hf_hub_download  # noqa: F401
    from transformers import AutoProcessor, PPOCRV6SmallRecForTextRecognition

    model = PPOCRV6SmallRecForTextRecognition.from_pretrained(EXPORT_DIR)
    model.to(device)
    model.eval()
    processor = AutoProcessor.from_pretrained(EXPORT_DIR)
    if not hasattr(processor, "character_list"):
        # some builds of the image processor do not read the dictionary on their own
        with open(os.path.join(EXPORT_DIR, "preprocessor_config.json"), encoding="utf-8") as f:
            processor.character_list = json.load(f)["character_list"]
    vocab = Vocab(processor.character_list)
    meta = json.load(open(os.path.join(EXPORT_DIR, "finetune_meta.json"), encoding="utf-8"))
    print(f"model: {EXPORT_DIR}  soup_alpha={meta.get('soup_alpha')}  classes={len(vocab)}",
          flush=True)

    ds = PPOCRDataset(items, vocab=vocab, augment=False, norm="paddle", glyph_scale="band")
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=False,
                        num_workers=args.workers, pin_memory=True, collate_fn=collate)

    # -- the gallery samples only --------------------------------------------- #
    if args.examples_pass:
        from make_report import pick_rows
        gallery_items = []
        for tid, directory in types:
            for r in pick_rows(read_labels(directory), N_EXAMPLES):
                text = r.get("text") or r.get("answer") or ""
                if not text:
                    continue
                gallery_items.append({
                    "type": tid, "path": os.path.join(directory, r["file"]),
                    "text": text, "answer": r.get("answer", text), "roi": r.get("roi"),
                })
        gds = PPOCRDataset(gallery_items, vocab=vocab, augment=False, norm="paddle",
                           glyph_scale="band")
        gloader = DataLoader(gds, batch_size=args.batch_size, shuffle=False,
                             num_workers=args.workers, pin_memory=True, collate_fn=collate)
        got = {}
        with torch.no_grad():
            for batch in gloader:
                px = batch["images"].to(device, non_blocking=True)
                with torch.autocast("cuda", dtype=torch.float16,
                                    enabled=not args.no_amp and device.type == "cuda"):
                    out = model(pixel_values=px)
                decoded = processor.post_process_text_recognition(out)
                for i, (idx, t) in enumerate(zip(batch["indices"], batch["types"])):
                    item = gloader.dataset.items[idx]
                    got[(t, os.path.basename(item["path"]))] = (
                        decoded[i]["text"], float(decoded[i].get("score", 0.0)))
        with open(args.out, encoding="utf-8") as f:
            sb = json.load(f)
        for tid, directory in types:
            ex = []
            for r in pick_rows(read_labels(directory), N_EXAMPLES):
                key = (tid, r["file"])
                if key not in got:
                    continue
                p, score = got[key]
                gold = r.get("text") or r.get("answer") or ""
                ex.append({
                    "file": r["file"],
                    "path": os.path.relpath(os.path.join(directory, r["file"]), ROOT).replace(os.sep, "/"),
                    "gold_text": gold,
                    "gold_answer": r.get("answer", gold),
                    "pred": p,
                    "pred_norm": norm(p),
                    "exact": bool(norm(p) == norm(gold)),
                    "score": round(score, 4),
                    "has_band": r.get("roi") is not None,
                    "roi": r.get("roi"),
                })
            if tid in sb.get("types", {}):
                sb["types"][tid]["examples"] = ex
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(sb, f, ensure_ascii=False, indent=1)
        print(f"examples pass done: {len(got)} samples -> {args.out}")
        return 0

    # -- the run -------------------------------------------------------------- #
    per_type = {}
    examples = {}
    lens = {}
    checked = 0
    mismatches = 0
    t0 = time.time()
    done = 0
    with torch.no_grad():
        for batch in loader:
            px = batch["images"].to(device, non_blocking=True)
            with torch.autocast("cuda", dtype=torch.float16,
                                enabled=not args.no_amp and device.type == "cuda"):
                out = model(pixel_values=px)
            decoded = processor.post_process_text_recognition(out)
            preds = [d["text"] for d in decoded]
            scores = [d.get("score", 0.0) for d in decoded]

            # guard: the pipeline's own greedy decode must agree with the processor
            if checked < 8:
                from finetune_ppocr import forward_logits
                import torch.nn.functional as F
                with torch.autocast("cuda", dtype=torch.float16,
                                    enabled=not args.no_amp and device.type == "cuda"):
                    logits = forward_logits(model, px)
                alt = greedy_decode(F.log_softmax(logits.float(), dim=-1), vocab)
                checked += 1
                bad = sum(1 for a, b in zip(alt, preds) if a != b)
                mismatches += bad
                if bad:
                    print(f"  DECODE MISMATCH in batch {checked}: {bad} of {len(preds)}",
                          flush=True)

            for i, (idx, t) in enumerate(zip(batch["indices"], batch["types"])):
                item = loader.dataset.items[idx]
                gold = item["text"]
                p_raw = preds[i]
                p, g = norm(p_raw), norm(gold)
                d = per_type.setdefault(t, {"n": 0, "exact": 0, "exact_raw": 0, "cer": []})
                d["n"] += 1
                d["exact"] += int(p == g)
                d["exact_raw"] += int(p_raw == gold)
                c = cer(p, g)
                if c is not None:
                    d["cer"].append(c)
                L = lens.setdefault(t, {"pred": [], "gold": []})
                L["pred"].append(len(p_raw))
                L["gold"].append(len(gold))
                ex = examples.setdefault(t, [])
                if len(ex) < N_EXAMPLES:
                    ex.append({
                        "file": os.path.basename(item["path"]),
                        "path": os.path.relpath(item["path"], ROOT).replace(os.sep, "/"),
                        "gold_text": gold,
                        "gold_answer": item.get("answer", gold),
                        "pred": p_raw,
                        "pred_norm": p,
                        "exact": bool(p == g),
                        "score": round(float(scores[i]), 4),
                        "has_band": item.get("roi") is not None,
                    })
            done += len(preds)
            if done % 2000 < args.batch_size:
                print(f"  {done}/{len(items)}  ({time.time() - t0:.0f}s)", flush=True)

    seconds = time.time() - t0
    print(f"decoded {done} images in {seconds:.0f}s   decode mismatches: {mismatches}",
          flush=True)

    # -- the aggregates ------------------------------------------------------- #
    out_per_type = {}
    for t, d in per_type.items():
        cers = d["cer"]
        L = lens[t]
        out_per_type[t] = {
            "n": d["n"],
            "exact_match": round(d["exact"] / d["n"], 4),
            "exact_match_raw": round(d["exact_raw"] / d["n"], 4),
            "cer": round(statistics.fmean(cers), 4) if cers else None,
            "cer_median": round(statistics.median(cers), 4) if cers else None,
            "pred_len_median": round(statistics.median(L["pred"]), 2),
            "pred_len_mean": round(statistics.fmean(L["pred"]), 3),
            "gold_len_median": round(statistics.median(L["gold"]), 2),
            "examples": examples[t],
        }

    agg_all = aggregate(out_per_type)
    held = {t: v for t, v in out_per_type.items() if t in HELD_OUT}
    agg_held = aggregate(held)

    result = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": {
            "path": os.path.relpath(EXPORT_DIR, ROOT).replace(os.sep, "/"),
            "hf_repo": "Titlehhhh/captchaocr-ppocrv6",
            "soup_alpha": meta.get("soup_alpha"),
            "epoch": meta.get("epoch"),
            "step": meta.get("step"),
            "recipe": meta.get("recipe"),
            "classes": len(vocab),
        },
        "protocol": {
            "pipeline": "train/ppocr_data.py + train/finetune_ppocr.py (imported, not re-implemented)",
            "crop": "roi band where it exists, ink bounding box otherwise",
            "geometry": "48 x 320, Paddle normalisation (x/255-0.5)/0.5, RGB->BGR",
            "decode": "AutoProcessor.post_process_text_recognition(out.last_hidden_state)",
            "metric": "exact match and CER on the normalised `text` (norm() from finetune_ppocr)",
            "aggregate": "micro over the images and median over the types (aggregate())",
            "device": str(device),
            "seconds": round(seconds, 1),
            "decode_mismatches_vs_pipeline": mismatches,
        },
        "published_reference": {
            **PUBLISHED,
            "note": "the numbers the model was published with - 7 held-out types, 3500 images",
        },
        "all_46": agg_all,
        "held_out_7_reproduced": agg_held,
        "types": out_per_type,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("wrote", args.out)
    print("all 46 :", json.dumps(agg_all, ensure_ascii=False))
    print("held-out:", json.dumps(agg_held, ensure_ascii=False))
    print("published:", json.dumps(PUBLISHED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
