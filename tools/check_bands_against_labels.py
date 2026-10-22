"""Does every roi() band carry the answer, and nothing else?

    python tools/check_bands_against_labels.py dataset/out dataset/out_ru

The `roi` field of a sample is the bounding box of the text band that carries the
answer - the line of a chat log, the name in a window title, the code on a map. A
recogniser is trained on that crop, so a band that points at the wrong text is worse
than no band at all: the label cannot be fitted, the loss does not come down, and the
type silently scores 0.000. That is not a hypothetical - it is what a band that
pointed at the plugin's own prefix instead of the answer did to one training run.

So this checks the pixels, not the metadata. For every sample with a band it crops
the band and looks at the colours in it:

  * the ink colour of the answer has to be in the crop - the answer is written in a
    colour of its own (red in a chat line, yellow in a map, aqua in a dialog), so a
    crop without it holds something else;
  * the ink colours of the text that must NOT be in the band have to be absent - the
    instruction line, the window title, the caption.

The rules are per type, in the RULES table below. A type that is not in the table is
reported with its colour census, so the table can be extended.

The other two checks live next to this one: `check_labels_and_roi.py` re-derives the
labels and checks that the band is inside the canvas, and `check_band_vs_answer.py`
compares the `text` and `answer` fields (they differ on purpose for the number-word
and the arithmetic families).
"""

import json
import os
import sys

from PIL import Image

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


def census(im):
    """The colour histogram of an image: {colour: pixels}."""
    return {colour: n for n, colour in (im.getcolors(maxcolors=1 << 24) or [])}


def check(root, verbose):
    """Check every sample with a band under one dataset root."""
    failures = []
    checked = 0
    without_rule = {}
    for dirpath, dirnames, filenames in os.walk(root):
        if "real_shots" in os.path.relpath(dirpath, root).split(os.sep):
            continue
        if "labels.jsonl" not in filenames:
            continue
        rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
        rows = [json.loads(l) for l in open(os.path.join(dirpath, "labels.jsonl"), encoding="utf-8")]
        for row in rows:
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
    return checked, failures


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    verbose = "--verbose" in sys.argv
    roots = [a for a in sys.argv[1:] if not a.startswith("--")]
    total = 0
    failures = []
    for root in roots:
        checked, bad = check(root, verbose)
        print(f"{root}: {checked} bands checked")
        total += checked
        failures += bad
    print(f"\n{total} bands checked against the label")
    if failures:
        print(f"{len(failures)} FAILURES:")
        for f in failures:
            print("  " + f)
        return 1
    print("every band carries the answer's ink and none of the other text's ink")
    return 0


if __name__ == "__main__":
    sys.exit(main())
