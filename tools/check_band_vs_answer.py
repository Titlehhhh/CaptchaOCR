"""Is the string inside the text band the same as the `answer` field?

    python tools/check_band_vs_answer.py dataset/out_ru

The `text` field of a sample is the literal string that is drawn in the picture, and the
`answer` field is what the player has to type.  For most types they are the same.  For
the number-word family they are not, on purpose: the map shows the number in Russian
words and the player answers with the digits.  A recogniser has to be trained on the
`text`, and a lexicon turns the words into the digits - so a mismatch is not a bug, but
it does have to be *known*, because a trainer that compares the prediction with the
`answer` of such a type will score zero.

The types with no band at all are reported as well: the band is where the recogniser
looks, and a type without one cannot be a recogniser's training target.
"""

import json
import os
import sys


def main():
    root = sys.argv[1]
    print(f"{'type':<40} {'n':>4} {'band':>5} {'text==answer':>13}  note")
    print("-" * 96)
    for dirpath, dirnames, filenames in os.walk(root):
        if "real_shots" in os.path.relpath(dirpath, root).split(os.sep):
            continue
        if "labels.jsonl" not in filenames:
            continue
        rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
        rows = [json.loads(l) for l in open(os.path.join(dirpath, "labels.jsonl"), encoding="utf-8")]
        n = len(rows)
        with_band = sum(1 for r in rows if r.get("roi"))
        same = sum(1 for r in rows if r.get("text") == r.get("answer"))
        if with_band == 0:
            note = "no band - not a recogniser's training target"
        elif same == n:
            note = "the band holds the answer"
        else:
            ex = next(r for r in rows if r.get("text") != r.get("answer"))
            note = f"the band holds the TEXT, the answer is the value: {ex['text']!r} -> {ex['answer']!r}"
        print(f"{rel:<40} {n:>4} {with_band:>5} {same:>13}  {note}")


if __name__ == "__main__":
    main()
