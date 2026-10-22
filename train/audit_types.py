"""Audit the dataset types: what survives the band filter and the charset filter.

    .venv-gpu\\Scripts\\python.exe train\\audit_types.py
    .venv-gpu\\Scripts\\python.exe train\\audit_types.py --json

One line per type: samples, how many rows carry a text band, whether the label
survives the charset, the length range of the drawn text and the number of
distinct answers. The last column is the leak: a type with one distinct answer
teaches the model a constant.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from captcha_crnn import CHARSET, CYRILLIC, build_encoder, find_types, read_labels

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIRS = [os.path.join(REPO, "dataset", "out"), os.path.join(REPO, "dataset", "out_ru")]


def audit(charset_name="latin"):
    cs = build_encoder(CHARSET if charset_name == "latin" else CYRILLIC)
    rows_out = []
    for type_id, directory, root in find_types(OUT_DIRS):
        rows = read_labels(directory)
        n = len(rows)
        with_roi = sum(1 for r in rows if r.get("roi"))
        texts = [r.get("text") or r.get("answer") or "" for r in rows]
        encodable = sum(1 for t in texts if cs.encode(t))
        lens = [len(t) for t in texts]
        answers = {r.get("answer", "") for r in rows}
        text_eq_answer = sum(1 for r in rows
                             if (r.get("text") or "") == (r.get("answer") or ""))
        rows_out.append({
            "type": type_id,
            "tree": os.path.basename(root),
            "n": n,
            "with_roi": with_roi,
            "encodable": encodable,
            "len_min": min(lens) if lens else 0,
            "len_max": max(lens) if lens else 0,
            "distinct_answers": len(answers),
            "text_eq_answer": text_eq_answer,
            "has_band": with_roi > 0,
            "in_charset": encodable == n and n > 0,
            "text_is_answer": text_eq_answer == n and n > 0,
        })
    return rows_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--charset", choices=["latin", "cyrillic"], default="latin")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    data = audit(args.charset)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
        return 0
    print(f"{'type':52s} {'tree':7s} {'n':>4s} {'roi':>4s} {'enc':>4s} "
          f"{'len':>7s} {'uniq':>5s} {'t==a':>5s}")
    for d in data:
        print(f"{d['type']:52s} {d['tree']:7s} {d['n']:4d} {d['with_roi']:4d} "
              f"{d['encodable']:4d} {str(d['len_min']) + '-' + str(d['len_max']):>7s} "
              f"{d['distinct_answers']:5d} {d['text_eq_answer']:5d}")
    keep = [d for d in data if d["has_band"] and d["in_charset"] and d["text_is_answer"]]
    print(f"\n{len(data)} types total; {len(keep)} have a band, a Latin label and text==answer:")
    for d in keep:
        print(f"  {d['type']:52s} {d['n']:4d}  len {d['len_min']}-{d['len_max']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
