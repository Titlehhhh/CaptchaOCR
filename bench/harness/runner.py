"""The run loop: score one model over the item sets and write the result JSON."""

import json
import os
import statistics
import sys
import time
import traceback

from .items import build_items, load_input
from .metrics import aggregate, cer


def slug(key: str) -> str:
    return key.replace("/", "__")


def environment():
    env = {"python": sys.version.split()[0]}
    for mod in ("torch", "transformers", "onnxruntime", "numpy", "PIL", "huggingface_hub"):
        try:
            m = __import__(mod)
            env[mod] = getattr(m, "__version__", "?")
        except Exception as e:
            env[mod] = f"not available ({type(e).__name__})"
    try:
        import torch
        env["cuda"] = torch.cuda.is_available()
        env["device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    except Exception:
        env["cuda"] = False
        env["device"] = "cpu"
    return env


def run_model(key, spec, sets, modes, n_per_type, out_dir):
    itemsets = {name: build_items(name, n_per_type) for name in sets}
    result = {
        "model_key": key,
        "model": spec["repo"],
        "backend": spec["backend"].__name__,
        "license": spec.get("license"),
        "environment": environment(),
        "protocol": {
            "item_sets": {k: len(v) for k, v in itemsets.items()},
            "n_per_type": n_per_type,
            "input_modes": modes,
            "gold": "text (the drawn string) primary; answer reported as a second column",
            "normalisation": "keep alnum (any script) and +-*/=; drop everything else",
            "aggregate": "micro over items + median over the per-type values",
        },
        "item_sets": itemsets,
        "modes": {},
        "ok": True,
    }
    for mode in modes:
        result["modes"][mode] = {}
        for sname, items in itemsets.items():
            meta = {}
            t0 = time.time()
            try:
                preds, lat = spec["backend"](spec["repo"], items, mode, meta)
                agg = aggregate(items, preds)
                result["modes"][mode][sname] = {
                    "ok": True,
                    "seconds": round(time.time() - t0, 1),
                    "latency_ms_median": round(statistics.median(lat), 1) if lat else None,
                    "latency_ms_mean": round(statistics.fmean(lat), 1) if lat else None,
                    "metrics": {k: v for k, v in agg.items() if k != "per_type"},
                    "per_type": agg["per_type"],
                    "preds": [
                        {"type": it["type"], "file": it["file"], "has_roi": it["has_roi"],
                         "gold_text": it["text"], "gold_answer": it["answer"],
                         "pred": str(pr), "cer": cer(pr, it["text"]),
                         "cer_answer": cer(pr, it["answer"])}
                        for it, pr in zip(items, preds)
                    ],
                }
                m = result["modes"][mode][sname]["metrics"]["roi_types"]
                print(f"  [{key}] {mode}/{sname}: roi-types acc={m['acc_micro']:.3f} "
                      f"CER={m['cer_micro']:.3f} median-acc={m['acc_median_over_types']:.3f} "
                      f"({result['modes'][mode][sname]['seconds']}s)", flush=True)
            except Exception as e:
                result["modes"][mode][sname] = {
                    "ok": False,
                    "error": f"{type(e).__name__}: {e}",
                    "trace": traceback.format_exc()[-1500:],
                }
                print(f"  [{key}] {mode}/{sname}: FAIL {type(e).__name__}: {e}", flush=True)
            result.setdefault("meta", {})[f"{mode}/{sname}"] = meta

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{slug(key)}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"  -> {path}", flush=True)
    return result


# --------------------------------------------------------------------------- #
# contact sheet
# --------------------------------------------------------------------------- #
def contact_sheet(path, out_png, mode="band", set_name="full", top=24):
    """PNG sheet: the band crop, the gold answer and the prediction, worst first."""
    from PIL import Image, ImageDraw
    data = json.load(open(path, encoding="utf-8"))
    block = data["modes"][mode][set_name]
    preds = sorted(block["preds"], key=lambda p: (-(p["cer"] if p["cer"] is not None else 0),
                                                  p["type"], p["file"]))[:top]
    items = {(it["type"], it["file"]): it for it in data["item_sets"][set_name]}
    cell_w, cell_h = 300, 120
    cols = 4
    rows = (len(preds) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    for k, p in enumerate(preds):
        r, c = divmod(k, cols)
        x0, y0 = c * cell_w, r * cell_h
        it = items[(p["type"], p["file"])]
        img = load_input(it, mode)
        img.thumbnail((cell_w - 8, cell_h - 44))
        sheet.paste(img, (x0 + 4, y0 + 4))
        draw.text((x0 + 4, y0 + cell_h - 38), f"{p['type']}  {p['file']}", fill=(0, 0, 0))
        draw.text((x0 + 4, y0 + cell_h - 26), f"GOLD: {p['gold_text']}", fill=(0, 100, 0))
        draw.text((x0 + 4, y0 + cell_h - 14), f"PRED: {p['pred']!r}", fill=(160, 0, 0))
    sheet.save(out_png)
    print(f"contact sheet -> {out_png}")
