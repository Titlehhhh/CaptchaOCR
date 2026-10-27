"""One checker for the text bands of a dataset - three modes, one logic.

The repository used to carry three overlapping band checkers:

* ``check_band_vs_answer.py``          - per type: does the band carry the answer,
  the drawn text, or is there no band at all?
* ``check_bands_against_labels.py``    - per sample: does the band carry the answer's
  ink and none of the other text's ink?
* ``check_caption_outside_roi.py``     - per sample: is the caption's ink ever inside
  the band of a composite?

They are one script with a ``--mode`` now; the three old file names stay as thin
wrappers, because the documentation and the runbooks point at them:

    python tools/check_bands.py --mode summary dataset/out_ru
    python tools/check_bands.py --mode ink     dataset/out dataset/out_ru --verbose
    python tools/check_bands.py --mode caption dataset/out_ru/GalleryCaptcha/ru-numberword-caption

    python tools/check_band_vs_answer.py       dataset/out_ru      # == --mode summary
    python tools/check_bands_against_labels.py dataset/out dataset/out_ru   # == --mode ink
    python tools/check_caption_outside_roi.py  dataset/out_ru/.../ru-numberword-caption

The exit codes are the old ones: ``0`` - nothing found, ``1`` - a problem was found,
``2`` - the arguments are wrong.

What the modes mean
-------------------

**summary** - the band is where the recogniser looks, so a type without one cannot be
a recogniser's training target.  For every type the table says how many samples
carry a band and how many of them have ``text == answer``.  The two differ on
purpose for the number-word family (the map shows the number in Russian words, the
player answers with the digits) and for the reversed family.

**ink** - the colour-level rule: the answer is written in a colour of its own (red in
a chat line, yellow on a map, aqua in a dialog), so a crop without that colour holds
something else.  The rules are per type, in the ``RULES`` table; a type that is not in
the table is reported with its colour census, so the table can be extended.

**caption** - the caption of a composite is a *different* string from the answer, so a
recogniser that is handed the text band must never see it.  The band of a composite
is the band of the map, cut off at the first row the caption's ink is on - this mode
checks that the cut really works, by looking for the caption's own fill colour inside
the band.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


# =====================================================================================
# shared: the walk over the dataset
# =====================================================================================

def type_dirs(root: str) -> list[str]:
    """Every directory of ``root`` that holds a ``labels.jsonl`` (real_shots excluded)."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        if "real_shots" in os.path.relpath(dirpath, root).split(os.sep):
            continue
        if "labels.jsonl" in filenames:
            out.append(dirpath)
    return out


def load_rows(dirpath: str) -> list[dict]:
    """The label rows of one type directory."""
    path = os.path.join(dirpath, "labels.jsonl")
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def rel_of(dirpath: str, root: str) -> str:
    return os.path.relpath(dirpath, root).replace(os.sep, "/")


# =====================================================================================
# mode: summary - does the band carry the answer?
# =====================================================================================

def mode_summary(roots: list[str]) -> int:
    """Per type: how many samples carry a band, and how many have text == answer."""
    for root in roots:
        print(f"{'type':<40} {'n':>4} {'band':>5} {'text==answer':>13}  note")
        print("-" * 96)
        for dirpath in type_dirs(root):
            rel = rel_of(dirpath, root)
            rows = load_rows(dirpath)
            n = len(rows)
            with_band = sum(1 for r in rows if r.get("roi"))
            same = sum(1 for r in rows if r.get("text") == r.get("answer"))
            if with_band == 0:
                note = "no band - not a recogniser's training target"
            elif same == n:
                note = "the band holds the answer"
            else:
                ex = next(r for r in rows if r.get("text") != r.get("answer"))
                note = (f"the band holds the TEXT, the answer is the value: "
                        f"{ex['text']!r} -> {ex['answer']!r}")
            print(f"{rel:<40} {n:>4} {with_band:>5} {same:>13}  {note}")
    return 0


# =====================================================================================
# mode: ink - does the band carry the answer's ink and nothing else?
# =====================================================================================

# --------------------------------------------------------------------------
# The rules. For every type: the ink colour(s) of the answer, the ink colour(s) of
# the text that must not be in the band, and - where the answer is written in
# several colours - the number of ink pixels that have to be in the crop.
#
#   "type": ([answer ink], [ink that must not be there], min ink pixels, [background])
# --------------------------------------------------------------------------
RULES = {
    # --- the 18-plugin tree -------------------------------------------------
    # the answer is the red run of the chat line, the prefix is gold and grey
    "LagBug/XProtect/equation": ([(255, 85, 85)], [(255, 170, 0), (170, 170, 170), (255, 255, 255)]),
    "LagBug/XProtect/reverse": ([(255, 85, 85)], [(255, 170, 0), (170, 170, 170), (255, 255, 255)]),
    "LagBug/XProtect/slot": ([(255, 85, 85)], [(255, 170, 0), (170, 170, 170), (255, 255, 255)]),
    "LagBug/XProtect/sneak": ([(255, 85, 85)], [(255, 170, 0), (170, 170, 170), (255, 255, 255)]),
    "LagBug/XProtect/jump": ([(255, 85, 85)], [(255, 170, 0), (170, 170, 170), (255, 255, 255)]),
    "LagBug/XProtect/drop": ([(255, 85, 85)], [(255, 170, 0), (170, 170, 170), (255, 255, 255)]),
    "LagBug/XProtect/gui": ([(255, 85, 85)], [(255, 170, 0), (170, 170, 170), (255, 255, 255)]),
    # the answer is the white run of the footer, the caption above it is grey
    "n1zamu/NCaptcha/anvil": ([(255, 255, 255)], [(170, 170, 170)]),
    # the answer is the red name in the window title
    "Yukun99/Captchas/itemslot": ([(255, 85, 85)], [(255, 255, 255), (85, 215, 255)]),
    # the title is white on the grey panel
    "Z4OLLIEZ4/reCaptcha/captchasx": ([(255, 255, 255)], [(255, 85, 85)]),
    "Joey61021/captcha/colorgui": ([(255, 255, 255)], [(255, 85, 85)]),
    # the chat line is white, the candidate buttons below it are coloured
    "FeelingAlive0/AdvancedCaptcha/math": ([(255, 255, 255)], [(255, 85, 85), (85, 255, 85), (255, 255, 85)]),
    "FeelingAlive0/AdvancedCaptcha/button": ([(255, 255, 255)], [(255, 85, 85), (85, 255, 85), (255, 255, 85)]),
    # the question is yellow, the rest of the screen is white or red
    "Mrbysco/Captcha/math": ([(255, 255, 85)], [(255, 255, 255), (255, 85, 85)]),
    # the code is black on white paper
    "Archy-X/Krypton/map": ([(0, 0, 0)], []),
    # white code on the black map
    "haq/mapcha/map": ([(255, 255, 255)], []),
    # black code on the white map
    "JSH32/Minecaptcha/map": ([(0, 0, 0)], []),
    # the code is (235,242,255) on the gradient
    "just-captcha/ProstoCaptcha/map": ([(235, 242, 255)], []),
    # the sheet is white, the glyphs are coloured - so the ink is everything that
    # is not the sheet
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA/map": ([], [], 20, [(255, 255, 255)]),
    # the aqua answer line in the dialog
    "jSdCool/minecaptcha/text": ([(0, 255, 255)], []),
    # the sprite indices in the dialog row are white
    "jSdCool/minecaptcha/image": ([(255, 255, 255)], []),
    # --- the catalogue tree --------------------------------------------------
    # the code is yellow on the dark grey field
    "CaptchaVerifyZ/map": ([(255, 255, 0)], [(255, 255, 255), (211, 211, 211)]),
}


def census(im) -> dict:
    """The colour histogram of an image: {colour: pixels}."""
    return {colour: n for n, colour in (im.getcolors(maxcolors=1 << 24) or [])}


def mode_ink(roots: list[str], verbose: bool = False) -> int:
    """Check every sample with a band under one dataset root."""
    total = 0
    failures: list[str] = []
    for root in roots:
        checked = 0
        without_rule: dict[str, dict] = {}
        for dirpath in type_dirs(root):
            rel = rel_of(dirpath, root)
            for row in load_rows(dirpath):
                roi = row.get("roi")
                if not roi:
                    continue
                checked += 1
                x, y, w, h = roi
                with Image.open(os.path.join(dirpath, row["file"])) as im:
                    frame = im.convert("RGB")
                if x < 0 or y < 0 or x + w > frame.width or y + h > frame.height:
                    failures.append(f"{rel}/{row['file']}: the band {roi} is outside the frame")
                    continue
                crop = frame.crop((x, y, x + w, y + h))
                counts = census(crop)
                rule = RULES.get(rel)
                if rule is None:
                    without_rule.setdefault(rel, counts)
                    continue
                must, must_not = rule[0], rule[1]
                min_ink = rule[2] if len(rule) > 2 else 0
                background = rule[3] if len(rule) > 3 else []
                missing = [c for c in must if c not in counts]
                present = [c for c in must_not if c in counts]
                ink = sum(n for c, n in counts.items() if c not in background)
                if missing or present or (min_ink and ink < min_ink):
                    failures.append(
                        f"{rel}/{row['file']}: band {roi} of {row.get('answer')!r} - "
                        f"missing {missing}, unexpected {present}, ink {ink}")
        if verbose:
            for rel, counts in sorted(without_rule.items()):
                top = sorted(counts.items(), key=lambda kv: -kv[1])[:4]
                print(f"  (no rule) {rel:48s} colours={top}")
        print(f"{root}: {checked} bands checked")
        total += checked
    print(f"\n{total} bands checked against the label")
    if failures:
        print(f"{len(failures)} FAILURES:")
        for f in failures:
            print("  " + f)
        return 1
    print("every band carries the answer's ink and none of the other text's ink")
    return 0


# =====================================================================================
# mode: caption - the caption's ink must never be inside the band
# =====================================================================================

ORANGE = (216, 127, 51)
WHITE = (255, 255, 255)


def caption_pixels(path: str) -> dict:
    """The rows that carry the caption: the ones with a long run of a caption colour."""
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        px = rgb.load()
        rows = {}
        for y in range(rgb.height):
            n_orange = n_white = 0
            for x in range(rgb.width):
                p = px[x, y]
                if p == ORANGE:
                    n_orange += 1
                elif p == WHITE:
                    n_white += 1
            if n_orange > 20:
                rows[y] = "orange"
            elif n_white > 40:
                rows[y] = "white"
        return rows


def mode_caption(directory: str) -> int:
    """Check one type directory: no caption ink inside the band."""
    rows = load_rows(directory)
    bad = 0
    checked = 0
    for r in rows:
        path = os.path.join(directory, r["file"])
        cap = caption_pixels(path)
        if not cap:
            continue
        checked += 1
        roi = r.get("roi")
        if not roi:
            print(f"!! {r['file']}: no roi")
            bad += 1
            continue
        x, y, w, h = roi
        inside = [ry for ry in cap if y <= ry < y + h]
        if inside:
            bad += 1
            print(f"!! {r['file']}: caption ink on rows {inside} inside the band {roi}")
    print(f"{checked} samples with a detectable caption, "
          f"{bad} with caption ink inside the band")
    print("RESULT:", "OK" if bad == 0 else "<-- CHECK")
    return 0 if bad == 0 else 1


# =====================================================================================
# cli
# =====================================================================================

def build_parser(prog: str = "check_bands.py") -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog=prog,
        description="Check the text bands of a dataset: does the band carry the answer "
                    "(summary), the answer's ink and nothing else (ink), and is the "
                    "caption's ink outside the band (caption)?")
    ap.add_argument("--mode", default="summary",
                    choices=["summary", "ink", "caption"],
                    help="which check to run (default: summary)")
    ap.add_argument("--verbose", action="store_true",
                    help="ink mode: print the colour census of the types without a rule")
    ap.add_argument("roots", nargs="*",
                    help="dataset root(s) (summary, ink) or one type directory (caption)")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode == "caption":
        if len(args.roots) != 1:
            print("the caption mode takes exactly one type directory", file=sys.stderr)
            return 2
        return mode_caption(args.roots[0])
    if not args.roots:
        print("give at least one dataset root", file=sys.stderr)
        return 2
    if args.mode == "summary":
        return mode_summary(args.roots)
    return mode_ink(args.roots, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
