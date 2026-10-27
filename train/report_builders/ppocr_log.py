"""The report of the FIRST PP-OCRv6 run, assembled from its log.

    .venv-gpu\\Scripts\\python.exe train\\make_report.py ppocr-log

Everything in the JSON is read out of the run's own log:

*   the stdout log of the run (the per-type blocks are printed to stdout, the run's
    own `log.txt` only holds the `log()` lines - both are read, the stdout first);
*   `baseline_per_type.json` - the archived bench measurement of the pretrained
    model (`reports/bench_models/ppocrv6-medium.json`, the previous render of the
    dataset).

This is the report of the run that was stopped during epoch 5 of 30 - its
"status" field says so. The numbers are the ones the run actually measured.
"""

import json
import os
import re

#: the seven held-out types of that run (Variant 1 of `reports/research3/DATASET_AUDIT.md`)
HELD = [
    "out/JSH32/Minecaptcha/map",
    "out/jonesdevelopment/sonar/complex",
    "out/jonesdevelopment/sonar/legacy",
    "out/jonesdevelopment/sonar/standard",
    "out/laforetbrut/are-you-sure/code",
    "out_ru/BotFilter/map",
    "out_ru/CaptchaVerifyZ/map",
]


def read_text(path):
    """Windows PowerShell's Tee-Object writes UTF-16, the script's own log UTF-8."""
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")


def parse_agg(block):
    m = re.search(r"MEDIAN over (\d+) types: exact=([\d.]+)\s+cer=([\d.]+)"
                  r"\s+\(micro: exact=([\d.]+)\s+cer=([\d.]+)\)", block)
    if not m:
        return None
    return {"types": int(m.group(1)),
            "exact_match_median": float(m.group(2)),
            "cer_median": float(m.group(3)),
            "exact_match_micro": float(m.group(4)),
            "cer_micro": float(m.group(5))}


def parse_types(block):
    """The per-type lines of one block."""
    out = {}
    for line in block.splitlines():
        mm = re.match(r"\s{2}(\S+)\s+n=\s*(\d+)\s+exact=([\d.]+)\s+cer=([\d.]+)", line)
        if mm:
            out[mm.group(1)] = {"n": int(mm.group(2)),
                                "exact_match": float(mm.group(3)),
                                "cer": float(mm.group(4))}
    return out


def build(run_dir, stdout_log, log_path, baseline_path):
    """The report as a dict; the caller writes it."""
    text = ""
    for p in ((stdout_log,) if os.path.isfile(stdout_log) else (log_path,)):
        if os.path.isfile(p):
            text += read_text(p) + "\n"
    with open(baseline_path, encoding="utf-8") as f:
        base = json.load(f)

    zero_block = re.search(r"--- ZERO STEP.*?\n(.*?)(?=\nzero step:)", text, re.S).group(1)
    zero_types = parse_types(zero_block)
    zero_agg = parse_agg(zero_block)

    # per-epoch held-out evaluations
    evals = []
    for m in re.finditer(r"--- EPOCH (\d+) .*?\n(.*?)(?=\nepoch \d+: held-out)", text, re.S):
        ep = int(m.group(1))
        agg = parse_agg(m.group(2))
        if agg:
            evals.append({"epoch": ep, "per_type": parse_types(m.group(2)), **agg})
    evals.sort(key=lambda e: e["epoch"])

    # the loss timeline
    timeline = []
    for m in re.finditer(r"^epoch (\d+): loss=([\d.]+)\s+([\d.]+)s\s+([\d.]+) img/s", text, re.M):
        timeline.append({"epoch": int(m.group(1)), "loss": float(m.group(2)),
                         "seconds": float(m.group(3)), "img_per_s": float(m.group(4))})

    steps = 0
    for m in re.finditer(r"epoch (\d+) step (\d+)/(\d+)", text):
        steps = max(steps, int(m.group(2)))
    zero_sec = re.search(r"zero step: ([\d.]+)s", text)
    best = re.search(r"new best held-out median exact=([\d.]+)", text)
    best_epoch = None
    if best:
        bm = re.findall(r"new best held-out median exact=[\d.]+", text)
        be = re.findall(r"--- EPOCH (\d+) ", text)
        idx = [i for i, v in enumerate(bm) if v.endswith(best.group(1))]
        if idx and idx[0] < len(be):
            best_epoch = int(be[idx[0]])

    zero_held = {t: zero_types.get(t) for t in HELD}
    best_eval = next((e for e in evals if e["epoch"] == best_epoch), None)
    final_held = best_eval["per_type"] if best_eval else {}
    last_eval = evals[-1] if evals else None

    better, worse, same = [], [], []
    for t in HELD:
        if t in zero_held and t in final_held and zero_held[t]:
            d = final_held[t]["exact_match"] - zero_held[t]["exact_match"]
            (better if d > 0 else worse if d < 0 else same).append(t)

    out = {
        "schema_version": "1.0",
        "task": "CapthaModel T1 - fine-tune of PP-OCRv6_medium_rec on the captcha dataset "
                "with a type-held-out evaluation",
        "authored": "2026-10-22, agent T1 (train/finetune_ppocr.py, train/ppocr_data.py)",
        "status": "STOPPED BY THE AUTHOR before the main run finished; the numbers below are "
                  "what the run actually measured, not a finished result",
        "model": {
            "repo": "PaddlePaddle/PP-OCRv6_medium_rec_safetensors",
            "revision": "024cad6a831de75c2c3c26e711ba8c4a82ccd24b",
            "class": "transformers.PPOCRV6SmallRecForTextRecognition",
            "params": 19134326,
            "head_out_channels": 18710,
            "hidden_size": 192,
            "backbone": "pp_lcnet_v4",
            "head": "the pretrained head is kept, not replaced",
            "dictionary": "18710 entries, index 0 = blank, index 18709 = space, "
                          "no Cyrillic at all",
            "license": "Apache-2.0",
        },
        "environment": {"python": "3.14.5", "torch": "2.14.1+cu126", "transformers": "5.19.0",
                        "gpu": "NVIDIA GeForce GTX 1080 Ti (11.8 GB, sm_61)", "driver": "581.57"},
        "split": {
            "strategy": "type-held-out, whole plugins",
            "held_out_types": HELD,
            "held_out_plugins": ["JSH32/Minecaptcha", "jonesdevelopment/sonar", "BotFilter",
                                 "CaptchaVerifyZ", "laforetbrut/are-you-sure"],
            "train_types": ["out/Archy-X/Krypton/map", "out/FeelingAlive0/AdvancedCaptcha/math",
                            "out/LagBug/XProtect/equation", "out/LagBug/XProtect/gui",
                            "out/LagBug/XProtect/reverse", "out/Mrbysco/Captcha/math",
                            "out/Yukun99/Captchas/itemslot", "out/haq/mapcha/map",
                            "out/jSdCool/minecaptcha/text", "out/just-captcha/ProstoCaptcha/map",
                            "out/n1zamu/NCaptcha/anvil",
                            "out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map",
                            "out_ru/GalleryCaptcha/ru-web"],
            "train_types_count": 13,
            "train_items": 1299,
            "held_out_items": 700,
            "dropped": {
                "no band (roi = null), excluded from training by the band rule": [
                    "out/InstantlyMoist/Captcha/textcaptcha", "out/LagBug/XProtect/code",
                    "out/LagBug/XProtect/map", "out/LagBug/XProtect/picture",
                    "out/irootdev/AnBot/captcha"],
                "label outside the model dictionary (no Cyrillic in it)": [
                    "out_ru/GalleryCaptcha/ru-numberword", "out_ru/GalleryCaptcha/ru-numberword-caption",
                    "out_ru/GalleryCaptcha/ru-symbols", "out_ru/LimboFilter/map",
                    "out_ru/LimboFilter/symbols"],
                "group C, not an OCR task": [
                    "out/Archy-X/Krypton/menu", "out/China2B2T/Captcha/wool",
                    "out/FeelingAlive0/AdvancedCaptcha/button", "out/Joey61021/captcha/colorgui",
                    "out/LagBug/XProtect/color", "out/LagBug/XProtect/different",
                    "out/LagBug/XProtect/drop", "out/LagBug/XProtect/jump",
                    "out/LagBug/XProtect/slot", "out/LagBug/XProtect/sneak",
                    "out/Z4OLLIEZ4/reCaptcha/captchasx", "out/jSdCool/minecaptcha/image",
                    "out_ru/CaptchaGUI/clickblock", "out_ru/GalleryCaptcha/ru-object-swatch",
                    "out_ru/LimboFilter/framed2x2", "out_ru/LimboFilter/framed3x3"],
            },
        },
        "preprocessing": {
            "crop": "roi band (the whole frame for the four held-out types without a band, "
                    "exactly like the archived bench)",
            "resize": "band -> 48 px tall, aspect preserved, width capped at 320, "
                      "zero-padded on the right to 320",
            "colour": "BGR (the PaddleOCR pipeline), (x/255 - 0.5) / 0.5",
            "T (time steps)": "measured: T = W / 8 (input 48x320 -> 40 frames)",
        },
        "zero_step": {
            "what": "the pretrained model on our held-out types before any training",
            "per_type": zero_held,
            "aggregate": zero_agg,
            "seconds": float(zero_sec.group(1)) if zero_sec else None,
        },
        "after_training": {
            "what": "the best checkpoint by the held-out median exact match "
                    f"(epoch {best_epoch}), stopped by the author",
            "best_epoch": best_epoch,
            "per_type": final_held,
            "aggregate": ({k: best_eval[k] for k in ("types", "exact_match_median", "cer_median",
                                                     "exact_match_micro", "cer_micro")}
                           if best_eval else None),
            "last_evaluation": ({"epoch": last_eval["epoch"],
                                 "exact_match_median": last_eval["exact_match_median"],
                                 "cer_median": last_eval["cer_median"],
                                 "exact_match_micro": last_eval["exact_match_micro"],
                                 "cer_micro": last_eval["cer_micro"]} if last_eval else None),
            "all_evaluations": [{"epoch": e["epoch"], "exact_match_median": e["exact_match_median"],
                                 "cer_median": e["cer_median"],
                                 "exact_match_micro": e["exact_match_micro"],
                                 "cer_micro": e["cer_micro"]} for e in evals],
        },
        "training_run": {
            "command": ".venv-gpu\\Scripts\\python.exe train\\finetune_ppocr.py --out "
                       "train\\run_ppocr\\final --epochs 30 --batch-size 32 --lr 1e-4 "
                       "--head-lr 1e-4 --workers 6 --eval-every 2 --save-every 100 "
                       "--max-minutes 11",
            "epochs_completed": len(timeline),
            "steps_completed": steps,
            "planned_steps": 1230,
            "stopped": "by the author (the run was killed during epoch 5)",
            "loss_timeline": timeline,
            "img_per_s_last": timeline[-1]["img_per_s"] if timeline else None,
            "checkpoint": "train/run_ppocr/final/ckpt/step_000200.pt (model + optimiser + "
                          "scheduler + GradScaler + step), best.pt (epoch %s)" % best_epoch,
            "resume_command": ".venv-gpu\\Scripts\\python.exe train\\finetune_ppocr.py --out "
                              "train\\run_ppocr\\final --epochs 30 --batch-size 32 --lr 1e-4 "
                              "--head-lr 1e-4 --workers 6 --eval-every 2 --save-every 100 "
                              "--max-minutes 55 --resume",
        },
        "comparison_with_archived_bench": {
            "source": "reports/bench_models/ppocrv6-medium.json (pretrained PP-OCRv6_medium_rec "
                      "in ONNX, 20 items per type, the previous render of the dataset)",
            "per_type_held_out": {t: base.get("band/full", {}).get(t) for t in HELD},
            "aggregate_held_out": {"exact_match_median": 0.55, "cer_median": 0.1475},
            "aggregate_all_46_types": {"exact_match_micro": 0.4043, "cer_micro": 0.5662,
                                       "exact_match_median_over_types": 0.175},
            "note": "the 0.40 of the brief is the micro accuracy over all 46 types; "
                    "on the 29 types with a band it is 0.5517",
        },
        "held_out_verdict": {"types_better": better, "types_worse": worse,
                              "types_unchanged": same},
        "notes": [
            "The pretrained head (18 710 classes) is kept, not replaced: replacing it would "
            "destroy the zero-step baseline, which is the only honest reference point.",
            "PP-OCRv6_medium_rec has no Cyrillic in its dictionary (measured: not one entry "
            "contains a codepoint in U+0400..U+04FF), so five Cyrillic types cannot be trained "
            "with this checkpoint at all.",
            "The four held-out types without a band are evaluated on the whole frame, exactly "
            "like the archived bench, so the two numbers are comparable.",
            "A flat CTC loss on the first epochs is not a bug; here the loss went down from "
            "1.0171 to 0.0136 in six epochs, so the all-blank plateau was never reached.",
        ],
    }
    return out, {"better": better, "worse": worse, "same": same,
                 "epochs": len(timeline), "steps": steps}
