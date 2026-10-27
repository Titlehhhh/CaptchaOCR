"""Check the labels and the ROI bands of a generated dataset.

Two independent checks, both run over every `labels.jsonl` of a dataset root:

1. **The labels.**  For every sample whose answer is a number, the words in the `text`
   field are re-derived from the digits with a Russian-number spelling that is written
   from scratch here, and compared against the label.  The spelling is cross-checked
   against a *parser* that reads the words back into a number, so an off-by-one in the
   table cannot pass unnoticed: a word that belongs to a different place value makes
   the two disagree.

   A previous version of this project had an off-by-one in exactly this function and
   poisoned 18 % of the dataset with wrong labels, which is why the check is written
   twice and independently of the generator.

   Samples whose answer is not a number (the symbol and the object-swatch families) are
   checked the other way round: the `text` must be the answer itself.  The same holds for
   the `reverse` family, where the band holds the code that is drawn and the answer is
   that code with the letters reversed - the answer is re-derived from the text there too.

2. **The ROI.**  For every sample that carries a `roi`, the band is cropped out of the
   PNG and must be inside the canvas, must not be empty and must not be a single flat
   colour - a recogniser that is handed such a band has nothing to read.

Usage:
    python tools/check_labels_and_roi.py dataset/out_ru
"""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import REPO  # noqa: E402

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


# --------------------------------------------------------------------------
# an independent Russian-number spelling
# --------------------------------------------------------------------------

# keyed by the VALUE, not by an index - the two tables of the generator are keyed by
# the index, so a slip in one of them cannot be copied into the other.
ONES = {
    1: "один", 2: "два", 3: "три", 4: "четыре", 5: "пять",
    6: "шесть", 7: "семь", 8: "восемь", 9: "девять",
}
TEENS = {
    10: "десять", 11: "одиннадцать", 12: "двенадцать", 13: "тринадцать",
    14: "четырнадцать", 15: "пятнадцать", 16: "шестнадцать", 17: "семнадцать",
    18: "восемнадцать", 19: "девятнадцать",
}
TENS = {
    20: "двадцать", 30: "тридцать", 40: "сорок", 50: "пятьдесят",
    60: "шестьдесят", 70: "семьдесят", 80: "восемьдесят", 90: "девяносто",
}
HUNDREDS = {
    100: "сто", 200: "двести", 300: "триста", 400: "четыреста",
    500: "пятьсот", 600: "шестьсот", 700: "семьсот", 800: "восемьсот",
    900: "девятьсот",
}

# the same words again, this time as a word -> value table, written out separately
VALUE_OF = {
    "один": 1, "два": 2, "три": 3, "четыре": 4, "пять": 5,
    "шесть": 6, "семь": 7, "восемь": 8, "девять": 9,
    "десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13,
    "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17,
    "восемнадцать": 18, "девятнадцать": 19,
    "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
    "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
    "сто": 100, "двести": 200, "триста": 300, "четыреста": 400,
    "пятьсот": 500, "шестьсот": 600, "семьсот": 700, "восемьсот": 800,
    "девятьсот": 900,
}


def spell(n):
    """The number in Russian words, lower case, without the "и" connector."""
    words = []
    hundreds = (n // 100) * 100
    rest = n % 100
    if hundreds:
        words.append(HUNDREDS[hundreds])
    if 10 <= rest <= 19:
        words.append(TEENS[rest])
    else:
        tens = (rest // 10) * 10
        unit = rest % 10
        if tens:
            words.append(TENS[tens])
        if unit:
            words.append(ONES[unit])
    return " ".join(words)


def parse(text):
    """Read the words back into a number - the inverse of :func:`spell`.

    <p>The word -> value table is written out again, independently of the tables above,
    so that a slip in one of them cannot be cancelled out by the same slip in the other.
    Every word contributes its place value, and the three categories are disjoint, so
    the sum is the number.
    """
    total = 0
    for word in text.split():
        if word not in VALUE_OF:
            raise ValueError("unknown word: " + word)
        total += VALUE_OF[word]
    return total


# hand-written expectations, so that a slip in the tables above cannot hide
EXPECTED = {
    1: "один", 2: "два", 5: "пять", 9: "девять",
    10: "десять", 11: "одиннадцать", 12: "двенадцать", 13: "тринадцать",
    14: "четырнадцать", 15: "пятнадцать", 16: "шестнадцать", 17: "семнадцать",
    18: "восемнадцать", 19: "девятнадцать",
    20: "двадцать", 21: "двадцать один", 30: "тридцать", 31: "тридцать один",
    40: "сорок", 50: "пятьдесят", 60: "шестьдесят", 70: "семьдесят",
    80: "восемьдесят", 90: "девяносто", 99: "девяносто девять",
    100: "сто", 101: "сто один", 110: "сто десять", 111: "сто одиннадцать",
    120: "сто двадцать", 199: "сто девяносто девять",
    200: "двести", 300: "триста", 400: "четыреста", 500: "пятьсот",
    600: "шестьсот", 700: "семьсот", 800: "восемьсот", 900: "девятьсот",
    999: "девятьсот девяносто девять",
}


def self_test():
    """The two derivations have to agree with each other and with the hand table."""
    problems = []
    seen = {}
    for n in range(1, 1000):
        words = spell(n)
        if parse(words) != n:
            problems.append(f"round trip failed for {n}: {words!r}")
        if words in seen:
            problems.append(f"{n} and {seen[words]} spell the same: {words!r}")
        seen[words] = n
    for n, want in EXPECTED.items():
        got = spell(n)
        if got != want:
            problems.append(f"spell({n}) = {got!r}, expected {want!r}")
    return problems


# --------------------------------------------------------------------------
# the dataset walk
# --------------------------------------------------------------------------

# The types whose `text` is a number spelled out in Russian words. For those the
# answer is the number in digits and the text has to be its spelling; for every other
# type the text is the string that is drawn, i.e. the answer itself.
#
# The rule is per type and not "the answer looks like a number": the symbol families
# draw digits as well (their charset contains 0-9), and the BotFilter captcha draws
# five-digit numbers that are not spelled out at all.
NUMBER_WORD_TYPES = {
    "GalleryCaptcha/ru-numberword",
    "GalleryCaptcha/ru-numberword-caption",
    "LimboFilter/map",
    "LimboFilter/framed3x3",
    "LimboFilter/framed2x2",
}

# The types whose `text` is the drawn string while the `answer` is that string with the
# letters reversed - the plugin asks the player to reverse the code it shows. This is one
# more *known* case of text != answer; the check re-derives the answer from the text
# instead of assuming that the two are equal.
REVERSED_TEXT_TYPES = {
    "LagBug/XProtect/reverse",
}


def type_dirs(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        parts = os.path.relpath(dirpath, root).split(os.sep)
        if "real_shots" in parts:
            continue
        if "labels.jsonl" in filenames:
            out.append(dirpath)
    return sorted(out)


def check(root):
    problems = self_test()
    if problems:
        print("!! the checker's own spelling is broken:")
        for p in problems[:20]:
            print("   ", p)
        return 1

    label_mismatch = 0
    roi_problems = 0
    samples = 0
    with_roi = 0
    per_type = {}

    for d in type_dirs(root):
        rel = os.path.relpath(d, root).replace(os.sep, "/")
        rows = [json.loads(l) for l in open(os.path.join(d, "labels.jsonl"), encoding="utf-8")]
        t_bad = 0
        t_roi = 0
        t_min = None
        t_max = 0
        for row in rows:
            samples += 1
            answer = row.get("answer")
            text = row.get("text")
            if answer is None or text is None:
                continue

            if rel in NUMBER_WORD_TYPES:
                n = int(answer)
                want = spell(n)
                if text != want:
                    t_bad += 1
                    label_mismatch += 1
                    print(f"!! {rel}/{row['file']}: answer {answer} -> text {text!r}, expected {want!r}")
            elif rel in REVERSED_TEXT_TYPES:
                # the drawn code is the text; the player answers with the code reversed
                if answer != text[::-1]:
                    t_bad += 1
                    label_mismatch += 1
                    print(f"!! {rel}/{row['file']}: answer {answer!r} is not the reverse of text {text!r}")
            else:
                # not a spelled-out number: the drawn string is the answer
                if text != answer:
                    t_bad += 1
                    label_mismatch += 1
                    print(f"!! {rel}/{row['file']}: text {text!r} != answer {answer!r}")

            roi = row.get("roi")
            if not roi:
                continue
            t_roi += 1
            with_roi += 1
            x, y, w, h = roi
            if w <= 0 or h <= 0:
                roi_problems += 1
                print(f"!! {rel}/{row['file']}: empty roi {roi}")
                continue
            if x < 0 or y < 0 or x + w > row["width"] or y + h > row["height"]:
                roi_problems += 1
                print(f"!! {rel}/{row['file']}: roi {roi} outside {row['width']}x{row['height']}")
                continue
            if Image is None:
                continue
            png = os.path.join(d, row["file"])
            with Image.open(png) as im:
                crop = im.convert("RGB").crop((x, y, x + w, y + h))
                colors = crop.getcolors(maxcolors=1 << 22)
            n_colors = len(colors)
            if n_colors <= 1:
                roi_problems += 1
                print(f"!! {rel}/{row['file']}: roi {roi} is a single colour")
            t_min = n_colors if t_min is None else min(t_min, n_colors)
            t_max = max(t_max, n_colors)

        per_type[rel] = (len(rows), t_bad, t_roi, t_min, t_max)

    print()
    print(f"{'type':<40} {'n':>5} {'label bad':>10} {'with roi':>9} {'roi colours':>16}")
    print("-" * 84)
    for rel, (n, bad, r, t_min, t_max) in per_type.items():
        band = f"{t_min}-{t_max}" if t_min is not None else "-"
        print(f"{rel:<40} {n:>5} {bad:>10} {r:>9} {band:>16}")
    print("-" * 84)
    print(f"{samples} samples, {with_roi} with a roi")
    print(f"label mismatches: {label_mismatch}")
    print(f"roi problems:     {roi_problems}")
    ok = label_mismatch == 0 and roi_problems == 0
    print("RESULT:", "OK" if ok else "<-- CHECK")
    return 0 if ok else 1


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="check_labels_and_roi.py",
        description="Re-derive the labels of a generated dataset and check that every "
                    "roi() band is inside the canvas and is not a flat colour.")
    ap.add_argument("root", nargs="?", default=os.path.join(REPO, "dataset", "out_ru"),
                    help="dataset root (default: <repo>/dataset/out_ru)")
    return ap.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    sys.exit(check(args.root))
