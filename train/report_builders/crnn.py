"""The report of the CRNN run, collected from the artefacts of the run.

    .venv-gpu\\Scripts\\python.exe train\\make_report.py crnn

Reads (all of them written by the run itself):

*   `val_report.json` - the trainer's held-out report;
*   `eval_train_types.json` - `train/eval_ckpt.py` on the training types;
*   `train.log` - the loss timeline.

Every number in the report comes from one of those three files.
"""

import json
import os
import re
import statistics

HELD_OUT_TYPES = [
    "CaptchaVerifyZ/map",
    "haq/mapcha/map",
    "jSdCool/minecaptcha/text",
    "laforetbrut/are-you-sure/code",
]

TRAIN_TYPES = [
    "Archy-X/Krypton/map",
    "GalleryCaptcha/ru-web",
    "JSH32/Minecaptcha/map",
    "LagBug/XProtect/reverse",
    "just-captcha/ProstoCaptcha/map",
    "n1zamu/NCaptcha/anvil",
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA/map",
]


def pct(x):
    return None if x is None else round(100.0 * x, 4)


def summarise(per_type, order):
    """Per-type percent metrics + the median over types + the micro over images."""
    types = {}
    for t in order:
        d = per_type.get(t)
        if d is None:
            continue
        types[t] = {
            "n": d["n"],
            "exact_match_pct": pct(d["accuracy"]),
            "cer_pct": pct(d["cer"]),
            "exact": d.get("exact"),
        }
    accs = [v["exact_match_pct"] for v in types.values()]
    cers = [v["cer_pct"] for v in types.values()]
    n = sum(v["n"] for v in types.values())
    ex = sum((v["exact"] or 0) for v in types.values())
    micro_cer = sum(v["cer_pct"] * v["n"] for v in types.values()) / max(1, n)
    out = {
        "per_type": types,
        "median_over_types": {
            "exact_match_pct": round(statistics.median(accs), 4) if accs else None,
            "cer_pct": round(statistics.median(cers), 4) if cers else None,
            "n_types": len(types),
        },
        "micro_over_images": {
            "n_images": n,
            "exact_match_pct": pct(ex / max(1, n)),
            "cer_pct": round(micro_cer, 4),
        },
    }
    if accs:
        out["mean_over_types_for_reference_only"] = {
            "exact_match_pct": round(statistics.mean(accs), 4),
            "cer_pct": round(statistics.mean(cers), 4),
        }
    return out


def parse_log(path):
    """The loss timeline: every logged step and every epoch line.

    Windows PowerShell 5.1's `Tee-Object` writes UTF-16LE, so the encoding is
    detected from the byte-order mark rather than assumed.
    """
    steps, epochs = [], []
    step_re = re.compile(r"step\s+(\d+)\s+loss\s+([0-9.]+)\s+([0-9.]+)\s+img/s\s+elapsed\s+([0-9.]+)")
    ep_re = re.compile(r"epoch\s+(\d+)/(\d+)\s+train loss\s+([0-9.]+)(.*)")
    with open(path, "rb") as f:
        raw = f.read()
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    text = raw.decode(enc, errors="replace")
    for line in text.splitlines():
        m = step_re.search(line)
        if m:
            steps.append({"step": int(m.group(1)), "loss": float(m.group(2)),
                          "img_s": float(m.group(3)), "elapsed_min": float(m.group(4))})
        m = ep_re.search(line)
        if m:
            val = {}
            vm = re.search(r"VAL acc\s+([0-9.]+)\s+CER\s+([0-9.]+)", m.group(4))
            if vm:
                val = {"val_accuracy": float(vm.group(1)), "val_cer": float(vm.group(2))}
            epochs.append({"epoch": int(m.group(1)), "total_epochs": int(m.group(2)),
                           "train_loss": float(m.group(3)), **val})
    return steps, epochs


def build(run_dir):
    """The report as a dict; the caller writes it."""
    with open(os.path.join(run_dir, "val_report.json"), encoding="utf-8") as f:
        val = json.load(f)
    with open(os.path.join(run_dir, "eval_train_types.json"), encoding="utf-8") as f:
        ev = json.load(f)

    held = summarise(val["per_type"], HELD_OUT_TYPES)
    trained = summarise(ev["report"]["per_type"], TRAIN_TYPES)

    steps, epochs = parse_log(os.path.join(run_dir, "train.log"))
    losses = [(s["step"], s["loss"]) for s in steps]
    below_1 = [st for st, ls in losses if ls < 1.0]
    below_01 = [st for st, ls in losses if ls < 0.1]
    below_001 = [st for st, ls in losses if ls < 0.01]
    rates = [s["img_s"] for s in steps if s["step"] > 200]  # skip the warm-up window

    out = {
        "report": "reports/TRAINING_CRNN_BIG.md",
        "date": "2026-10-22",
        "model": {
            "arch": "CRNN (CNN + BiLSTM) + CTC, trained from scratch",
            "classes": 63,
            "parameters": 4623615,
            "file": "train/captcha_crnn.py",
        },
        "split": {
            "kind": "type-held-out (whole plugin/type), never a random image split",
            "training_types": TRAIN_TYPES,
            "held_out_types": HELD_OUT_TYPES,
            "training_images": 3500,
            "held_out_images": 1999,
        },
        "held_out": held,
        "training_types": trained,
        "memorisation_gap": {
            "exact_match_pct": {
                "training_median": trained["median_over_types"]["exact_match_pct"],
                "held_out_median": held["median_over_types"]["exact_match_pct"],
            },
            "cer_pct": {
                "training_median": trained["median_over_types"]["cer_pct"],
                "held_out_median": held["median_over_types"]["cer_pct"],
            },
        },
        "loss_timeline": {
            "logged_steps": steps,
            "epochs": epochs,
            "first_step_below_1.0": below_1[0] if below_1 else None,
            "first_step_below_0.1": below_01[0] if below_01 else None,
            "first_step_below_0.01": below_001[0] if below_001 else None,
            "final_step_loss": losses[-1] if losses else None,
            "median_img_s_after_step_200": round(statistics.median(rates), 1) if rates else None,
        },
        "checkpoint": ev.get("checkpoint"),
        "checkpoint_step": ev.get("step"),
    }
    return out
