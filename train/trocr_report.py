"""The report of a TrOCR run: the TrOCR numbers next to the PP-OCRv6 ones.

It merges the run's own `result.json` with the PP-OCRv6 run of the same held-out
types, so that the two models are compared on the same images.
"""

import json
import os
import time


# --------------------------------------------------------------------------- #
# the report (merges this run with the PP-OCRv6 run of the same held-out types)
# --------------------------------------------------------------------------- #
def read_ppocr_numbers(log_path, result_path):
    """The PP-OCRv6 numbers of `train/run_ppocr/big`, read from the files of that run."""
    out = {"source": None, "zero_step": None, "final": None}
    if os.path.isfile(result_path):
        with open(result_path, encoding="utf-8") as f:
            res = json.load(f)
        out["source"] = result_path
        out["model"] = res.get("model")
        out["runtime"] = res.get("runtime")
        out["train_items"] = res.get("split", {}).get("train_types")
        for key in ("zero_step", "final"):
            blk = res.get(key)
            if not blk:
                out[key] = None
                continue
            out[key] = {"held_out": blk.get("held_out"), "all": blk.get("all"),
                        "per_type": blk.get("per_type"),
                        "epoch": blk.get("epoch"), "step": blk.get("step"),
                        "seconds": blk.get("seconds")}
        out["history"] = res.get("history")
        return out
    if os.path.isfile(log_path):
        out["source"] = log_path
        zeros, finals = [], []
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("zero step:"):
                    zeros.append(line.strip())
                if line.startswith("epoch ") and "held-out median exact=" in line:
                    finals.append(line.strip())
        out["zero_step_log_lines"] = zeros
        out["final_log_lines"] = finals
    return out


def build_report(result_path, ppocr_log, ppocr_result, out_path, extra_eval=None):
    """Write `reports/TRAINING_TROCR_BIG.json`: TrOCR zero-step / fine-tuned next to PP-OCRv6."""
    with open(result_path, encoding="utf-8") as f:
        res = json.load(f)
    pp = read_ppocr_numbers(ppocr_log, ppocr_result)
    val_set = set(res["split"]["held_out_types"])
    # The evaluation of the first epoch (the best TrOCR checkpoint), produced by
    # `--eval-checkpoint`; the `result.json` of the run that followed it holds the
    # *second* epoch, which is worse.
    ep0 = None
    if extra_eval and os.path.isfile(extra_eval):
        with open(extra_eval, encoding="utf-8") as f:
            ep0 = json.load(f)

    def pct(x):
        return None if x is None else round(100.0 * x, 2)

    def table(per_type):
        rows = []
        for t in sorted(per_type):
            v = per_type[t]
            rows.append({"type": t, "n": v["n"],
                         "exact_match_pct": pct(v["exact_match"]),
                         "cer_pct": pct(v["cer"])})
        return rows

    def agg_block(agg):
        if not agg:
            return None
        return {"types": agg["types"], "items": agg["items"],
                "exact_match_median_pct": pct(agg["exact_match_median"]),
                "cer_median_pct": pct(agg["cer_median"]),
                "exact_match_micro_pct": pct(agg["exact_match_micro"]),
                "cer_micro_pct": pct(agg["cer_micro"])}

    trocr_zero = res["zero_step"]
    trocr_final = res["final"]
    # The best TrOCR checkpoint: the first epoch if it was evaluated separately,
    # otherwise the last run's final block.
    best_block = ep0 if ep0 else trocr_final
    best_per_type = (ep0 or {}).get("per_type") or trocr_final.get("per_type") or {}
    best_agg = (ep0 or {}).get("held_out") or trocr_final.get("held_out")
    pp_zero = (pp.get("zero_step") or {}).get("per_type") or {}
    pp_final = (pp.get("final") or {}).get("per_type") or {}

    side = []
    for t in res["split"]["held_out_types"]:
        tz = trocr_zero["per_type"].get(t, {})
        tf = best_per_type.get(t, {})
        pz = pp_zero.get(t, {})
        pf = pp_final.get(t, {})
        side.append({
            "type": t,
            "trocr_zero_step": {"exact_match_pct": pct(tz.get("exact_match")),
                                "cer_pct": pct(tz.get("cer"))},
            "trocr_finetuned": {"exact_match_pct": pct(tf.get("exact_match")),
                                "cer_pct": pct(tf.get("cer"))},
            "ppocr_v6_zero_step": {"exact_match_pct": pct(pz.get("exact_match")),
                                    "cer_pct": pct(pz.get("cer"))},
            "ppocr_v6_finetuned": {"exact_match_pct": pct(pf.get("exact_match")),
                                   "cer_pct": pct(pf.get("cer"))},
        })

    def agg_of(blk, key):
        if not blk:
            return None
        a = blk.get(key) or {}
        return {"types": a.get("types"), "items": a.get("items"),
                "exact_match_median_pct": pct(a.get("exact_match_median")),
                "cer_median_pct": pct(a.get("cer_median")),
                "exact_match_micro_pct": pct(a.get("exact_match_micro")),
                "cer_micro_pct": pct(a.get("cer_micro"))}

    report = {
        "title": "TrOCR-small-printed vs PP-OCRv6-medium-rec on the same 7 held-out captcha types",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "held_out_types": res["split"]["held_out_types"],
        "train_types": res["split"]["train_types"],
        "dropped_types": res["split"]["dropped"],
        "train_items": res["split"]["train_items"],
        "held_out_items": res["split"]["held_out_items"],
        "model": res["model"],
        "charset": res["charset"],
        "trocr_zero_step": {
            "held_out": agg_block(trocr_zero["held_out"]),
            "per_type": table(trocr_zero["per_type"]),
            "seconds": trocr_zero["seconds"],
        },
        "trocr_finetuned": {
            "held_out": agg_block(best_agg),
            "per_type": table(best_per_type),
            "epoch": (ep0 or {}).get("epoch", trocr_final.get("epoch")),
            "step": (ep0 or {}).get("step", trocr_final.get("step")),
            "checkpoint": (ep0 or {}).get("checkpoint") or "train/run/trocr_big/best.pt",
            "note": ("the BEST TrOCR checkpoint (epoch 0). The second epoch is worse - "
                     "see trocr_finetuned_epoch1."),
        },
        "trocr_finetuned_epoch1": {
            "held_out": agg_block(trocr_final["held_out"]),
            "per_type": table(trocr_final.get("per_type") or {}),
            "epoch": trocr_final.get("epoch"),
            "step": trocr_final.get("step"),
            "note": "the continuation run (--resume --epochs 2): one more epoch, worse",
        },
        "ppocr_v6": {
            "source": pp.get("source"),
            "runtime": pp.get("runtime"),
            "zero_step": {"held_out": agg_of(pp.get("zero_step"), "held_out"),
                          "per_type": table(pp_zero),
                          "seconds": (pp.get("zero_step") or {}).get("seconds")},
            "finetuned": {"held_out": agg_of(pp.get("final"), "held_out"),
                          "per_type": table(pp_final),
                          "epoch": (pp.get("final") or {}).get("epoch"),
                          "step": (pp.get("final") or {}).get("step")},
            "history": pp.get("history"),
        },
        "side_by_side_per_type": side,
        "runtime": res["runtime"],
        "history": res["history"],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    return report
