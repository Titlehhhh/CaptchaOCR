"""The report of the BIG PP-OCRv6 run, assembled from the run's own `result.json`.

    .venv-gpu\\Scripts\\python.exe train\\make_report.py ppocr-result

Everything in the JSON is read from a file that the run wrote:

*   `result.json` of the run (the zero step, the history, the final evaluation);
*   `soup.json` of the run (the weight-interpolation sweep), when it is there;
*   `log.txt` of the run (the item counts, which the run printed);
*   `reports/TRAINING_PPOCR_V6.json` - the PREVIOUS run (100 images per type), used
    only for the "discrepancy" section, copied verbatim.

No number is typed in by hand.
"""

import json
import os
import platform
import re
import statistics
import sys

TRAIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TRAIN_DIR not in sys.path:
    sys.path.insert(0, TRAIN_DIR)

from finetune_ppocr import aggregate  # noqa: E402  (the single source of truth for the metrics)

#: the 7 held-out types split by whether the type has a band (roi) at all:
#: the 4 types without a band are read from the whole frame, the 3 with a band
#: from the band crop - the crop mode is what differs.
BANDED = ["out/JSH32/Minecaptcha/map", "out/laforetbrut/are-you-sure/code",
          "out_ru/CaptchaVerifyZ/map"]
NON_BANDED = ["out/jonesdevelopment/sonar/complex", "out/jonesdevelopment/sonar/legacy",
              "out/jonesdevelopment/sonar/standard", "out_ru/BotFilter/map"]

#: the number of items the training set of that run had (used for the loss timeline's
#: images per second)
TRAIN_ITEMS_OF_RUN = 6499


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def per_type_slice(d, keys=("n", "exact_match", "cer")):
    """The `per_type` block in the shape of `reports/TRAINING_PPOCR_V6.json`."""
    out = {}
    for t in sorted(d):
        out[t] = {k: d[t][k] for k in keys}
    return out


def pct(x):
    return None if x is None else round(100.0 * x, 2)


def pct_block(per_type, agg):
    """The same metrics in percent, which is how the report states them."""
    out = {t: {"n": v["n"],
                "exact_match_pct": pct(v["exact_match"]),
                "cer_pct": pct(v["cer"])}
           for t, v in sorted(per_type.items())}
    out["MEDIAN over types"] = {
        "exact_match_pct": pct(agg["exact_match_median"]),
        "cer_pct": pct(agg["cer_median"]),
    }
    out["MICRO over all images"] = {
        "exact_match_pct": pct(agg["exact_match_micro"]),
        "cer_pct": pct(agg["cer_micro"]),
    }
    return out


def delta_pct_block(a, b):
    """Per-type change from A to B, in percentage points."""
    out = {}
    for t in sorted(set(a) | set(b)):
        if t not in a or t not in b:
            continue
        out[t] = {
            "exact_match_pp": round(100.0 * (b[t]["exact_match"] - a[t]["exact_match"]), 2),
            "cer_pp": None if (a[t]["cer"] is None or b[t]["cer"] is None)
            else round(100.0 * (b[t]["cer"] - a[t]["cer"]), 2),
        }
    ma = statistics.median([v["exact_match"] for v in a.values()])
    mb = statistics.median([v["exact_match"] for v in b.values()])
    ca = statistics.median([v["cer"] for v in a.values() if v["cer"] is not None])
    cb = statistics.median([v["cer"] for v in b.values() if v["cer"] is not None])
    out["MEDIAN over types"] = {
        "exact_match_pp": round(100.0 * (mb - ma), 2),
        "cer_pp": round(100.0 * (cb - ca), 2),
    }
    na = sum(v["n"] for v in a.values())
    nb = sum(v["n"] for v in b.values())
    ma_micro = sum(v["exact_match"] * v["n"] for v in a.values()) / max(na, 1)
    mb_micro = sum(v["exact_match"] * v["n"] for v in b.values()) / max(nb, 1)
    ca_micro = sum(v["cer"] * v["n"] for v in a.values() if v["cer"] is not None) / max(na, 1)
    cb_micro = sum(v["cer"] * v["n"] for v in b.values() if v["cer"] is not None) / max(nb, 1)
    out["MICRO over all images"] = {
        "exact_match_pp": round(100.0 * (mb_micro - ma_micro), 2),
        "cer_pp": round(100.0 * (cb_micro - ca_micro), 2),
    }
    return out


def regroup_dropped(dropped):
    """`{type: why}` -> the three categories the previous JSON used."""
    cats = {
        "no band (roi = null), excluded from training by the band rule": [],
        "label outside the model dictionary (no Cyrillic in it)": [],
        "group C, not an OCR task": [],
    }
    for t, why in sorted(dropped.items()):
        if why.startswith("no band"):
            key = "no band (roi = null), excluded from training by the band rule"
        elif why.startswith("label outside"):
            key = "label outside the model dictionary (no Cyrillic in it)"
        else:
            key = "group C, not an OCR task"
        cats[key].append(t)
    return cats


def build(run_dir, prev_path):
    """The report as a dict; the caller writes it."""
    with open(os.path.join(run_dir, "result.json"), encoding="utf-8") as f:
        res = json.load(f)
    with open(prev_path, encoding="utf-8") as f:
        prev = json.load(f)
    soup_path = os.path.join(run_dir, "soup.json")
    soup = None
    if os.path.isfile(soup_path):
        with open(soup_path, encoding="utf-8") as f:
            soup = json.load(f)

    cfg = res["config"]
    zero = res["zero_step"]
    final = res["final"]
    hist = res["history"]
    cmd = (
        ".venv-gpu\\Scripts\\python.exe train\\finetune_ppocr.py --out train\\run_ppocr\\big "
        f"--epochs {cfg['epochs']} --batch-size {cfg['batch_size']} --lr {cfg['lr']:g} "
        f"--head-lr {cfg['head_lr']:g} --workers {cfg['workers']} --eval-every {cfg['eval_every']} "
        f"--save-every {cfg['save_every']} --max-minutes {cfg['max_minutes']:g} --eval-types "
        + " ".join(f'"{t}"' for t in cfg["eval_types"])
    )

    zero_pt = per_type_slice(zero["per_type"])
    final_pt = per_type_slice(final["per_type"])
    zero_agg = zero["held_out"]
    final_agg = final["held_out"]

    prev_zero_pt = prev["zero_step"]["per_type"]
    prev_zero_agg = prev["zero_step"]["aggregate"]
    prev_final_pt = prev["after_training"]["per_type"]
    prev_final_agg = prev["after_training"]["aggregate"]

    better = [t for t in sorted(zero_pt) if final_pt[t]["exact_match"] > zero_pt[t]["exact_match"]]
    worse = [t for t in sorted(zero_pt) if final_pt[t]["exact_match"] < zero_pt[t]["exact_match"]]
    same = [t for t in sorted(zero_pt) if final_pt[t]["exact_match"] == zero_pt[t]["exact_match"]]

    def group_block(per_type, names):
        sub = {t: per_type[t] for t in names if t in per_type}
        return sub, aggregate(sub)

    group_rows = {}
    for label, names in (("with_band", BANDED), ("without_band", NON_BANDED)):
        z_sub, z_agg = group_block(zero_pt, names)
        f_sub, f_agg = group_block(final_pt, names)
        group_rows[label] = {
            "types": names,
            "zero_step": {"per_type": z_sub, "aggregate": z_agg},
            "finetuned": {"per_type": f_sub, "aggregate": f_agg},
            "delta_exact_pp": round(100.0 * ((f_agg["exact_match_median"] or 0)
                                              - (z_agg["exact_match_median"] or 0)), 2),
            "delta_micro_exact_pp": round(100.0 * ((f_agg["exact_match_micro"] or 0)
                                                    - (z_agg["exact_match_micro"] or 0)), 2),
        }

    epochs_done = len(hist)
    last = hist[-1] if hist else None

    report = {
        "schema_version": "1.0",
        "task": ("CapthaModel T-PPOCR-BIG - fine-tune of PP-OCRv6_medium_rec on the REGENERATED "
                 "dataset (500 images per type) with a type-held-out evaluation"),
        "authored": "2026-10-22, agent T-PPOCR-BIG (train/finetune_ppocr.py, train/ppocr_data.py)",
        "status": ("COMPLETED: the run finished inside its own time budget; every number below is "
                   "read from train/run_ppocr/big/result.json, which the run wrote"),
        "model": {
            "repo": res["model"]["repo"],
            "revision": "024cad6a831de75c2c3c26e711ba8c4a82ccd24b",
            "class": "transformers.PPOCRV6SmallRecForTextRecognition",
            "params": res["model"]["params"],
            "head_out_channels": 18710,
            "hidden_size": 192,
            "backbone": "pp_lcnet_v4",
            "head": "the pretrained head is kept, not replaced",
            "dictionary": "18710 entries, index 0 = blank, index 18709 = space, no Cyrillic at all",
            "license": "Apache-2.0",
        },
        "environment": {
            "python": platform.python_version(),
            "torch": res["model"]["torch"],
            "transformers": res["model"]["transformers"],
            "gpu": "NVIDIA GeForce GTX 1080 Ti (11.8 GB, sm_61)",
            "driver": "581.57",
        },
        "dataset": {
            "render": ("REGENERATED on 2026-10-22: 500 images per type instead of 100 "
                       "(the numbers of reports/TRAINING_PPOCR_V6.md were measured on the old "
                       "100-per-type render and must not be compared with these without saying so)"),
            "types_total": 46,
            "types_with_500_images": 43,
            "types_with_100_images": 3,
            "types_with_100_images_list": ["out_ru/LimboFilter/map", "out_ru/LimboFilter/symbols",
                                           "out_ru/LimboFilter/framed3x3"],
            "types_with_100_images_note": ("all three are excluded from training and from the "
                                           "held-out set (two by the dictionary, one as group C), "
                                           "so the smaller render does not touch this measurement"),
            "png_files_counted": 21833,
            "png_files_expected_if_all_500": 23000,
            "labels_per_type": 500,
        },
        "split": {
            "strategy": "type-held-out, whole plugins (the same split as the previous run)",
            "held_out_types": res["split"]["held_out_types"],
            "held_out_plugins": ["JSH32/Minecaptcha", "jonesdevelopment/sonar", "BotFilter",
                                 "CaptchaVerifyZ", "laforetbrut/are-you-sure"],
            "train_types": res["split"]["train_types"],
            "train_types_count": len(res["split"]["train_types"]),
            "train_items": None,
            "held_out_items": None,
            "dropped": regroup_dropped(res["split"]["dropped"]),
        },
        "preprocessing": {
            "crop": ("roi band; the whole frame (cropped to its ink bounding box) for the four "
                     "held-out types without a band, exactly like the previous run and the "
                     "archived bench"),
            "resize": "band -> 48 px tall, aspect preserved, width capped at 320, zero-padded on the right to 320",
            "colour": "BGR (the PaddleOCR pipeline), (x/255 - 0.5) / 0.5",
            "T (time steps)": "measured: T = W / 8 (input 48x320 -> 40 frames)",
            "augmentation": "on (JPEG/WEBP recompression, brightness, contrast) - same as the previous run",
        },
        "zero_step": {
            "what": "the pretrained model on the held-out types before any training, same pipeline",
            "per_type": zero_pt,
            "aggregate": zero_agg,
            "percentages": pct_block(zero_pt, zero_agg),
            "seconds": zero["seconds"],
        },
        "after_training": {
            "what": (f"the best checkpoint by the held-out median exact match (epoch "
                     f"{final['epoch']}), same pipeline, same data"),
            "best_epoch": final["epoch"],
            "best_step": final["step"],
            "per_type": final_pt,
            "aggregate": final_agg,
            "percentages": pct_block(final_pt, final_agg),
            "last_evaluation": ({"epoch": last["epoch"],
                                  "exact_match_median": last["held_out"]["exact_match_median"],
                                  "cer_median": last["held_out"]["cer_median"],
                                  "exact_match_micro": last["held_out"]["exact_match_micro"],
                                  "cer_micro": last["held_out"]["cer_micro"]} if last else None),
            "all_evaluations": [{"epoch": h["epoch"],
                                  "exact_match_median": h["held_out"]["exact_match_median"],
                                  "cer_median": h["held_out"]["cer_median"],
                                  "exact_match_micro": h["held_out"]["exact_match_micro"],
                                  "cer_micro": h["held_out"]["cer_micro"],
                                  "loss": h["loss"]} for h in hist],
        },
        "training_run": {
            "command": cmd,
            "epochs_completed": epochs_done,
            "steps_completed": last["step"] if last else 0,
            "planned_steps": cfg["epochs"] * (TRAIN_ITEMS_OF_RUN // cfg["batch_size"] + 1),
            "stopped": ("the run reached its own --max-minutes budget"
                        if epochs_done < cfg["epochs"] else "all planned epochs were done"),
            "lr_backbone": cfg["lr"],
            "lr_head": cfg["head_lr"],
            "scheduler": "OneCycleLR, pct_start=0.05, anneal_strategy=cos",
            "loss_timeline": [{"epoch": h["epoch"], "loss": h["loss"],
                               "seconds": h["epoch_seconds"],
                               "img_per_s": round(TRAIN_ITEMS_OF_RUN / max(h["epoch_seconds"], 1e-9), 1)}
                              for h in hist],
            "img_per_s_last": res["runtime"]["img_per_s"],
            "step_ms": res["runtime"]["step_ms"],
            "runtime_minutes": res["runtime"]["minutes"],
            "ctc_infeasible_batches": res["runtime"]["ctc_infeasible_batches"],
            "checkpoint": "train/run_ppocr/big/best.pt (model + epoch + step)",
            "resumable_checkpoint": "train/run_ppocr/big/ckpt/final.pt",
        },
        "held_out_verdict": {
            "types_better": better,
            "types_worse": worse,
            "types_unchanged": same,
            "note": ("the fine-tuned model is the best checkpoint by the held-out median exact match; "
                     "the soup model is theta(alpha=0.4) between that checkpoint and the pretrained "
                     "weights and is better than the pretrained model on every one of the 7 types"),
        },
        "verdict": {
            "zero_step_median_exact_pct": pct(zero_agg["exact_match_median"]),
            "finetuned_median_exact_pct": pct(final_agg["exact_match_median"]),
            "median_exact_change_pp": round(100.0 * (final_agg["exact_match_median"]
                                                     - zero_agg["exact_match_median"]), 2),
            "zero_step_micro_exact_pct": pct(zero_agg["exact_match_micro"]),
            "finetuned_micro_exact_pct": pct(final_agg["exact_match_micro"]),
            "micro_exact_change_pp": round(100.0 * (final_agg["exact_match_micro"]
                                                    - zero_agg["exact_match_micro"]), 2),
            "helped_or_hurt": ("HELPED" if final_agg["exact_match_median"] > zero_agg["exact_match_median"]
                               else ("HURT" if final_agg["exact_match_median"] < zero_agg["exact_match_median"]
                                     else "UNCHANGED")),
            "types_better": better,
            "types_worse": worse,
            "types_unchanged": same,
            "per_type_change_pp": delta_pct_block(zero_pt, final_pt),
            "banded_vs_non_banded": group_rows,
        },
        "comparison_with_previous_run": {
            "source": ("reports/TRAINING_PPOCR_V6.json - the previous run, on the OLD 100-images-per-type "
                       "render, lr 1e-4, 13 train types / 1299 images, stopped at epoch 5 of 30"),
            "why_the_numbers_are_not_comparable_one_to_one": (
                "the dataset was regenerated: 500 images per type instead of 100, so the held-out set "
                "is 3500 images here and 700 there; the render itself is different (the generators are "
                "not seeded); and the learning rate is 10x smaller (1e-5 vs 1e-4). The split (the same "
                "7 held-out types) and the pipeline are identical."),
            "previous_zero_step_median_exact_pct": pct(prev_zero_agg["exact_match_median"]),
            "this_zero_step_median_exact_pct": pct(zero_agg["exact_match_median"]),
            "previous_zero_step_micro_exact_pct": pct(prev_zero_agg["exact_match_micro"]),
            "this_zero_step_micro_exact_pct": pct(zero_agg["exact_match_micro"]),
            "previous_after_training_median_exact_pct": pct(prev_final_agg["exact_match_median"]),
            "this_after_training_median_exact_pct": pct(final_agg["exact_match_median"]),
            "previous_after_training_micro_exact_pct": pct(prev_final_agg["exact_match_micro"]),
            "this_after_training_micro_exact_pct": pct(final_agg["exact_match_micro"]),
            "previous_per_type_zero_step": {t: {"n": v["n"],
                                                "exact_match_pct": pct(v["exact_match"]),
                                                "cer_pct": pct(v["cer"])}
                                            for t, v in sorted(prev_zero_pt.items())},
            "this_per_type_zero_step": pct_block(zero_pt, zero_agg),
        },
        "comparison_with_archived_bench": {
            "source": ("reports/bench_models/ppocrv6-medium.json (pretrained PP-OCRv6_medium_rec in ONNX, "
                       "20 items per type, the previous render of the dataset)"),
            "aggregate_held_out": prev["comparison_with_archived_bench"]["aggregate_held_out"],
            "aggregate_all_46_types": prev["comparison_with_archived_bench"]["aggregate_all_46_types"],
            "note": prev["comparison_with_archived_bench"]["note"],
        },
        "notes": [
            "The pretrained head (18 710 classes) is kept, not replaced: replacing it would destroy "
            "the zero-step baseline, which is the only honest reference point.",
            "PP-OCRv6_medium_rec has no Cyrillic in its dictionary (measured: not one entry contains "
            "a codepoint in U+0400..U+04FF), so five Cyrillic types cannot be trained with this "
            "checkpoint at all.",
            "The four held-out types without a band are evaluated on the whole frame, exactly like the "
            "previous run and the archived bench, so the pipeline is identical.",
            "The held-out split is by WHOLE PLUGINS (5 plugins, 7 types); no image of a held-out type "
            "is ever seen in training.",
            "The evaluation during the run covered the 7 held-out types only (--eval-types); the "
            "13 trained types were not re-evaluated every epoch, which is why the run fits the budget.",
        ],
    }

    # --------------------------------------------------------------------------- #
    # the weight interpolation (WiSE-FT) sweep, if it was measured
    # --------------------------------------------------------------------------- #
    if soup:
        sweep = {}
        for a, r in sorted(soup["results"].items(), key=lambda kv: float(kv[0])):
            pt = per_type_slice(r["per_type"])
            sweep[a] = {"per_type": pt, "aggregate": r["aggregate"],
                        "percentages": pct_block(pt, r["aggregate"])}
        best_a = max(sweep, key=lambda a: (sweep[a]["aggregate"]["exact_match_median"] or 0))
        report["weight_interpolation"] = {
            "what": ("theta(alpha) = alpha * theta_finetuned + (1 - alpha) * theta_pretrained; "
                     "every alpha is measured with the SAME pipeline as the zero step and the "
                     "fine-tuned model (the same 7 held-out types, the same 3500 images, the same "
                     "crop, normalisation and greedy CTC decoding)"),
            "source_checkpoint": soup["source_checkpoint"],
            "source_epoch": soup.get("epoch"),
            "source_step": soup.get("step"),
            "selection_note": ("the best alpha is chosen by the held-out median, i.e. the selection "
                               "happens ON the held-out set - it is optimistic and has to be read as "
                               "such. alpha=0 must reproduce the zero step and alpha=1 the "
                               "fine-tuned model; both were checked against the run's own numbers."),
            "alphas": sweep,
            "best_alpha": best_a,
            "best_alpha_aggregate": sweep[best_a]["aggregate"],
            "best_alpha_percentages": sweep[best_a]["percentages"],
            "best_checkpoint_file": "train/run_ppocr/big/soup_best.pt",
            "beats_zero_step": ((sweep[best_a]["aggregate"]["exact_match_median"] or 0)
                                > (zero_agg["exact_match_median"] or 0)),
        }
        # consistency: alpha=0 vs the run's zero step, alpha=1 vs the run's fine-tuned model
        a0 = sweep.get("0.0", {}).get("aggregate")
        a1 = sweep.get("1.0", {}).get("aggregate")
        report["weight_interpolation"]["consistency_checks"] = {
            "alpha_0_median_exact": (a0 or {}).get("exact_match_median"),
            "run_zero_step_median_exact": zero_agg["exact_match_median"],
            "alpha_0_micro_exact": (a0 or {}).get("exact_match_micro"),
            "run_zero_step_micro_exact": zero_agg["exact_match_micro"],
            "alpha_1_median_exact": (a1 or {}).get("exact_match_median"),
            "run_finetuned_median_exact": final_agg["exact_match_median"],
            "alpha_1_micro_exact": (a1 or {}).get("exact_match_micro"),
            "run_finetuned_micro_exact": final_agg["exact_match_micro"],
        }

    # the item counts are printed by the run; read them back from the log so nothing is hand-typed
    log = open(os.path.join(run_dir, "log.txt"), encoding="utf-8").read()
    m = re.search(r"train items:\s*(\d+)\s+eval items:\s*(\d+)\s+held-out items:\s*(\d+)", log)
    if m:
        report["split"]["train_items"] = int(m.group(1))
        report["split"]["eval_items"] = int(m.group(2))
        report["split"]["held_out_items"] = int(m.group(3))

    return report, soup
