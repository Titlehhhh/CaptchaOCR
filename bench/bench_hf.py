"""Benchmark harness: run HF captcha-OCR models on the generated text captchas."""
import json, os, sys, time, re, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import OUT, results

RESULTS = results("bench_results.json")

TEXT_TYPES = [
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

N_PER_TYPE = 8


def build_testset():
    items = []
    for t in TEXT_TYPES:
        d = os.path.join(OUT, t)
        lj = os.path.join(d, "labels.jsonl")
        if not os.path.isfile(lj):
            print(f"[skip] no labels for {t}")
            continue
        with open(lj, encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
        for r in rows[:N_PER_TYPE]:
            items.append({
                "type": t,
                "path": os.path.join(d, r["file"]),
                "answer": r.get("answer", ""),
                "text": r.get("text") or r.get("answer", ""),
                "roi": r.get("roi"),
            })
    return items


def norm(s):
    if s is None:
        return ""
    s = str(s).strip()
    s = re.sub(r"[^A-Za-z0-9+\-*]", "", s)
    return s


def lev(a, b):
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


def score(pred, gold):
    p, g = norm(pred), norm(gold)
    if not g:
        return None
    return lev(p, g) / len(g)


def load_image(path, size=None, roi=None):
    """Load an image, optionally cropped to its text band.

    29 of the 46 types are *scenes* - a chat log, an inventory window, an anvil
    dialog - where the answer is one line among several. Handing such an image whole
    to a recogniser is an ill-posed question, so the band recorded in `labels.jsonl`
    is cropped off first. The models are then measured on the same input our own
    recogniser sees, which is the only fair comparison.
    """
    from PIL import Image
    img = Image.open(path).convert("RGB")
    if roi:
        x, y, w, h = roi
        x = max(0, min(x, img.width - 1))
        y = max(0, min(y, img.height - 1))
        w = max(1, min(w, img.width - x))
        h = max(1, min(h, img.height - y))
        img = img.crop((x, y, x + w, y + h))
    if size:
        img = img.resize(size, Image.BICUBIC)
    return img


def load_band(item, size=None):
    """`load_image` for a test-set item, using the band it carries."""
    return load_image(item["path"], size=size, roi=item.get("roi"))


def predict_trocr(model_id, paths):
    """Load an image-to-text model via transformers, predict on given paths."""
    import torch
    from transformers import AutoProcessor

    proc = None
    model = None
    last_err = None
    # transformers>=5: AutoModelForImageTextToText; older: TrOCRForCausalLM
    for loader_name in ("AutoModelForImageTextToText", "TrOCRForConditionalGeneration",
                        "TrOCRForCausalLM", "AutoModelForVision2Seq"):
        try:
            mod = __import__("transformers", fromlist=[loader_name])
            Loader = getattr(mod, loader_name)
            proc = AutoProcessor.from_pretrained(model_id)
            model = Loader.from_pretrained(model_id)
            model.eval()
            last_err = None
            break
        except Exception as e:  # try next loader
            last_err = f"{loader_name}: {type(e).__name__}: {e}"
            model = None
    if model is None:
        raise RuntimeError(f"cannot load. last={last_err}")

    outs = []
    with torch.no_grad():
        for p in paths:
            img = load_image(p)
            inputs = proc(img, return_tensors="pt")
            gen = model.generate(**inputs, max_new_tokens=32)
            txt = proc.batch_decode(gen, skip_special_tokens=True)[0]
            outs.append(txt)
    return outs, getattr(model, "config", None)


MODELS = sys.argv[1:] if len(sys.argv) > 1 else [
    "anuashok/ocr-captcha-v3",
    "anuashok/ocr-captcha-v2",
    "DunnBC22/trocr-base-printed_captcha_ocr",
    "tomofi/trocr-captcha",
    "chanelcolgate/trocr-base-printed_captcha_ocr",
    "hongyusir/trocr-base-printed_captcha_ocr",
    "youminmin/my-captcha-ocr-model",
    "luckystars0612/trocr-finetuned-captcha",
    "arkhabbazan/ocr-math-captcha",
    "microsoft/trocr-base-printed",
]


def main():
    items = build_testset()
    print(f"test items: {len(items)} over {len(TEXT_TYPES)} types", flush=True)
    results = {}
    if os.path.isfile(RESULTS):
        with open(RESULTS, encoding="utf-8") as f:
            results = json.load(f)

    for mid in MODELS:
        if mid in results:
            print(f"[skip] {mid} already done", flush=True)
            continue
        print(f"\n===== {mid} =====", flush=True)
        t0 = time.time()
        rec = {"model": mid, "ok": False, "preds": [], "exact": 0, "n": 0, "cer_sum": 0.0}
        try:
            preds, cfg = predict_trocr(mid, [it["path"] for it in items])
            load_s = time.time() - t0
            for it, pr in zip(items, preds):
                c = score(pr, it["answer"])
                rec["preds"].append({
                    "type": it["type"], "file": os.path.basename(it["path"]),
                    "gold": it["answer"], "pred": pr.strip(), "pred_norm": norm(pr), "cer": c,
                })
                if c is not None:
                    rec["n"] += 1
                    rec["cer_sum"] += c
                    if norm(pr) == norm(it["answer"]):
                        rec["exact"] += 1
            rec["ok"] = True
            rec["mean_cer"] = round(rec["cer_sum"] / max(rec["n"], 1), 4)
            rec["accuracy"] = round(rec["exact"] / max(rec["n"], 1), 4)
            rec["seconds"] = round(time.time() - t0, 1)
            rec["load_seconds"] = round(load_s, 1)
            print(f"OK acc={rec['accuracy']:.3f} CER={rec['mean_cer']:.3f} "
                  f"({rec['exact']}/{rec['n']}) in {rec['seconds']}s", flush=True)
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["trace"] = traceback.format_exc()[-1200:]
            print(f"FAIL {rec['error']}", flush=True)
        results[mid] = rec
        with open(RESULTS, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1)

    print("\nDONE", flush=True)
    for mid, r in results.items():
        if r.get("ok"):
            print(f"  {mid}: acc={r['accuracy']:.3f} cer={r['mean_cer']:.3f} t={r.get('seconds')}s")
        else:
            print(f"  {mid}: FAIL {r.get('error','')[:120]}")


if __name__ == "__main__":
    main()