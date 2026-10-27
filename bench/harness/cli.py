
import argparse
import os

from .config import RESULTS_DIR
from .registry import MODELS
from .runner import contact_sheet, run_model


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="bench_models.py",
        description="Run ready-made captcha/OCR models on OUR dataset under ONE "
                    "protocol (46 types x 20 = 920 items, band and frame input).")
    ap.add_argument("--models", default="", help="comma separated keys of MODELS")
    ap.add_argument("--sets", default="full,legacy104,legacy64")
    ap.add_argument("--modes", default="band,frame")
    ap.add_argument("--n", type=int, default=20, help="samples per type in the 'full' set")
    ap.add_argument("--out", default=RESULTS_DIR)
    ap.add_argument("--contact-sheet", default="", help="path of a result json")
    ap.add_argument("--contact-mode", default="band")
    ap.add_argument("--contact-set", default="full")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.contact_sheet:
        base = os.path.splitext(os.path.basename(args.contact_sheet))[0]
        contact_sheet(args.contact_sheet,
                      os.path.join(args.out, f"errors_{base}.png"),
                      mode=args.contact_mode, set_name=args.contact_set)
        return 0

    keys = [k.strip() for k in args.models.split(",") if k.strip()]
    sets = [s.strip() for s in args.sets.split(",") if s.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for k in keys:
        if k not in MODELS:
            print(f"unknown model key: {k}; known: {', '.join(MODELS)}")
            continue
        print(f"===== {k} ({MODELS[k]['repo']}) =====", flush=True)
        run_model(k, MODELS[k], sets, modes, args.n, args.out)
    return 0
