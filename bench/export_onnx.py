r"""Export the trained CRNN to ONNX, quantise it to int8, and measure both.

    .venv-gpu\Scripts\python.exe bench\export_onnx.py export   --ckpt train\run\main\ckpt\step_0005700.pt
    .venv-gpu\Scripts\python.exe bench\export_onnx.py quantize --fp32 bench\models\crnn_fp32.onnx
    .venv-gpu\Scripts\python.exe bench\export_onnx.py eval     --model bench\models\crnn_fp32.onnx --out reports\bench_models\T2_eval_fp32.json
    .venv-gpu\Scripts\python.exe bench\export_onnx.py speed    --out reports\bench_models\T2_speed.json

The model is the CRNN+CTC of `train/captcha_crnn.py` (4 623 615 parameters, 63 classes).
The input is a text band scaled to a 32 px glyph height with a floating width
(`(B, 1, 32, W)`, `T = W/4` time steps), the output is the CTC logits `(B, T, 63)`.

The evaluation protocol is the one of `reports/TRAINING_MINIMAL_LATIN.md`: the same
band crop, the same glyph scaling, the same greedy CTC decode, exact match + CER per
type. The types are the ten of the main run (`train/run/main`): six the model was
trained on and four it never saw. Both numbers are reported, because the trained
types are memorised (1.000) and the held-out types are not (0.000) - the runtime
changes neither.
"""

import argparse
import json
import os
import statistics
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "train"))

from captcha_crnn import (CHARSET, CaptchaDataset, CRNN, build_encoder, build_items,  # noqa: E402
                          cer, collate, find_types, read_labels)

OUT_DIRS = [os.path.join(REPO, "dataset", "out"), os.path.join(REPO, "dataset", "out_ru")]

#: The ten types of the main run (`reports/TRAINING_MINIMAL_LATIN.md` section 4).
TRAINED_TYPES = [
    "Archy-X/Krypton/map",
    "GalleryCaptcha/ru-web",
    "JSH32/Minecaptcha/map",
    "just-captcha/ProstoCaptcha/map",
    "n1zamu/NCaptcha/anvil",
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA/map",
]
HELD_OUT_TYPES = [
    "CaptchaVerifyZ/map",
    "haq/mapcha/map",
    "jSdCool/minecaptcha/text",
    "laforetbrut/are-you-sure/code",
]
ALL_TYPES = TRAINED_TYPES + HELD_OUT_TYPES

#: The model metadata a runtime needs: the alphabet, the geometry and the normalisation.
CONFIG = {
    "name": "captha-crnn-ctc",
    "charset": CHARSET,
    "blank_index": 0,
    "num_classes": len(CHARSET) + 1,
    "input": {
        "layout": "NCHW",
        "channels": 1,
        "glyph_height": 32,
        "width": "dynamic (T = W/4 time steps)",
        "min_width": 64,
        "max_width": 400,
    },
    "preprocess": {
        "crop": "roi = [x, y, w, h] from labels.jsonl; null = the whole frame",
        "grayscale": "PIL 'L' (ITU-R 601-2)",
        "glyph_height": "the median height of the busy rows of the band",
        "resize": "PIL BILINEAR to (w, 32)",
        "normalise": "(x/255 - 0.5) / 0.5",
        "mean": 0.5,
        "std": 0.5,
    },
    "decode": "greedy CTC: argmax, collapse repeats, drop the blank",
    "source_checkpoint": "train/run/main/ckpt/step_0005700.pt",
}


# --------------------------------------------------------------------------- helpers

def build_eval_items(types, limit_per_type=None):
    """The evaluation set: the bands of the given types, exactly as the trainer reads them.

    A type that carries a band on most of its samples but not on all loses the
    band-less samples here too - showing the whole frame to a band recogniser is
    the ill-posed task, and the trainer drops those rows as well.
    """
    found = find_types(OUT_DIRS, wanted=list(types))
    by_id = {t: d for t, d, _r in found}
    ordered = [(t, by_id[t]) for t in types if t in by_id]
    items = build_items(ordered, limit_per_type=limit_per_type)
    keep = []
    per_type_rows = {}
    for it in items:
        per_type_rows.setdefault(it["type"], []).append(it)
    for typ, rows in per_type_rows.items():
        with_roi = [r for r in rows if r["roi"]]
        if with_roi and len(with_roi) != len(rows):
            keep.extend(with_roi)
        else:
            keep.extend(rows)
    keep.sort(key=lambda it: (ALL_TYPES.index(it["type"]) if it["type"] in ALL_TYPES else 99,
                               it["path"]))
    return keep


def load_checkpoint(ckpt_path, device="cpu"):
    import torch
    state = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    cs = build_encoder(CHARSET)
    model = CRNN(cs.num_classes)
    model.load_state_dict(state["model"])
    model.to(device).eval()
    return model, cs, state


def make_batches(items, cs, batch_size=64, workers=4):
    """The evaluation batches: the trainer's own dataset, collate and order."""
    import torch
    ds = CaptchaDataset(items, cs.encode, augment=False)
    loader = torch.utils.data.DataLoader(ds, batch_size=batch_size, shuffle=False,
                                         collate_fn=collate, num_workers=workers)
    out = []
    for batch in loader:
        out.append(batch)
    return out


def greedy_decode_np(logits, charset=CHARSET):
    """The greedy CTC decode of `captcha_crnn.greedy_decode`, in numpy.

    `logits` is (B, T, C); returns a list of (text, confidence).
    """
    x = logits - logits.max(axis=-1, keepdims=True)
    e = np.exp(x)
    probs = e / e.sum(axis=-1, keepdims=True)
    best = probs.argmax(axis=-1)
    best_p = probs.max(axis=-1)
    out = []
    for b in range(best.shape[0]):
        chars, confs = [], []
        prev = -1
        for t in range(best.shape[1]):
            k = int(best[b, t])
            if k != prev and k != 0:
                chars.append(k)
                confs.append(float(best_p[b, t]))
            prev = k
        text = "".join(charset[k - 1] for k in chars if 1 <= k <= len(charset))
        conf = float(np.exp(np.mean(np.log(np.clip(confs, 1e-6, 1.0))))) if confs else 0.0
        out.append((text, conf))
    return out


def summarise(per_type):
    """Turn the raw per-type counters into the report's numbers."""
    out = {}
    for typ, d in per_type.items():
        out[typ] = {"n": d["n"], "exact": d["exact"],
                    "accuracy": d["exact"] / max(1, d["n"]),
                    "cer": d["cer"] / max(1, d["n"]),
                    "confidence": d["conf"] / max(1, d["n"])}
    accs = sorted(v["accuracy"] for v in out.values())
    cers = sorted(v["cer"] for v in out.values())
    n = sum(v["n"] for v in out.values())
    ex = sum(v["exact"] for v in out.values())
    overall = {
        "n": n,
        "exact": ex,
        "accuracy": ex / max(1, n),
        "cer": sum(v["cer"] * v["n"] for v in out.values()) / max(1, n),
        "median_type_accuracy": statistics.median(accs) if accs else None,
        "median_type_cer": statistics.median(cers) if cers else None,
    }
    return overall, out


def group_median(per_type, types):
    """The median over a named group of types (the trained ones / the held-out ones)."""
    sel = [per_type[t] for t in types if t in per_type]
    if not sel:
        return None
    accs = sorted(v["accuracy"] for v in sel)
    cers = sorted(v["cer"] for v in sel)
    n = sum(v["n"] for v in sel)
    ex = sum(v["exact"] for v in sel)
    return {"types": len(sel), "n": n, "exact": ex,
            "accuracy": ex / max(1, n),
            "median_type_accuracy": statistics.median(accs),
            "median_type_cer": statistics.median(cers)}


# --------------------------------------------------------------------------- export

def cmd_export(args):
    import torch
    import torch.nn as nn
    import onnxruntime as ort

    model, cs, state = load_checkpoint(args.ckpt, device="cpu")
    print(f"checkpoint {args.ckpt}  step {state.get('step')}  epoch {state.get('epoch')}")
    print(f"parameters {sum(p.numel() for p in model.parameters()):,}  classes {cs.num_classes}")

    class LogitsOnly(nn.Module):
        """`CRNN.forward` returns (logits, time steps); the ONNX graph needs one output."""

        def __init__(self, base):
            super().__init__()
            self.base = base

        def forward(self, x):
            return self.base(x)[0]

    wrapped = LogitsOnly(model).eval()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    t0 = time.time()
    torch.onnx.export(
        wrapped, (torch.zeros(1, 1, 32, 128),), args.out,
        input_names=["image"], output_names=["logits"],
        dynamic_axes={"image": {0: "batch", 3: "width"},
                      "logits": {0: "batch", 1: "time"}},
        opset_version=args.opset, do_constant_folding=True, dynamo=False,
    )
    print(f"exported {args.out}  opset {args.opset}  {os.path.getsize(args.out):,} bytes  "
          f"in {time.time() - t0:.1f}s")

    sess = ort.InferenceSession(args.out, providers=["CPUExecutionProvider"])
    print("input :", [(i.name, i.shape) for i in sess.get_inputs()])
    print("output:", [(o.name, o.shape) for o in sess.get_outputs()])

    # the parity check: random tensors at the widths the brief asks for, plus a batch
    rng = np.random.default_rng(7)
    checks = []
    for width in (60, 128, 400):
        x = rng.standard_normal((1, 1, 32, width)).astype(np.float32)
        with torch.no_grad():
            ref = wrapped(torch.from_numpy(x)).numpy()
        got = sess.run(None, {"image": x})[0]
        checks.append({"width": width, "batch": 1,
                       "max_abs_diff": float(np.abs(ref - got).max()),
                       "shape_torch": list(ref.shape), "shape_onnx": list(got.shape)})
        print(f"  width {width:4d}: torch {tuple(ref.shape)} onnx {tuple(got.shape)} "
              f"max abs diff {checks[-1]['max_abs_diff']:.3e}")

    x = rng.standard_normal((4, 1, 32, 200)).astype(np.float32)
    with torch.no_grad():
        ref = wrapped(torch.from_numpy(x)).numpy()
    got = sess.run(None, {"image": x})[0]
    checks.append({"width": 200, "batch": 4,
                   "max_abs_diff": float(np.abs(ref - got).max()),
                   "shape_torch": list(ref.shape), "shape_onnx": list(got.shape)})
    print(f"  batch 4 x width 200: max abs diff {checks[-1]['max_abs_diff']:.3e}")

    cfg = dict(CONFIG)
    cfg["onnx"] = {"file": os.path.basename(args.out),
                   "opset": args.opset,
                   "bytes": os.path.getsize(args.out),
                   "input_name": "image", "output_name": "logits",
                   "dynamic_axes": {"image": ["batch", "width"], "logits": ["batch", "time"]}}
    cfg["checkpoint"] = {"path": args.ckpt, "step": state.get("step"),
                         "epoch": state.get("epoch"),
                         "parameters": sum(p.numel() for p in model.parameters()),
                         "charset": state.get("charset")}
    with open(args.config, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    print(f"wrote {args.config}")

    with open(args.report, "w", encoding="utf-8") as f:
        json.dump({"checkpoint": args.ckpt, "onnx": args.out, "opset": args.opset,
                   "bytes": os.path.getsize(args.out), "parity": checks}, f, indent=1)
    print(f"wrote {args.report}")
    return 0


# --------------------------------------------------------------------------- quantisation

def cmd_quantize(args):
    from onnxruntime.quantization import (QuantType, quantize_dynamic, quantize_static)
    from onnxruntime.quantization.shape_inference import quant_pre_process

    os.makedirs(os.path.dirname(os.path.abspath(args.out_dir)), exist_ok=True)
    results = []

    # -- dynamic: the weights become int8, the activations stay float and are
    #    quantised on the fly.
    if "dynamic" in args.variants:
        dyn = os.path.join(args.out_dir, "crnn_int8_dynamic.onnx")
        t0 = time.time()
        quantize_dynamic(args.fp32, dyn, weight_type=QuantType.QInt8)
        results.append({"variant": "dynamic", "file": dyn,
                        "bytes": os.path.getsize(dyn), "seconds": round(time.time() - t0, 1)})
        print(f"dynamic int8 -> {dyn}  {os.path.getsize(dyn):,} bytes  {time.time()-t0:.1f}s")

    # -- static: the activation ranges are measured on our own bands.
    pre = os.path.join(args.out_dir, "crnn_fp32_preproc.onnx")
    if any(v.startswith("static") for v in args.variants):
        quant_pre_process(args.fp32, pre, skip_symbolic_shape=False)
        results.append({"variant": "preprocessed", "file": pre,
                        "bytes": os.path.getsize(pre)})
        print(f"pre-processed -> {pre}  {os.path.getsize(pre):,} bytes")

    statics = {
        "static": {"reduce_range": False, "calib_per_type": args.calib_per_type},
        "static_reduce": {"reduce_range": True, "calib_per_type": args.calib_per_type},
        "static_full": {"reduce_range": False, "calib_per_type": 100},
    }
    for name in args.variants:
        if not name.startswith("static") or name not in statics:
            continue
        opts = statics[name]
        static = os.path.join(args.out_dir, f"crnn_int8_{name}.onnx")
        t0 = time.time()
        try:
            reader = make_calibration_reader(args, calib_per_type=opts["calib_per_type"])
            quantize_static(pre, static, calibration_data_reader=reader,
                            quant_format="QDQ", per_channel=True,
                            reduce_range=opts["reduce_range"],
                            activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8,
                            extra_options={"ActivationSymmetric": False,
                                           "WeightSymmetric": True,
                                           "EnableSubgraph": False,
                                           "ForceQuantizeNoInputCheck": False})
            results.append({"variant": name, "file": static,
                            "bytes": os.path.getsize(static),
                            "reduce_range": opts["reduce_range"],
                            "calib_per_type": opts["calib_per_type"],
                            "seconds": round(time.time() - t0, 1)})
            print(f"static int8 [{name}] -> {static}  {os.path.getsize(static):,} bytes  "
                  f"{time.time()-t0:.1f}s")
        except Exception as e:  # a failed variant is a fact, not a crash
            results.append({"variant": name, "file": None, "error": f"{type(e).__name__}: {e}"})
            print(f"static int8 [{name}] FAILED: {type(e).__name__}: {e}")

    results.insert(0, {"variant": "fp32", "file": args.fp32,
                       "bytes": os.path.getsize(args.fp32)})
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump({"fp32": args.fp32, "variants": results}, f, indent=1)
    print(f"wrote {args.report}")
    return 0


def make_calibration_reader(args, calib_per_type=None):
    """The calibration set: bands of our own pictures (the trained types)."""
    from onnxruntime.quantization import CalibrationDataReader
    import numpy as np
    from captcha_crnn import CaptchaDataset, collate
    import torch

    cs = build_encoder(CHARSET)
    items = build_eval_items(args.calib_types or TRAINED_TYPES,
                             limit_per_type=calib_per_type or args.calib_per_type)
    ds = CaptchaDataset(items, cs.encode, augment=False)
    loader = torch.utils.data.DataLoader(ds, batch_size=8, shuffle=False,
                                         collate_fn=collate, num_workers=2)
    pieces = []
    for batch in loader:
        arr = batch["images"].numpy().astype(np.float32)
        for i, w in enumerate(batch["widths"].tolist()):
            pieces.append(arr[i:i + 1, :, :, :w])
    width = int(max(p.shape[3] for p in pieces))
    x = np.zeros((len(pieces), 1, 32, width), dtype=np.float32)
    for i, p in enumerate(pieces):
        x[i, :, :, :p.shape[3]] = p
    # the calibration reader hands the data over one item at a time, and the static
    # quantiser concatenates them - so all the items have to share one width. The
    # width axis of the model is dynamic, so padding to the widest band is legal.
    print(f"calibration set: {x.shape[0]} bands, width {x.shape[3]}, "
          f"from {len(args.calib_types or TRAINED_TYPES)} types")

    class Reader(CalibrationDataReader):
        def __init__(self, data):
            self.data = data
            self.i = 0

        def get_next(self):
            if self.i >= self.data.shape[0]:
                return None
            item = {"image": self.data[self.i:self.i + 1]}
            self.i += 1
            return item

    return Reader(x)


# --------------------------------------------------------------------------- evaluation

def cmd_eval(args):
    import torch
    import onnxruntime as ort

    cs = build_encoder(CHARSET)
    items = build_eval_items(args.types, limit_per_type=args.limit_per_type)
    batches = make_batches(items, cs, batch_size=args.batch_size)
    n_items = sum(b["images"].shape[0] for b in batches)
    print(f"evaluating {args.model} on {n_items} bands of {len(args.types)} types")

    so = ort.SessionOptions()
    so.intra_op_num_threads = args.threads
    so.inter_op_num_threads = 1
    sess = ort.InferenceSession(args.model, so, providers=["CPUExecutionProvider"])

    per_type = {}
    conf_sum = {}
    examples = []
    for batch in batches:
        images = batch["images"].numpy().astype(np.float32)
        logits = sess.run(None, {"image": images})[0]
        preds = greedy_decode_np(logits)
        offset = 0
        for i, (pred, conf) in enumerate(preds):
            gold = cs.decode(batch["labels"][offset:offset + int(batch["lengths"][i])].tolist())
            typ = batch["types"][i]
            d = per_type.setdefault(typ, {"n": 0, "exact": 0, "cer": 0.0, "conf": 0.0})
            d["n"] += 1
            d["exact"] += int(pred == gold)
            c = cer(pred, gold)
            d["cer"] += c if c is not None else 0.0
            d["conf"] += conf
            if len(examples) < 12 and pred != gold:
                examples.append({"type": typ, "gold": gold, "pred": pred,
                                 "cer": c, "conf": round(conf, 4)})
            offset += int(batch["lengths"][i])
    overall, per_type_out = summarise(per_type)
    for typ, d in per_type.items():
        d["conf"] = d["conf"] / max(1, d["n"])
        per_type_out[typ]["confidence"] = d["conf"]

    report = {
        "model": args.model,
        "bytes": os.path.getsize(args.model),
        "backend": "onnxruntime CPU",
        "protocol": "reports/TRAINING_MINIMAL_LATIN.md (band crop, glyph 32, greedy CTC)",
        "overall": overall,
        "trained_types": group_median(per_type_out, TRAINED_TYPES),
        "held_out_types": group_median(per_type_out, HELD_OUT_TYPES),
        "per_type": per_type_out,
        "wrong_examples": examples,
    }
    print(json.dumps({"overall": overall,
                      "trained": report["trained_types"],
                      "held_out": report["held_out_types"]}, indent=1))
    for typ, d in sorted(per_type_out.items()):
        print(f"  {typ:52s} acc {d['accuracy']:.3f}  cer {d['cer']:.3f}  n={d['n']}")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f"wrote {args.out}")
    return 0


def cmd_eval_torch(args):
    """The same protocol with PyTorch - the reference the ONNX numbers are compared to."""
    import torch
    from captcha_crnn import greedy_decode

    cs = build_encoder(CHARSET)
    model, cs, state = load_checkpoint(args.ckpt, device=args.device)
    items = build_eval_items(args.types, limit_per_type=args.limit_per_type)
    batches = make_batches(items, cs, batch_size=args.batch_size)
    n_items = sum(b["images"].shape[0] for b in batches)
    print(f"evaluating {args.ckpt} (torch) on {n_items} bands of {len(args.types)} types")

    per_type = {}
    with torch.no_grad():
        for batch in batches:
            images = batch["images"].to(args.device)
            logits, _t = model(images)
            preds = greedy_decode(logits.float().cpu(), cs.decode)
            offset = 0
            for i, (pred, conf) in enumerate(preds):
                gold = cs.decode(batch["labels"][offset:offset + int(batch["lengths"][i])].tolist())
                typ = batch["types"][i]
                d = per_type.setdefault(typ, {"n": 0, "exact": 0, "cer": 0.0, "conf": 0.0})
                d["n"] += 1
                d["exact"] += int(pred == gold)
                c = cer(pred, gold)
                d["cer"] += c if c is not None else 0.0
                d["conf"] += conf
                offset += int(batch["lengths"][i])
    for d in per_type.values():
        d["conf"] = d["conf"] / max(1, d["n"])
    overall, per_type_out = summarise(per_type)
    for typ, d in per_type.items():
        per_type_out[typ]["confidence"] = d["conf"]
    report = {"model": args.ckpt, "backend": "pytorch " + args.device,
              "overall": overall,
              "trained_types": group_median(per_type_out, TRAINED_TYPES),
              "held_out_types": group_median(per_type_out, HELD_OUT_TYPES),
              "per_type": per_type_out}
    print(json.dumps({"overall": overall,
                      "trained": report["trained_types"],
                      "held_out": report["held_out_types"]}, indent=1))
    for typ, d in sorted(per_type_out.items()):
        print(f"  {typ:52s} acc {d['accuracy']:.3f}  cer {d['cer']:.3f}  n={d['n']}")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f"wrote {args.out}")
    return 0


# --------------------------------------------------------------------------- speed

def make_batches_for_speed(arrays, bs):
    """Group the bands into batches of `bs`, padded to the width of their batch.

    The padding is what the trainer does too (the collate pads to the widest band
    of the batch), so a batched number includes the cost of the padding.
    """
    out = []
    for off in range(0, len(arrays), bs):
        group = arrays[off:off + bs]
        width = max(g.shape[3] for g in group)
        if any(g.shape[3] != width for g in group):
            padded = np.zeros((len(group), 1, 32, width), dtype=np.float32)
            for i, g in enumerate(group):
                padded[i, :, :, :g.shape[3]] = g
            group = [padded]
        out.append(np.concatenate(group, axis=0))
    return out


def cmd_speed(args):
    import torch
    import onnxruntime as ort

    cs = build_encoder(CHARSET)
    items = build_eval_items(args.types, limit_per_type=args.limit_per_type)
    batches = make_batches(items, cs, batch_size=args.batch_size)
    # the speed set: the tensors as the runtime sees them, one band per image
    arrays = []
    for b in batches:
        arr = b["images"].numpy().astype(np.float32)
        for i in range(arr.shape[0]):
            w = int(b["widths"][i])
            arrays.append(arr[i:i + 1, :, :, :w])
    print(f"speed set: {len(arrays)} bands, widths {min(a.shape[3] for a in arrays)}"
          f"..{max(a.shape[3] for a in arrays)}")

    results = []

    # -- PyTorch on the GPU
    if torch.cuda.is_available():
        model, _cs, _st = load_checkpoint(args.ckpt, device="cuda")
        for bs in (1, 32):
            feeds = make_batches_for_speed(arrays, bs)
            xs = [torch.from_numpy(f).cuda() for f in feeds]
            with torch.no_grad():
                for x in xs:
                    model(x)
                torch.cuda.synchronize()
                reps = []
                for _ in range(args.repeats):
                    t0 = time.time()
                    for x in xs:
                        model(x)
                    torch.cuda.synchronize()
                    reps.append(time.time() - t0)
            n = sum(int(x.shape[0]) for x in xs)
            results.append({"backend": f"pytorch cuda fp32 (batch {bs})",
                            "threads": "-", "images": n,
                            "img_per_s": round(n / statistics.mean(reps), 1),
                            "mean_s": round(statistics.mean(reps), 4),
                            "std_s": round(statistics.pstdev(reps), 4),
                            "min_s": round(min(reps), 4), "max_s": round(max(reps), 4)})
            print(f"  pytorch cuda fp32 batch {bs}: {results[-1]['img_per_s']} img/s")
        del model
        torch.cuda.empty_cache()

    # -- PyTorch on the CPU
    torch.set_num_threads(args.torch_threads)
    model, _cs, _st = load_checkpoint(args.ckpt, device="cpu")
    for bs in (1,):
        feeds = make_batches_for_speed(arrays, bs)
        xs = [torch.from_numpy(f) for f in feeds]
        with torch.no_grad():
            for x in xs:
                model(x)
            reps = []
            for _ in range(args.repeats):
                t0 = time.time()
                for x in xs:
                    model(x)
                reps.append(time.time() - t0)
        n = sum(int(x.shape[0]) for x in xs)
        results.append({"backend": f"pytorch cpu fp32 (batch {bs})",
                        "threads": args.torch_threads, "images": n,
                        "img_per_s": round(n / statistics.mean(reps), 1),
                        "mean_s": round(statistics.mean(reps), 4),
                        "std_s": round(statistics.pstdev(reps), 4),
                        "min_s": round(min(reps), 4), "max_s": round(max(reps), 4)})
        print(f"  pytorch cpu fp32 batch {bs}: {results[-1]['img_per_s']} img/s")
    del model

    # -- ONNX Runtime on the CPU, every model and every thread count
    for model_path in args.models:
        for threads in args.ort_threads:
            so = ort.SessionOptions()
            so.intra_op_num_threads = threads
            so.inter_op_num_threads = 1
            so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess = ort.InferenceSession(model_path, so, providers=["CPUExecutionProvider"])
            for bs in (1, 32):
                feeds = make_batches_for_speed(arrays, bs)
                sess.run(None, {"image": feeds[0]})
                reps = []
                for _ in range(args.repeats):
                    t0 = time.time()
                    for f in feeds:
                        sess.run(None, {"image": f})
                    reps.append(time.time() - t0)
                n = sum(f.shape[0] for f in feeds)
                entry = {"backend": f"onnxruntime cpu {os.path.basename(model_path)} (batch {bs})",
                         "threads": threads, "images": n,
                         "img_per_s": round(n / statistics.mean(reps), 1),
                         "mean_s": round(statistics.mean(reps), 4),
                         "std_s": round(statistics.pstdev(reps), 4),
                         "min_s": round(min(reps), 4), "max_s": round(max(reps), 4)}
                results.append(entry)
                print(f"  {entry['backend']} threads={threads}: {entry['img_per_s']} img/s")

    report = {"speed_set": {"bands": len(arrays),
                             "width_min": int(min(a.shape[3] for a in arrays)),
                             "width_max": int(max(a.shape[3] for a in arrays)),
                             "types": args.types},
              "repeats": args.repeats,
              "results": results}
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f"wrote {args.out}")
    return 0


# --------------------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("export")
    p.add_argument("--ckpt", default=os.path.join(REPO, "train", "run", "main", "ckpt",
                                                   "step_0005700.pt"))
    p.add_argument("--out", default=os.path.join(REPO, "bench", "models", "crnn_fp32.onnx"))
    p.add_argument("--config", default=os.path.join(REPO, "bench", "models", "config.json"))
    p.add_argument("--report", default=os.path.join(REPO, "reports", "bench_models",
                                                     "T2_export_parity.json"))
    p.add_argument("--opset", type=int, default=17)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("quantize")
    p.add_argument("--fp32", default=os.path.join(REPO, "bench", "models", "crnn_fp32.onnx"))
    p.add_argument("--out-dir", default=os.path.join(REPO, "bench", "models"))
    p.add_argument("--report", default=os.path.join(REPO, "reports", "bench_models",
                                                     "T2_quantization.json"))
    p.add_argument("--calib-types", nargs="*", default=TRAINED_TYPES)
    p.add_argument("--calib-per-type", type=int, default=20)
    p.add_argument("--variants", nargs="*",
                   default=["dynamic", "static", "static_reduce", "static_full"],
                   choices=["dynamic", "static", "static_reduce", "static_full"])
    p.set_defaults(func=cmd_quantize)

    p = sub.add_parser("eval")
    p.add_argument("--model", required=True)
    p.add_argument("--types", nargs="*", default=ALL_TYPES)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--limit-per-type", type=int, default=None)
    p.add_argument("--threads", type=int, default=8)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("eval-torch")
    p.add_argument("--ckpt", default=os.path.join(REPO, "train", "run", "main", "ckpt",
                                                   "step_0005700.pt"))
    p.add_argument("--types", nargs="*", default=ALL_TYPES)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--limit-per-type", type=int, default=None)
    p.add_argument("--device", default="cuda")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_eval_torch)

    p = sub.add_parser("speed")
    p.add_argument("--ckpt", default=os.path.join(REPO, "train", "run", "main", "ckpt",
                                                   "step_0005700.pt"))
    p.add_argument("--models", nargs="*", default=[])
    p.add_argument("--types", nargs="*", default=TRAINED_TYPES)
    p.add_argument("--limit-per-type", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--torch-threads", type=int, default=8)
    p.add_argument("--ort-threads", nargs="*", type=int, default=[1, 4, 8, 18])
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_speed)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
