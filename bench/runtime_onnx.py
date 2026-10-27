""

import argparse
import json
import math
import os
import sys
import time

import numpy as np
import onnxruntime as ort
from PIL import Image


def load_band(path, roi):
    img = Image.open(path)
    if img.mode != "L":
        img = img.convert("L")
    if roi:
        x, y, w, h = roi
        x = max(0, min(x, img.width - 1))
        y = max(0, min(y, img.height - 1))
        w = max(1, min(w, img.width - x))
        h = max(1, min(h, img.height - y))
        img = img.crop((x, y, x + w, y + h))
    return img


def line_height(img):
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 2 or a.shape[0] < 3:
        return img.height
    busy = a.std(axis=1) > 6.0
    runs, start = [], None
    for i, b in enumerate(busy):
        if b and start is None:
            start = i
        elif not b and start is not None:
            runs.append(i - start)
            start = None
    if start is not None:
        runs.append(len(busy) - start)
    runs = [r for r in runs if r >= 2]
    if not runs:
        return img.height
    return max(1, int(np.median(runs)))


def preprocess(img, cfg):
    h = cfg["input"]["glyph_height"]
    line = line_height(img)
    scale = h / max(1, line)
    w = int(round(img.width * scale))
    w = max(cfg["input"]["min_width"], w)
    w = min(cfg["input"]["max_width"], w)
    img = img.resize((w, h), Image.BILINEAR)
    a = np.asarray(img, dtype=np.float32) / 255.0
    a = (a - cfg["preprocess"]["mean"]) / cfg["preprocess"]["std"]
    return np.ascontiguousarray(a.reshape(1, 1, h, w)), w


def decode(logits, charset):
    x = logits - logits.max(axis=-1, keepdims=True)
    e = np.exp(x)
    probs = e / e.sum(axis=-1, keepdims=True)
    best = probs.argmax(axis=-1)[0]
    best_p = probs.max(axis=-1)[0]
    chars, confs, prev = [], [], -1
    for t in range(best.shape[0]):
        k = int(best[t])
        if k != prev and k != 0:
            chars.append(k)
            confs.append(float(best_p[t]))
        prev = k
    text = "".join(charset[k - 1] for k in chars if 1 <= k <= len(charset))
    conf = float(math.exp(sum(math.log(max(c, 1e-6)) for c in confs) / len(confs))) if confs else 0.0
    return text, conf


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--roi", nargs=4, type=int, default=None,
                    help="x y w h; without it the whole frame is the band")
    ap.add_argument("--threads", type=int, default=0)
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    charset = cfg["charset"]

    so = ort.SessionOptions()
    if args.threads:
        so.intra_op_num_threads = args.threads
    sess = ort.InferenceSession(args.model, so, providers=["CPUExecutionProvider"])

    t0 = time.time()
    img = load_band(args.image, args.roi)
    tensor, w = preprocess(img, cfg)
    logits = sess.run(None, {sess.get_inputs()[0].name: tensor})[0]
    text, conf = decode(logits, charset)
    dt = (time.time() - t0) * 1000.0

    out = {"file": args.image.replace("\\", "/"), "text": text,
           "confidence": round(conf, 6), "width": w,
           "time_ms": round(dt, 2)}
    if "--dump-tensor" in sys.argv:
        path = sys.argv[sys.argv.index("--dump-tensor") + 1]
        tensor.astype(np.float32).tofile(path)
        out["tensor_file"] = path
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
