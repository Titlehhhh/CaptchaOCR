import os
import random
import statistics
import time

import numpy as np
import torch

from .ppocr_data import cer, find_types, type_stats

DEFAULT_VAL_TYPES = [
    "out/jonesdevelopment/sonar/standard",
    "out/jonesdevelopment/sonar/legacy",
    "out/jonesdevelopment/sonar/complex",
    "out_ru/BotFilter/map",
    "out_ru/CaptchaVerifyZ/map",
    "out/laforetbrut/are-you-sure/code",
    "out/JSH32/Minecaptcha/map",
]

GROUP_C = [
    "out/Archy-X/Krypton/menu",
    "out/China2B2T/Captcha/wool",
    "out/FeelingAlive0/AdvancedCaptcha/button",
    "out/Joey61021/captcha/colorgui",
    "out/LagBug/XProtect/color",
    "out/LagBug/XProtect/different",
    "out/LagBug/XProtect/drop",
    "out/LagBug/XProtect/jump",
    "out/LagBug/XProtect/slot",
    "out/LagBug/XProtect/sneak",
    "out/Z4OLLIEZ4/reCaptcha/captchasx",
    "out/jSdCool/minecaptcha/image",
    "out_ru/GalleryCaptcha/ru-object-swatch",
    "out_ru/CaptchaGUI/clickblock",
    "out_ru/LimboFilter/framed2x2",
    "out_ru/LimboFilter/framed3x3",
]


def norm(s):
    if s is None:
        return ""
    return "".join(ch for ch in str(s) if ch.isalnum() or ch in "+-*/=")


def aggregate(per_type, cer_micro_over="all", empty_items=None):
    if not per_type:
        out = {"types": 0}
        if empty_items is not None:
            out["items"] = empty_items
        out.update({"exact_match_median": None, "cer_median": None,
                    "exact_match_micro": None, "cer_micro": None})
        return out
    accs = [v["exact_match"] for v in per_type.values()]
    cers = [v["cer"] for v in per_type.values() if v["cer"] is not None]
    n = sum(v["n"] for v in per_type.values())
    ex = sum(v["exact_match"] * v["n"] for v in per_type.values())
    cn = sum(v["n"] for v in per_type.values() if v["cer"] is not None)
    cs = sum(v["cer"] * v["n"] for v in per_type.values() if v["cer"] is not None)
    if cer_micro_over == "cer":
        micro_cer = round(cs / max(cn, 1), 4) if cn else None
    else:
        micro_cer = round(cs / max(n, 1), 4)
    return {
        "types": len(per_type),
        "items": n,
        "exact_match_median": round(statistics.median(accs), 4),
        "cer_median": round(statistics.median(cers), 4) if cers else None,
        "exact_match_micro": round(ex / max(n, 1), 4),
        "cer_micro": micro_cer,
    }


def print_per_type(per_type, title, agg_fn, precision=3):
    print(f"--- {title} ---")
    for t in sorted(per_type):
        v = per_type[t]
        c = v["cer"] if v["cer"] is not None else float("nan")
        print(f"  {t:48s} n={v['n']:4d} exact={v['exact_match']:.{precision}f} cer={c:.{precision}f}")
    agg = agg_fn(per_type)
    print(f"  MEDIAN over {agg['types']} types: exact={agg['exact_match_median']} "
          f"cer={agg['cer_median']}  (micro: exact={agg['exact_match_micro']} cer={agg['cer_micro']})")
    return agg


def accumulate_type(per_type, t, pred, gold):
    p, g = norm(pred), norm(gold)
    d = per_type.setdefault(t, {"n": 0, "exact": 0, "exact_raw": 0, "cer": []})
    d["n"] += 1
    d["exact"] += int(p == g)
    d["exact_raw"] += int(pred == gold)
    c = cer(p, g)
    if c is not None:
        d["cer"].append(c)
    return d


def finalise_per_type(per_type):
    out = {}
    for t, d in per_type.items():
        out[t] = {
            "n": d["n"],
            "exact_match": round(d["exact"] / d["n"], 4),
            "exact_match_raw": round(d["exact_raw"] / d["n"], 4),
            "cer": round(statistics.fmean(d["cer"]), 4) if d["cer"] else None,
        }
    return out


def discover_types(roots):
    types = find_types(roots)
    stats = {s["type"]: s for s in type_stats(types)}
    return types, stats


def build_split(types, stats, args, group_c, keep_type):
    def matches(tid, patterns):
        return any(p in tid for p in patterns)

    train_types, val_types, dropped = [], [], []
    for tid, directory in types:
        st = stats[tid]
        if matches(tid, args.val_types):
            val_types.append((tid, directory))
            continue
        if matches(tid, args.exclude_types):
            dropped.append((tid, "excluded by --exclude-types"))
            continue
        if tid in group_c:
            dropped.append((tid, "group C: not an OCR task"))
            continue
        keep, why = keep_type(st)
        if not keep:
            dropped.append((tid, why))
            continue
        train_types.append((tid, directory))
    return train_types, val_types, dropped, stats


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def pick_device(spec):
    if spec == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device("cuda" if spec == "cuda" else spec)


def open_log(out_dir):
    log_path = os.path.join(out_dir, "log.txt")
    log_f = open(log_path, "a", encoding="utf-8")

    def log(msg):
        print(msg, flush=True)
        log_f.write(str(msg) + "\n")
        log_f.flush()

    return log, log_f


def runtime_block(t_start, step_times, img_times, extra=None):
    out = {
        "seconds": round(time.time() - t_start, 1),
        "minutes": round((time.time() - t_start) / 60.0, 2),
        "img_per_s": round(sum(img_times) / max(sum(step_times), 1e-9), 1),
        "step_ms": round(1000 * sum(step_times) / max(len(step_times), 1), 1),
    }
    if extra:
        out.update(extra)
    return out
