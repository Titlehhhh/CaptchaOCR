"""T1 harness: run READY-MADE captcha/OCR models on OUR dataset under ONE protocol.

This is a *new* harness (the brief allows `bench/bench_models.py`). It does not
touch `bench/bench_hf.py`, `bench/bench_others.py` or `bench/bench_onnx.py`.

Protocol (identical for every model):

  * **Item sets** - built from `dataset/out` + `dataset/out_ru`, `labels.jsonl`:
      - ``full``       : all 46 types x N samples (N default 20) = 920 items
      - ``legacy104``  : the 13 types x 8 samples of the old bench (104 items)
      - ``legacy64``   : the 8 band-carrying types x 8 samples of the old bench
                         (64 items) - the set the published 0.156 / 0.125 / 0.047
                         baselines were re-scored on
  * **Input modes** - ``band`` (the `roi` crop from labels.jsonl; the whole frame
    for the 17 types that have no band) and ``frame`` (the whole PNG). The two
    are never mixed: they are separate result blocks.
  * **Metrics** - exact match and CER, per type, then
      - micro (over items),
      - macro-median (median over the per-type values - the brief asks for the
        median, not the mean),
      - separately for the 29 types that carry a band and the 17 that do not.
  * **Ground truth** - the *drawn* string (`text`) is primary, because that is
    what an OCR model can possibly read; the *answer* (the solved captcha) is
    reported as a second column. The two differ in 8 of the 46 types.

Everything that is measured is written to `reports/bench_models/<model>.json`
(model, weights revision, preprocessing, library versions, per-type metrics,
every prediction). The old `reports/bench_results*.json` are never touched.

Usage:
    .venv-gpu\\Scripts\\python.exe bench\\bench_models.py --models grafj-crnn,ppocrv5
    python bench\\bench_models.py --models easyocr          # system python (CPU)
    .venv-gpu\\Scripts\\python.exe bench\\bench_models.py --contact-sheet <slug>
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import OUT, OUT_RU, REPORTS  # noqa: E402

# The HF cache must live inside the workspace: the sandbox that runs the
# python processes cannot write to %USERPROFILE%\\.cache.
os.environ.setdefault("HF_HOME", os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "build", "hf_cache"))

RESULTS_DIR = os.path.join(REPORTS, "bench_models")
# The user's pre-existing Hugging Face cache: read-only, but readable. An explicit
# HF_HUB_CACHE wins; otherwise the default location of the platform is used.
# It is deliberately NOT the HF_HOME set above - that one points into the workspace.
OLD_HUB = os.environ.get("HF_HUB_CACHE") or os.path.join(
    os.path.expanduser("~"), ".cache", "huggingface", "hub")

# The 13 types of the old benchmark (bench/bench_hf.py: TEXT_TYPES).
LEGACY_TYPES = [
    "Archy-X/Krypton/map",
    "InstantlyMoist/Captcha/textcaptcha",
    "JSH32/Minecaptcha/map",
    "haq/mapcha/map",
    "LagBug/XProtect/code",
    "LagBug/XProtect/map",
    "irootdev/AnBot/captcha",
    "jonesdevelopment/sonar/standard",
    "jSdCool/minecaptcha/text",
    "just-captcha/ProstoCaptcha/map",
    "laforetbrut/are-you-sure/code",
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA/map",
    "n1zamu/NCaptcha/anvil",
]


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def norm(s) -> str:
    """Unicode-aware normalisation of an OCR string.

    Keeps letters and digits of *any* script plus the arithmetic operators, and
    drops everything else (spaces, punctuation, artefacts).  The old harness
    used ``re.sub(r"[^A-Za-z0-9+\\-*]", "", s)``, which silently emptied every
    Cyrillic sample; that is why the old numbers only cover ASCII types.
    """
    if s is None:
        return ""
    out = []
    for ch in str(s):
        if ch.isalnum() or ch in "+-*/=×÷":
            out.append(ch)
    return "".join(out)


def lev(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(pred, gold) -> float | None:
    p, g = norm(pred), norm(gold)
    if not g:
        return None
    return lev(p, g) / len(g)


# --------------------------------------------------------------------------- #
# items
# --------------------------------------------------------------------------- #
def _read_types():
    """All 46 captcha types: (type_id, folder, rows)."""
    out = []
    for root, tag in ((OUT, "out"), (OUT_RU, "out_ru")):
        for lj in sorted(glob.glob(os.path.join(root, "**", "labels.jsonl"), recursive=True)):
            d = os.path.dirname(lj)
            rel = os.path.relpath(d, root).replace(os.sep, "/")
            rows = []
            with open(lj, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
            out.append((f"{tag}/{rel}", d, rows))
    return out


def _spread(n_rows: int, n_take: int):
    """Deterministic, evenly spread row indices (0 .. n_rows-1)."""
    if n_take <= 1:
        return [0]
    if n_rows <= n_take:
        return list(range(n_rows))
    return [round(k * (n_rows - 1) / (n_take - 1)) for k in range(n_take)]


def build_items(set_name: str, n_per_type: int):
    """Build one item set. Every item carries its band, the drawn text and the answer."""
    types = _read_types()
    items = []
    if set_name == "full":
        wanted = None
        take = n_per_type
        head = 0
    elif set_name == "legacy104":
        wanted = set(LEGACY_TYPES)
        take = 8
        head = 0
    elif set_name == "legacy64":
        wanted = set(LEGACY_TYPES)
        take = 8
        head = 0
    else:
        raise ValueError(set_name)

    for tid, folder, rows in types:
        short = tid.split("/", 1)[1]
        if wanted is not None and short not in wanted:
            continue
        if set_name == "legacy64" and not any(r.get("roi") for r in rows[:8]):
            continue
        idxs = _spread(len(rows), take) if set_name == "full" else list(range(min(take, len(rows))))
        for i in idxs:
            r = rows[i]
            items.append({
                "type": tid,
                "path": os.path.join(folder, r["file"]),
                "file": r["file"],
                "answer": str(r.get("answer", "")),
                "text": str(r.get("text") or r.get("answer", "")),
                "roi": r.get("roi"),
                "has_roi": bool(r.get("roi")),
            })
    return items


def load_input(item, mode: str):
    """The picture the model sees. 'band' = the roi crop, 'frame' = the whole PNG."""
    from PIL import Image
    img = Image.open(item["path"]).convert("RGB")
    if mode == "band" and item["roi"]:
        x, y, w, h = item["roi"]
        x = max(0, min(x, img.width - 1))
        y = max(0, min(y, img.height - 1))
        w = max(1, min(w, img.width - x))
        h = max(1, min(h, img.height - y))
        img = img.crop((x, y, x + w, y + h))
    return img


# --------------------------------------------------------------------------- #
# aggregation
# --------------------------------------------------------------------------- #
def aggregate(items, preds):
    """Per-type and overall exact-match / CER, split by 'has a band'."""
    per_type = {}
    for it, pr in zip(items, preds):
        t = it["type"]
        d = per_type.setdefault(t, {"n": 0, "exact": 0, "cer_sum": 0.0,
                                    "exact_ans": 0, "cer_ans_sum": 0.0,
                                    "has_roi": it["has_roi"]})
        d["n"] += 1
        c = cer(pr, it["text"])
        ca = cer(pr, it["answer"])
        if c is not None:
            d["cer_sum"] += c
            d["exact"] += int(norm(pr) == norm(it["text"]))
        if ca is not None:
            d["cer_ans_sum"] += ca
            d["exact_ans"] += int(norm(pr) == norm(it["answer"]))

    def block(rows):
        if not rows:
            return None
        accs = [d["exact"] / max(d["n"], 1) for d in rows]
        cers = [d["cer_sum"] / max(d["n"], 1) for d in rows]
        n = sum(d["n"] for d in rows)
        ex = sum(d["exact"] for d in rows)
        cs = sum(d["cer_sum"] for d in rows)
        exa = sum(d["exact_ans"] for d in rows)
        csa = sum(d["cer_ans_sum"] for d in rows)
        return {
            "types": len(rows),
            "items": n,
            "acc_micro": round(ex / max(n, 1), 4),
            "cer_micro": round(cs / max(n, 1), 4),
            "acc_micro_answer": round(exa / max(n, 1), 4),
            "cer_micro_answer": round(csa / max(n, 1), 4),
            "acc_median_over_types": round(statistics.median(accs), 4),
            "cer_median_over_types": round(statistics.median(cers), 4),
            "acc_mean_over_types": round(statistics.fmean(accs), 4),
            "cer_mean_over_types": round(statistics.fmean(cers), 4),
            "types_with_acc_1": sum(1 for a in accs if a >= 0.999),
            "types_with_acc_0": sum(1 for a in accs if a <= 0.001),
        }

    band_rows = [d for d in per_type.values() if d["has_roi"]]
    noband_rows = [d for d in per_type.values() if not d["has_roi"]]
    blocks = {
        "roi_types": block(band_rows),
        "no_roi_types": block(noband_rows),
        "all_types": block(list(per_type.values())),
    }
    for d in per_type.values():
        n = max(d["n"], 1)
        d["acc"] = round(d["exact"] / n, 4)
        d["cer"] = round(d["cer_sum"] / n, 4)
        d["acc_answer"] = round(d["exact_ans"] / n, 4)
        d["cer_answer"] = round(d["cer_ans_sum"] / n, 4)
        del d["exact"], d["cer_sum"], d["exact_ans"], d["cer_ans_sum"]
    return {
        "per_type": per_type,
        **blocks,
    }


# --------------------------------------------------------------------------- #
# download helper (the pre-existing user cache is read-only, but readable)
# --------------------------------------------------------------------------- #
def hf_file(repo: str, filename: str):
    """Return (path, revision) for a file of a HF repo.

    The user's pre-existing Hugging Face cache (~/.cache/huggingface/hub, or
    $HF_HUB_CACHE when it is set) is readable but not writable by the
    sandboxed python process, so it is used as-is when the file is already
    there; everything else is downloaded into the workspace cache
    (build/hf_cache).
    """
    from huggingface_hub import hf_hub_download
    slug = "models--" + repo.replace("/", "--")
    snapdir = os.path.join(OLD_HUB, slug, "snapshots")
    if os.path.isdir(snapdir):
        for rev in sorted(os.listdir(snapdir)):
            p = os.path.join(snapdir, rev, filename)
            if os.path.isfile(p):
                return p, rev
    p = hf_hub_download(repo, filename)
    rev = os.path.basename(os.path.dirname(os.path.dirname(p)))
    return p, rev


def repo_revision(repo: str):
    try:
        from huggingface_hub import HfApi
        return HfApi().model_info(repo).sha
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# backends
# --------------------------------------------------------------------------- #
def backend_ppocr_onnx(repo, items, mode, meta):
    """PaddleOCR rec-models in ONNX (PP-OCRv5/v6, cyrillic_PP-OCRv5).

    Preprocessing follows the model's own `inference.yml`:
    DecodeImage(img_mode=BGR) -> RecResizeImg(image_shape=[3,48,320]).
    The character dictionary is taken from the same `inference.yml`
    (`PostProcess.character_dict`); CTCLabelDecode maps index 0 to the blank.
    """
    import numpy as np
    import onnxruntime as ort
    import yaml

    onnx_path, rev_file = hf_file(repo, "inference.onnx")
    yml_path, _ = hf_file(repo, "inference.yml")
    cfg = yaml.safe_load(open(yml_path, encoding="utf-8"))
    chars = cfg["PostProcess"]["character_dict"]
    character = ["<blank>"] + list(chars) + [" "]          # CTCLabelDecode
    img_shape = cfg["PreProcess"]["transform_ops"][2]["RecResizeImg"]["image_shape"]
    img_mode = cfg["PreProcess"]["transform_ops"][0]["DecodeImage"]["img_mode"]
    imgC, imgH, imgW = img_shape

    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name

    from PIL import Image
    preds, lat = [], []
    for it in items:
        img = load_input(it, mode)
        w, h = img.size
        resize_w = max(1, min(int(round(imgH * (w / float(h)))), imgW))
        arr = np.asarray(img.resize((resize_w, imgH), Image.BILINEAR), dtype=np.float32)
        if img_mode == "BGR":
            arr = arr[:, :, ::-1]
        arr = arr.transpose(2, 0, 1) / 255.0
        arr = (arr - 0.5) / 0.5
        pad = np.zeros((imgC, imgH, imgW), dtype=np.float32)
        pad[:, :, :resize_w] = arr
        x = pad[None]
        t0 = time.perf_counter()
        logits = sess.run(None, {in_name: x})[0][0]        # (T, C)
        idx = logits.argmax(-1)
        chars_out, prev = [], None
        for i in idx:
            i = int(i)
            if i != 0 and i != prev:
                chars_out.append(character[i] if i < len(character) else "")
            prev = i
        lat.append((time.perf_counter() - t0) * 1000)
        preds.append("".join(chars_out))

    meta["weights"] = {"repo": repo, "revision": repo_revision(repo),
                        "files": {"inference.onnx": onnx_path, "inference.yml": yml_path}}
    meta["preprocessing"] = (f"ResizeImg [3,{imgH},{imgW}] aspect-preserving, {img_mode}, "
                             f"(x/255-0.5)/0.5, zero-pad right; greedy CTC, "
                             f"character_dict from inference.yml ({len(chars)} chars)")
    meta["runtime"] = {"engine": "onnxruntime", "providers": sess.get_providers()}
    return preds, lat


def backend_grafj(repo, items, mode, meta):
    """Graf-J captcha CRNN / conv-transformer (custom code, CTC)."""
    import torch
    from transformers import AutoModel, AutoProcessor

    proc = AutoProcessor.from_pretrained(repo, trust_remote_code=True)
    model = AutoModel.from_pretrained(repo, trust_remote_code=True).eval()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(dev)

    is_ctc = not hasattr(model, "generate")
    preds, lat = [], []
    batch = 16
    with torch.no_grad():
        for s in range(0, len(items), batch):
            chunk = items[s:s + batch]
            imgs = [load_input(it, mode) for it in chunk]
            t0 = time.perf_counter()
            if is_ctc:
                inputs = proc(imgs)
                px = inputs["pixel_values"]
                if not torch.is_tensor(px):
                    px = torch.as_tensor(px)
                logits = model(px.to(dev)).logits
                outs = proc.batch_decode(logits)
                preds.extend(outs)
            else:
                inputs = proc(images=imgs, return_tensors="pt")
                gen = model.generate(**{k: v.to(dev) for k, v in inputs.items()},
                                     max_new_tokens=64)
                preds.extend(proc.batch_decode(gen, skip_special_tokens=True))
            dt = (time.perf_counter() - t0) * 1000 / len(chunk)
            lat.extend([dt] * len(chunk))

    meta["weights"] = {"repo": repo, "revision": repo_revision(repo)}
    meta["preprocessing"] = ("the model's own CaptchaProcessor: grayscale, resize to 150x40, "
                             "ToTensor [0,1]; greedy CTC decode with the model's vocabulary")
    meta["runtime"] = {"torch": torch.__version__, "device": dev,
                       "transformers": __import__("transformers").__version__}
    return preds, lat


def backend_trocr(repo, items, mode, meta):
    """TrOCR line (VisionEncoderDecoder) - transformers."""
    import torch
    from transformers import AutoProcessor

    proc = AutoProcessor.from_pretrained(repo)
    model = None
    last = None
    for loader_name in ("AutoModelForImageTextToText", "TrOCRForConditionalGeneration",
                        "TrOCRForCausalLM", "AutoModelForVision2Seq"):
        try:
            Loader = getattr(__import__("transformers", fromlist=[loader_name]), loader_name)
            model = Loader.from_pretrained(repo).eval()
            last = None
            break
        except Exception as e:
            last = f"{loader_name}: {type(e).__name__}: {e}"
            model = None
    if model is None:
        raise RuntimeError(f"cannot load {repo}; last error: {last}")

    # transformers 5.x: the TrOCRProcessor of a *base* (not fine-tuned) model
    # demands `text`/`text_target` ("You need to specify either `text` or
    # `text_target`"). For inference only the image processor is needed.
    image_processor = None
    try:
        from transformers import TrOCRImageProcessor
        image_processor = TrOCRImageProcessor.from_pretrained(repo)
    except Exception:
        image_processor = None

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(dev)
    preds, lat = [], []
    batch = 16
    with torch.no_grad():
        for s in range(0, len(items), batch):
            chunk = items[s:s + batch]
            imgs = [load_input(it, mode) for it in chunk]
            t0 = time.perf_counter()
            try:
                inputs = proc(images=imgs, return_tensors="pt")
                px = inputs["pixel_values"]
            except Exception as e:
                if image_processor is None:
                    raise
                meta.setdefault("processor_note", f"{type(e).__name__}: {e} -> "
                                                  "fell back to TrOCRImageProcessor")
                px = image_processor(images=imgs, return_tensors="pt").pixel_values
            gen = model.generate(pixel_values=px.to(dev), max_new_tokens=100)
            preds.extend([t.strip() for t in proc.batch_decode(gen, skip_special_tokens=True)])
            dt = (time.perf_counter() - t0) * 1000 / len(chunk)
            lat.extend([dt] * len(chunk))

    meta["weights"] = {"repo": repo, "revision": repo_revision(repo)}
    meta["preprocessing"] = ("the model's own TrOCRProcessor (resize to the processor's "
                             "size); greedy generate, max_new_tokens=100")
    meta["runtime"] = {"torch": torch.__version__, "device": dev,
                       "transformers": __import__("transformers").__version__}
    return preds, lat


def backend_txtcaptcha(repo, items, mode, meta):
    """jtrecenti/txtcaptcha-crnn (CRNN + BiLSTM + CTC, MIT)."""
    import torch
    from txtcaptcha import from_pretrained
    from txtcaptcha.dataset import decode_indices, transform_image

    model = from_pretrained(repo)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(dev).eval()
    preds, lat = [], []
    batch = 16
    with torch.no_grad():
        for s in range(0, len(items), batch):
            chunk = items[s:s + batch]
            imgs = [load_input(it, mode) for it in chunk]
            t0 = time.perf_counter()
            x = transform_image(imgs, height=32).to(dev)
            logits = model(x)                      # (T, B, C)
            idx = logits.argmax(-1).transpose(0, 1)  # (B, T)
            for row in idx:
                preds.append(decode_indices(row.tolist(), model.vocab, collapse=True))
            dt = (time.perf_counter() - t0) * 1000 / len(chunk)
            lat.extend([dt] * len(chunk))

    meta["weights"] = {"repo": repo, "revision": repo_revision(repo)}
    meta["preprocessing"] = ("txtcaptcha.transform_image: RGB, height 32, aspect preserved, "
                             "BILINEAR, ToTensor [0,1]; greedy CTC (blank=0)")
    meta["runtime"] = {"torch": torch.__version__, "device": dev, "package": "txtcaptcha 0.1.0"}
    return preds, lat


def backend_doctr_onnx(repo, items, mode, meta):
    """graycat660/doctr-crnn-vgg16-bn-russian-onnx (docTR CRNN, ru+en, ONNX)."""
    import numpy as np
    import onnxruntime as ort

    onnx_path, _ = hf_file(repo, "model.onnx")
    cfg = json.load(open(hf_file(repo, "config.json")[0], encoding="utf-8"))
    vocab = cfg["vocab"]
    blank = cfg["blank_index"]
    mean = np.asarray(cfg["mean"], dtype=np.float32).reshape(3, 1, 1)
    std = np.asarray(cfg["std"], dtype=np.float32).reshape(3, 1, 1)
    H, W = cfg["input_shape"][1], cfg["input_shape"][2]

    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name

    from PIL import Image
    preds, lat = [], []
    for it in items:
        img = load_input(it, mode)
        w, h = img.size
        scale = min(H / float(h), W / float(w))
        nw, nh = max(1, min(W, int(round(w * scale)))), max(1, min(H, int(round(h * scale))))
        arr = np.asarray(img.resize((nw, nh), Image.BILINEAR), dtype=np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)
        pad = np.zeros((3, H, W), dtype=np.float32)
        pad[:, :nh, :nw] = arr
        x = ((pad - mean) / std)[None]
        t0 = time.perf_counter()
        logits = sess.run(None, {in_name: x})[0][0]
        idx = logits.argmax(-1)
        out, prev = [], None
        for i in idx:
            i = int(i)
            if i != blank and i != prev:
                out.append(vocab[i] if i < len(vocab) else "")
            prev = i
        lat.append((time.perf_counter() - t0) * 1000)
        preds.append("".join(out))

    meta["weights"] = {"repo": repo, "revision": repo_revision(repo),
                        "files": {"model.onnx": onnx_path}}
    meta["preprocessing"] = (f"resize keep-aspect into {H}x{W}, zero-pad bottom/right, /255, "
                             f"(x-mean)/std per channel (config.json); greedy CTC, blank={blank}")
    meta["runtime"] = {"engine": "onnxruntime", "providers": sess.get_providers()}
    return preds, lat


def backend_easyocr(repo, items, mode, meta):
    """EasyOCR/en - the baseline of the old bench (runs in the system python)."""
    import numpy as np
    import easyocr
    rd = easyocr.Reader(["en"], gpu=False, verbose=False)
    preds, lat = [], []
    for it in items:
        img = load_input(it, mode)
        # EasyOCR only accepts a numpy array (cv2/BGR convention) - a PIL image
        # raises "Invalid input type".
        arr = np.asarray(img, dtype=np.uint8)[:, :, ::-1]
        t0 = time.perf_counter()
        res = rd.readtext(arr, detail=0, paragraph=True)
        lat.append((time.perf_counter() - t0) * 1000)
        preds.append(res[0] if res else "")
    meta["weights"] = {"repo": "EasyOCR (JaidedAI/EasyOCR) + en detection/recognition weights",
                       "revision": "en model of easyocr 1.7.2 (bundled with the package)"}
    meta["preprocessing"] = "EasyOCR readtext on the numpy (BGR) band crop (detector + recogniser)"
    meta["runtime"] = {"package": "easyocr 1.7.2", "device": "cpu"}
    return preds, lat


# --------------------------------------------------------------------------- #
# model registry
# --------------------------------------------------------------------------- #
MODELS = {
    "grafj-crnn": {"repo": "Graf-J/captcha-crnn-finetuned", "backend": backend_grafj,
                   "license": "MIT"},
    "grafj-crnn-base": {"repo": "Graf-J/captcha-crnn-base", "backend": backend_grafj,
                        "license": "MIT"},
    "grafj-convtr": {"repo": "Graf-J/captcha-conv-transformer-finetuned",
                     "backend": backend_grafj, "license": "MIT"},
    "anuashok-v3": {"repo": "anuashok/ocr-captcha-v3", "backend": backend_trocr,
                    "license": "Apache-2.0"},
    "trocr-base-printed": {"repo": "microsoft/trocr-base-printed", "backend": backend_trocr,
                           "license": "MIT"},
    "emelnov-mailru": {"repo": "emelnov/ocr-captcha-v4-mailru", "backend": backend_trocr,
                       "license": "(tag not set; base TrOCR = MIT)"},
    "ppocrv5-mobile": {"repo": "PaddlePaddle/PP-OCRv5_mobile_rec_onnx",
                       "backend": backend_ppocr_onnx, "license": "Apache-2.0"},
    "ppocrv5-server": {"repo": "PaddlePaddle/PP-OCRv5_server_rec_onnx",
                       "backend": backend_ppocr_onnx, "license": "Apache-2.0"},
    "ppocrv5-latin": {"repo": "PaddlePaddle/latin_PP-OCRv5_mobile_rec_onnx",
                      "backend": backend_ppocr_onnx, "license": "Apache-2.0"},
    "ppocrv6-medium": {"repo": "PaddlePaddle/PP-OCRv6_medium_rec_onnx",
                       "backend": backend_ppocr_onnx, "license": "Apache-2.0"},
    "ppocrv6-small": {"repo": "PaddlePaddle/PP-OCRv6_small_rec_onnx",
                      "backend": backend_ppocr_onnx, "license": "Apache-2.0"},
    "ppocrv6-tiny": {"repo": "PaddlePaddle/PP-OCRv6_tiny_rec_onnx",
                     "backend": backend_ppocr_onnx, "license": "Apache-2.0"},
    "ppocrv5-cyrillic": {"repo": "PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec_onnx",
                         "backend": backend_ppocr_onnx, "license": "Apache-2.0"},
    "doctr-crnn-ru": {"repo": "graycat660/doctr-crnn-vgg16-bn-russian-onnx",
                      "backend": backend_doctr_onnx, "license": "Apache-2.0"},
    "txtcaptcha-crnn": {"repo": "jtrecenti/txtcaptcha-crnn", "backend": backend_txtcaptcha,
                        "license": "MIT"},
    "easyocr": {"repo": "easyocr", "backend": backend_easyocr, "license": "Apache-2.0"},
}


def slug(key: str) -> str:
    return key.replace("/", "__")


# --------------------------------------------------------------------------- #
# runner
# --------------------------------------------------------------------------- #
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="", help="comma separated keys of MODELS")
    ap.add_argument("--sets", default="full,legacy104,legacy64")
    ap.add_argument("--modes", default="band,frame")
    ap.add_argument("--n", type=int, default=20, help="samples per type in the 'full' set")
    ap.add_argument("--out", default=RESULTS_DIR)
    ap.add_argument("--contact-sheet", default="", help="path of a result json")
    ap.add_argument("--contact-mode", default="band")
    ap.add_argument("--contact-set", default="full")
    args = ap.parse_args()

    if args.contact_sheet:
        base = os.path.splitext(os.path.basename(args.contact_sheet))[0]
        contact_sheet(args.contact_sheet,
                      os.path.join(args.out, f"errors_{base}.png"),
                      mode=args.contact_mode, set_name=args.contact_set)
        return

    keys = [k.strip() for k in args.models.split(",") if k.strip()]
    sets = [s.strip() for s in args.sets.split(",") if s.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for k in keys:
        if k not in MODELS:
            print(f"unknown model key: {k}; known: {', '.join(MODELS)}")
            continue
        print(f"===== {k} ({MODELS[k]['repo']}) =====", flush=True)
        run_model(k, MODELS[k], sets, modes, args.n, args.out)


if __name__ == "__main__":
    main()
