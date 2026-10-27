import json
import os
import sys


def main():
    root = sys.argv[1]
    wanted = sys.argv[2:]
    print(f"{'type':<40} {'n':>4} {'roi':>5} {'full':>5} {'median band':>20}")
    print("-" * 78)
    for dirpath, dirnames, filenames in os.walk(root):
        if "real_shots" in os.path.relpath(dirpath, root).split(os.sep):
            continue
        if "labels.jsonl" not in filenames:
            continue
        rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if wanted and not any(w in rel for w in wanted):
            continue
        rows = [json.loads(l) for l in open(os.path.join(dirpath, "labels.jsonl"), encoding="utf-8")]
        bands = [r["roi"] for r in rows if r.get("roi")]
        full = sum(1 for x, y, w, h in bands
                   if x == 0 and y == 0 and w == rows[0]["width"] and h == rows[0]["height"])
        areas = sorted(w * h for x, y, w, h in bands)
        med = areas[len(areas) // 2] if areas else 0
        print(f"{rel:<40} {len(rows):>4} {len(bands):>5} {full:>5} {med:>20}")


if __name__ == "__main__":
    main()
