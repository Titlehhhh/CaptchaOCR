import json, os, sys, time, traceback

from bench_hf import build_testset, norm, score, load_image, load_band

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import results as result_path

RESULTS = result_path("bench_results_others.json")


def save(results):
    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)


def record(results, mid, preds, items, elapsed, err=None):
    rec = {"model": mid, "preds": [], "seconds": round(elapsed, 1)}
    if err:
        rec["ok"] = False
        rec["error"] = err
        print(f"FAIL {mid}: {err}", flush=True)
        results[mid] = rec
        save(results)
        return
    ex = 0
    cer = 0.0
    n = 0
    for it, pr in zip(items, preds):
        c = score(pr, it["answer"])
        rec["preds"].append({
            "type": it["type"], "file": os.path.basename(it["path"]),
            "gold": it["answer"], "pred": str(pr).strip(), "pred_norm": norm(pr), "cer": c,
        })
        if c is not None:
            n += 1
            cer += c
            if norm(pr) == norm(it["answer"]):
                ex += 1
    rec.update({"ok": True, "exact": ex, "n": n,
                "accuracy": round(ex / max(n, 1), 4),
                "mean_cer": round(cer / max(n, 1), 4)})
    print(f"OK {mid} acc={rec['accuracy']:.3f} cer={rec['mean_cer']:.3f} ({ex}/{n}) {elapsed:.1f}s",
          flush=True)
    results[mid] = rec
    save(results)


def run_easyocr(items):
    import easyocr
    rd = easyocr.Reader(["en"], gpu=False, verbose=False)
    return [rd.readtext(load_band(it), detail=0, paragraph=True)[0] if
            rd.readtext(load_band(it), detail=0, paragraph=True) else ""
            for it in items]


def run_custom_transformers(model_id, items, extra=None):
    import torch
    from transformers import AutoProcessor
    proc = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)





    model = None
    last_err = None
    for loader_name in ("AutoModel", "AutoModelForImageTextToText"):
        try:
            import transformers
            loader = getattr(transformers, loader_name)
            model = loader.from_pretrained(model_id, trust_remote_code=True)
            model.eval()
            last_err = None
            break
        except Exception as e:
            last_err = f"{loader_name}: {type(e).__name__}: {e}"
            model = None
    if model is None:
        raise RuntimeError(f"cannot load {model_id}; last error: {last_err}")
    outs = []




    is_ctc = not hasattr(model, "generate")
    outs = []
    with torch.no_grad():
        for it in items:
            img = load_band(it)
            if is_ctc:
                try:
                    inputs = proc(img, return_tensors="pt")
                except TypeError:
                    inputs = proc(img)
                pixel_values = inputs["pixel_values"]
                if not torch.is_tensor(pixel_values):
                    pixel_values = torch.as_tensor(pixel_values)
                outputs = model(pixel_values)
                logits = getattr(outputs, "logits", outputs)
                if hasattr(proc, "batch_decode"):
                    outs.append(proc.batch_decode(logits)[0])
                else:
                    outs.append(str(logits))
                continue
            inputs = proc(img, return_tensors="pt")
            gen = model.generate(**inputs, max_new_tokens=32)
            outs.append(proc.batch_decode(gen, skip_special_tokens=True)[0])
    return outs


def run_florence(model_id, items):
    import torch
    from transformers import AutoProcessor, AutoModelForCausalLM
    proc = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True).eval()
    task_prompt = "<OCR>"
    outs = []
    with torch.no_grad():
        for it in items:
            inputs = proc(text=task_prompt, images=load_band(it), return_tensors="pt")
            gen = model.generate(**inputs, max_new_tokens=32, num_beams=3)
            txt = proc.batch_decode(gen, skip_special_tokens=False)[0]
            parsed = proc.post_process_generation(
                txt, task=task_prompt, image_size=load_band(it).size)
            val = ""
            if isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, str):
                        val = v
            outs.append(val or txt)
    return outs


TASKS = {
    "EasyOCR/en": run_easyocr,
    "Graf-J/captcha-crnn-finetuned": lambda items: run_custom_transformers("Graf-J/captcha-crnn-finetuned", items),
    "Graf-J/captcha-conv-transformer-finetuned": lambda items: run_custom_transformers("Graf-J/captcha-conv-transformer-finetuned", items),
    "04RR/Florence-base-Captcha": lambda items: run_florence("04RR/Florence-base-Captcha", items),
}


def main():
    items = build_testset()
    print(f"test items: {len(items)}", flush=True)
    results = {}
    if os.path.isfile(RESULTS):
        with open(RESULTS, encoding="utf-8") as f:
            results = json.load(f)

    for name, fn in TASKS.items():
        if name in results:
            print(f"[skip] {name}", flush=True)
            continue
        print(f"\n===== {name} =====", flush=True)
        t0 = time.time()
        try:
            preds = fn(items)
            record(results, name, preds, items, time.time() - t0)
        except Exception as e:
            record(results, name, [], items, time.time() - t0,
                   err=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}")


if __name__ == "__main__":
    main()