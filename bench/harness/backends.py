
import json
import os
import time

from .config import OLD_HUB
from .items import load_input





def hf_file(repo: str, filename: str):
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





def backend_ppocr_onnx(repo, items, mode, meta):
    import numpy as np
    import onnxruntime as ort
    import yaml

    onnx_path, rev_file = hf_file(repo, "inference.onnx")
    yml_path, _ = hf_file(repo, "inference.yml")
    cfg = yaml.safe_load(open(yml_path, encoding="utf-8"))
    chars = cfg["PostProcess"]["character_dict"]
    character = ["<blank>"] + list(chars) + [" "]
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
        logits = sess.run(None, {in_name: x})[0][0]
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


def backend_doctr_onnx(repo, items, mode, meta):
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





def backend_grafj(repo, items, mode, meta):
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
            logits = model(x)
            idx = logits.argmax(-1).transpose(0, 1)
            for row in idx:
                preds.append(decode_indices(row.tolist(), model.vocab, collapse=True))
            dt = (time.perf_counter() - t0) * 1000 / len(chunk)
            lat.extend([dt] * len(chunk))

    meta["weights"] = {"repo": repo, "revision": repo_revision(repo)}
    meta["preprocessing"] = ("txtcaptcha.transform_image: RGB, height 32, aspect preserved, "
                             "BILINEAR, ToTensor [0,1]; greedy CTC (blank=0)")
    meta["runtime"] = {"torch": torch.__version__, "device": dev, "package": "txtcaptcha 0.1.0"}
    return preds, lat


def backend_easyocr(repo, items, mode, meta):
    import numpy as np
    import easyocr
    rd = easyocr.Reader(["en"], gpu=False, verbose=False)
    preds, lat = [], []
    for it in items:
        img = load_input(it, mode)


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
