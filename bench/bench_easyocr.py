"""EasyOCR only - readtext needs a path string, not a PIL image."""
import json, os, sys, time

from bench_hf import build_testset, norm, score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import results as result_path

RESULTS = result_path("bench_results_others.json")

items = build_testset()
print(f"test items: {len(items)}", flush=True)

import easyocr
rd = easyocr.Reader(["en"], gpu=False, verbose=False)

preds = []
t0 = time.time()
for it in items:
    res = rd.readtext(it["path"], detail=0, paragraph=True)
    preds.append(res[0] if res else "")
elapsed = time.time() - t0

rec = {"model": "EasyOCR/en", "preds": []}
ex, cer, n = 0, 0.0, 0
for it, pr in zip(items, preds):
    c = score(pr, it["answer"])
    rec["preds"].append({"type": it["type"], "file": os.path.basename(it["path"]),
                         "gold": it["answer"], "pred": str(pr).strip(),
                         "pred_norm": norm(pr), "cer": c})
    if c is not None:
        n += 1
        cer += c
        if norm(pr) == norm(it["answer"]):
            ex += 1
rec.update({"ok": True, "exact": ex, "n": n,
            "accuracy": round(ex / max(n, 1), 4),
            "mean_cer": round(cer / max(n, 1), 4),
            "seconds": round(elapsed, 1)})
print(f"OK EasyOCR acc={rec['accuracy']:.3f} cer={rec['mean_cer']:.3f} ({ex}/{n}) "
      f"{elapsed:.1f}s ({elapsed/len(items)*1000:.0f}ms/img)", flush=True)

results = {}
if os.path.isfile(RESULTS):
    with open(RESULTS, encoding="utf-8") as f:
        results = json.load(f)
results["EasyOCR/en"] = rec
with open(RESULTS, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
print("saved", flush=True)