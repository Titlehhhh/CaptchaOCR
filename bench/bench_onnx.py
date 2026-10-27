import json, os, sys, time, traceback

import numpy as np
from PIL import Image

from bench_hf import build_testset, norm, score, load_band

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import results as result_path

RESULTS = result_path("bench_results_onnx.json")

CAPTCHAD_CHARSET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
IDX2CHAR = {i + 1: ch for i, ch in enumerate(CAPTCHAD_CHARSET)}
BLANK_IDX = 0


def ctc_decode(tokens):
    res, prev = [], None
    for t in tokens:
        if t != prev and t != BLANK_IDX and t in IDX2CHAR:
            res.append(IDX2CHAR[t])
        prev = t
    return "".join(res)


def captchad_preprocess(path, roi=None):
    with Image.open(path) as im:
        if im.mode == "RGBA":
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[3])
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")
        im = im.resize((192, 64), Image.BILINEAR)
        arr = np.array(im, dtype=np.float32).transpose(2, 0, 1)
    arr = (arr - 127.5) / 127.5
    return arr[np.newaxis, :, :, :]


def run_captchad(model_id, items, quant):
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    fname = {"fp32": "captchad.onnx", "int8": "captchad_int8.onnx"}[quant]
    w = hf_hub_download(model_id, fname)
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = min(4, os.cpu_count() or 4)
    sess = ort.InferenceSession(w, sess_options=opts)
    name = sess.get_inputs()[0].name
    lat = []
    outs = []
    for it in items:
        t0 = time.perf_counter()
        logits = sess.run(None, {name: captchad_preprocess(it["path"])})[0]
        preds = np.argmax(logits[:, 0, :], axis=-1).tolist()
        outs.append(ctc_decode(preds))
        lat.append((time.perf_counter() - t0) * 1000)
    print(f"   latency mean={np.mean(lat):.1f}ms min={np.min(lat):.1f}ms", flush=True)
    return outs


def phpwind_preprocess(path):
    import cv2
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    k = np.ones((2, 2), np.uint8)
    den = cv2.morphologyEx(img, cv2.MORPH_OPEN, k)
    im = Image.fromarray(den).convert("RGB").resize((160, 64), Image.BILINEAR)
    a = np.asarray(im, dtype=np.float32) / 255.0
    return a.transpose(2, 0, 1)[None]


def run_phpwind(model_id, items):
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    w = hf_hub_download(model_id, "model.onnx")
    sess = ort.InferenceSession(w, providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    outs = []
    for it in items:
        out = sess.run(None, {name: phpwind_preprocess(it["path"])})[0]
        outs.append("".join(str(int(out[0, p].argmax())) for p in range(out.shape[1])))
    return outs


TASKS = [
    ("AndresDev/captCHAD [onnx fp32]", "AndresDev/captCHAD", "fp32"),
    ("AndresDev/captCHAD [onnx int8]", "AndresDev/captCHAD", "int8"),
    ("FlanChanXwO/phpwind-captcha-ocr [onnx]", "FlanChanXwO/phpwind-captcha-ocr", None),
]


def main():
    items = build_testset()
    print(f"test items: {len(items)}", flush=True)
    results = {}
    if os.path.isfile(RESULTS):
        with open(RESULTS, encoding="utf-8") as f:
            results = json.load(f)

    for name, mid, quant in TASKS:
        if name in results:
            print(f"[skip] {name}", flush=True)
            continue
        print(f"\n===== {name} =====", flush=True)
        t0 = time.time()
        rec = {"model": name, "preds": []}
        try:
            if quant is None:
                preds = run_phpwind(mid, items)
            else:
                preds = run_captchad(mid, items, quant)
            ex, cer, n = 0, 0.0, 0
            for it, pr in zip(items, preds):
                c = score(pr, it["answer"])
                rec["preds"].append({
                    "type": it["type"], "file": os.path.basename(it["path"]),
                    "gold": it["answer"], "pred": pr.strip(), "pred_norm": norm(pr), "cer": c})
                if c is not None:
                    n += 1
                    cer += c
                    if norm(pr) == norm(it["answer"]):
                        ex += 1
            rec.update({"ok": True, "exact": ex, "n": n,
                        "accuracy": round(ex / max(n, 1), 4),
                        "mean_cer": round(cer / max(n, 1), 4),
                        "seconds": round(time.time() - t0, 1)})
            print(f"OK acc={rec['accuracy']:.3f} cer={rec['mean_cer']:.3f} ({ex}/{n})", flush=True)
        except Exception as e:
            rec.update({"ok": False, "error": f"{type(e).__name__}: {e}",
                        "trace": traceback.format_exc()[-800:]})
            print(f"FAIL {rec['error']}", flush=True)
        results[name] = rec
        with open(RESULTS, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
    print("\nDONE", flush=True)


if __name__ == "__main__":
    main()