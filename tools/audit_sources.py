import json
import os
import sys


def main():
    root = sys.argv[1]
    for dirpath, dirnames, filenames in os.walk(root):
        if "real_shots" in os.path.relpath(dirpath, root).split(os.sep):
            continue
        if "labels.jsonl" not in filenames:
            continue
        rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
        rows = [json.loads(l) for l in open(os.path.join(dirpath, "labels.jsonl"), encoding="utf-8")]
        sources = {}
        for r in rows:
            sources.setdefault(r.get("source"), 0)
            sources[r.get("source")] += 1
        for src, n in sources.items():
            print(f"{rel}  ({n})\n    {src}")


if __name__ == "__main__":
    main()
