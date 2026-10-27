"""The verification of the export: the training code, the exported code, a fresh
process and the ONNX graph must all agree.

The export is verified, not assumed: the script loads the checkpoint back, runs the
*training* code and the *exported* code on the same images and compares the decoded
strings; then it re-loads the repository in a **fresh process** through `AutoModel` /
`AutoProcessor` and compares again; then it runs the ONNX through `onnxruntime` and
compares a third time. A silent mismatch is the classic way an export goes wrong, so
the script fails loudly instead of writing a model card.
"""

import json
import os
import subprocess
import sys

import numpy as np
import torch

from .common import ENTRY_SCRIPT, TRAIN_DIR, find_types, log, read_labels
from .writer import import_from_dir


def pick_samples(charset: str, n: int, roots: list[str]) -> list[dict]:
    """Pick a spread of labelled images across the dataset trees.

    A type that has a text band contributes a banded sample (that is the interesting
    path); a type without one contributes a whole frame.
    """
    table = {c: i for i, c in enumerate(charset)}
    types = find_types(roots)
    if not types:
        return []
    step = max(1, len(types) // max(1, n))
    picked = types[::step][:n]
    samples = []
    for type_id, directory, _root in picked:
        try:
            rows = read_labels(directory)
        except OSError:
            continue
        if not rows:
            continue
        banded = [r for r in rows if r.get("roi")]
        row = (banded or rows)[0]
        text = row.get("text") or row.get("answer") or ""
        if not text or any(c not in table for c in text):
            continue
        if len(text) > 12:
            continue
        samples.append({
            "type": type_id,
            "path": os.path.join(directory, row["file"]),
            "roi": row.get("roi"),
            "text": text,
            "answer": row.get("answer", text),
        })
    return samples


# =====================================================================================
# The reference implementation - the training code
# =====================================================================================
def training_reference(items: list[dict], state: dict, charset: str, glyph_height: int):
    """The predictions the *training* code produces for these items.

    This is the ground truth the export is checked against: the same checkpoint, the
    same dataset class, the same greedy decode.
    """
    if TRAIN_DIR not in sys.path:
        sys.path.insert(0, TRAIN_DIR)
    from captcha_crnn import CRNN, CaptchaDataset, build_encoder, collate, greedy_decode

    cs = build_encoder(charset)
    model = CRNN(cs.num_classes, glyph_height=glyph_height)
    model.load_state_dict(state)
    model.eval()

    dataset = CaptchaDataset(items, cs.encode, glyph_height=glyph_height, augment=False)
    batch = collate([dataset[i] for i in range(len(items))])
    with torch.no_grad():
        logits, _ = model(batch["images"])
    return greedy_decode(logits.float(), cs.decode), batch


def exported_predictions(out_dir: str, samples: list[dict], model=None, processor=None):
    """The predictions of the *exported* code, in this process."""
    if model is None or processor is None:
        modeling = import_from_dir(out_dir, "modeling_captcha")
        processing = import_from_dir(out_dir, "processing_captcha")
        model = modeling.CaptchaModel.from_pretrained(out_dir)
        processor = processing.CaptchaProcessor.from_pretrained(out_dir)
    model.eval()
    images = [s["path"] for s in samples]
    rois = [s["roi"] for s in samples]
    texts = [s["text"] for s in samples]
    inputs = processor(images=images, roi=rois, text=texts, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
    return model.greedy_decode(logits)


def fresh_process_predictions(out_dir: str, samples: list[dict], spec_path: str) -> list[list]:
    """Load the repository in a **fresh process** through AutoModel / AutoProcessor."""
    cmd = [sys.executable, ENTRY_SCRIPT,
           "--_load-check", out_dir, "--_load-check-spec", spec_path]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if proc.returncode != 0:
        raise RuntimeError(f"the fresh-process load failed:\n{proc.stdout}\n{proc.stderr}")
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    return payload["preds"]


def load_check(out_dir: str, spec_path: str) -> int:
    """The child process of `fresh_process_predictions`: load and predict."""
    from transformers import AutoModel, AutoProcessor

    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    model = AutoModel.from_pretrained(out_dir, trust_remote_code=True).eval()
    processor = AutoProcessor.from_pretrained(out_dir, trust_remote_code=True)
    inputs = processor(images=[s["path"] for s in spec["samples"]],
                       roi=[s["roi"] for s in spec["samples"]],
                       text=[s["text"] for s in spec["samples"]],
                       return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
    preds = model.greedy_decode(logits)
    print(json.dumps({"preds": [[t, c] for t, c in preds],
                      "model_class": type(model).__name__,
                      "processor_class": type(processor).__name__}))
    return 0


def onnx_predictions(out_dir: str, batch: dict) -> list[list]:
    """The predictions of the ONNX graph, through onnxruntime."""
    import onnxruntime as ort

    path = os.path.join(out_dir, "onnx", "model.onnx")
    sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    x = batch["images"].numpy().astype(np.float32)
    logits = sess.run(None, {name: x})[0]
    with open(os.path.join(out_dir, "vocab.json"), encoding="utf-8") as f:
        vocab = json.load(f)
    itos = vocab["itos"]
    blank = vocab["blank_index"]
    preds = []
    for b in range(logits.shape[0]):
        ids = logits[b].argmax(axis=-1)
        chars, prev = [], -1
        for k in ids:
            k = int(k)
            if k != prev and k != blank:
                chars.append(itos.get(str(k), ""))
            prev = k
        preds.append(["".join(chars), 0.0])
    return preds


def verify(out_dir: str, samples: list[dict], ckpt_state: dict, charset: str,
           cfg: dict, report: dict) -> dict:
    """The three-way check: the training code, the exported code, a fresh process, ONNX."""
    log("")
    log(f"verifying on {len(samples)} images from the dataset")

    # -- 1. the training code is the reference -----------------------------------
    items = [{"type": s["type"], "path": s["path"], "text": s["text"],
              "answer": s["answer"], "roi": s["roi"], "type_id": s["type"]}
             for s in samples]
    ref_preds, batch = training_reference(items, ckpt_state, charset, cfg["glyph_height"])
    ref = [p[0] for p in ref_preds]
    log(f"  training code : {ref}")

    # -- 2. the exported code, in this process ------------------------------------
    exp_preds = exported_predictions(out_dir, samples)
    exp = [p[0] for p in exp_preds]
    same = sum(1 for a, b in zip(ref, exp) if a == b)
    log(f"  exported code : {exp}")
    log(f"  training code vs exported code: {same}/{len(ref)} identical")
    if same != len(ref):
        for s, a, b in zip(samples, ref, exp):
            if a != b:
                log(f"    MISMATCH {s['type']} {os.path.basename(s['path'])}: "
                    f"training={a!r} exported={b!r}")
    report["parity_training_vs_exported"] = f"{same}/{len(ref)}"

    # -- 3. a fresh process, through AutoModel / AutoProcessor --------------------
    spec_path = os.path.join(out_dir, "..", "_load_check_spec.json")
    spec_path = os.path.abspath(spec_path)
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump({"samples": samples}, f)
    try:
        fresh = fresh_process_predictions(out_dir, samples, spec_path)
        fresh_texts = [p[0] for p in fresh]
        same_fresh = sum(1 for a, b in zip(ref, fresh_texts) if a == b)
        log(f"  fresh process (AutoModel + AutoProcessor, trust_remote_code=True): "
            f"{fresh_texts}")
        log(f"  training code vs fresh process: {same_fresh}/{len(ref)} identical")
        report["parity_fresh_process"] = f"{same_fresh}/{len(ref)}"
    except Exception as exc:  # noqa: BLE001
        log(f"  fresh process load FAILED: {type(exc).__name__}: {exc}")
        report["parity_fresh_process"] = f"FAILED: {exc}"
        same_fresh = -1
    finally:
        if os.path.exists(spec_path):
            os.remove(spec_path)

    # -- 4. the ONNX graph --------------------------------------------------------
    try:
        onnx_preds = onnx_predictions(out_dir, batch)
        onnx_texts = [p[0] for p in onnx_preds]
        same_onnx = sum(1 for a, b in zip(ref, onnx_texts) if a == b)
        log(f"  onnxruntime   : {onnx_texts}")
        log(f"  training code vs onnxruntime: {same_onnx}/{len(ref)} identical")
        report["parity_onnx"] = f"{same_onnx}/{len(ref)}"
    except Exception as exc:  # noqa: BLE001
        log(f"  onnxruntime FAILED: {type(exc).__name__}: {exc}")
        report["parity_onnx"] = f"FAILED: {exc}"
        same_onnx = -1

    report["samples"] = [{"type": s["type"], "file": os.path.basename(s["path"]),
                          "roi": s["roi"], "gold": s["text"],
                          "training": a, "exported": b}
                         for s, a, b in zip(samples, ref, exp)]
    ok = same == len(ref) and same_fresh == len(ref) and same_onnx == len(ref)
    report["all_three_agree"] = ok
    log("")
    log("VERIFICATION " + ("PASSED" if ok else "FAILED"))
    return report
