#!/usr/bin/env python3

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REPO_ID = "Titlehhhh/captchaocr-dataset"
DEFAULT_DEST = os.path.join("dataset", "full")
LOCAL_CACHE = os.path.join(REPO_ROOT, ".hf-cache")
DATASET_TREES = ("out", "out_ru")


def find_types():
    types = []
    for tree in DATASET_TREES:
        base = os.path.join(REPO_ROOT, "dataset", tree)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, filenames in os.walk(base):
            if "labels.jsonl" not in filenames:
                continue
            rel = os.path.relpath(dirpath, base).replace(os.sep, "/")
            pngs = sorted(f for f in filenames if f.lower().endswith(".png"))
            size = 0
            for f in pngs:
                p = os.path.join(dirpath, f)
                if os.path.isfile(p):
                    size += os.path.getsize(p)
            rows = 0
            try:
                with open(os.path.join(dirpath, "labels.jsonl"), encoding="utf-8") as fh:
                    rows = sum(1 for line in fh if line.strip())
            except OSError:
                pass
            plugin = ""
            captcha = ""
            try:
                with open(os.path.join(dirpath, "labels.jsonl"), encoding="utf-8") as fh:
                    import json

                    for line in fh:
                        if line.strip():
                            row = json.loads(line)
                            plugin = row.get("plugin", "")
                            captcha = row.get("captcha", "")
                            break
            except (OSError, ValueError):
                pass
            types.append(
                {
                    "tree": tree,
                    "plugin": plugin,
                    "captcha": captcha,
                    "dir": rel,
                    "files": len(pngs),
                    "bytes": size,
                    "rows": rows,
                }
            )
    types.sort(key=lambda t: (t["tree"], t["dir"]))
    return types


def type_key(t):
    return (t["plugin"] + "/" + t["captcha"]).strip("/")


def match_types(types, wanted):
    selected = []
    unknown = []
    for w in wanted:
        w = w.strip().strip("/")
        if not w:
            continue
        low = w.lower()
        hits = [
            t
            for t in types
            if low in (type_key(t).lower(), t["captcha"].lower(), t["dir"].lower())
            or low in t["dir"].lower().split("/")
        ]
        if hits:
            for h in hits:
                if h not in selected:
                    selected.append(h)
        else:
            unknown.append(w)
    return selected, unknown


def patterns_for(types):
    pats = []
    for t in types:
        rel = t["dir"]
        pats.append(rel + "/**")
        pats.append("**/" + rel + "/**")
        pats.append("data/%s/%s/**" % (t["tree"], rel))
        pats.append(rel)
    return sorted(set(pats))


def resolve_cache_dir(explicit):
    if explicit:
        return os.path.abspath(explicit), "--cache-dir"
    env = os.environ.get("HF_HUB_CACHE")
    if env:
        return os.path.abspath(env), "HF_HUB_CACHE"
    home = os.environ.get("HF_HOME")
    if home:
        return os.path.abspath(os.path.join(home, "hub")), "HF_HOME"
    standard = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
    if os.access(standard, os.W_OK):
        return os.path.abspath(standard), "standard hub cache"
    return LOCAL_CACHE, "standard hub cache is read-only -> .hf-cache/"


def human(n):
    return "%.2f MB" % (n / 1048576.0)


def print_plan(args, types, selected, unknown, cache_dir, cache_why):
    dest = os.path.abspath(args.dest)
    print("CaptchaOCR dataset fetch - plan")
    print("  repo        : %s (dataset, revision %s)" % (args.repo_id, args.revision))
    print("  destination : %s" % dest)
    print("  cache       : %s  [%s]" % (cache_dir, cache_why))
    print("  types       : %d of %d known" % (len(selected), len(types)))
    if unknown:
        print("  UNKNOWN     : %s (no such type in the local labels)" % ", ".join(unknown))
    print()
    total_files = 0
    total_bytes = 0
    for t in selected:
        print(
            "  %-46s %4d png  %8s" % (type_key(t), t["files"], human(t["bytes"]))
        )
        total_files += t["files"]
        total_bytes += t["bytes"]
    print()
    print("  total       : %d files, %s" % (total_files, human(total_bytes)))
    if args.types:
        print()
        print("  allow_patterns:")
        for p in patterns_for(selected):
            print("    %s" % p)
    print()
    print("  dry run: nothing was downloaded, no network request was made.")


def do_download(args, types, selected, unknown, cache_dir):
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print(
            "huggingface_hub is not installed. Install it first:\n"
            "    pip install -U huggingface_hub",
            file=sys.stderr,
        )
        return 2

    dest = os.path.abspath(args.dest)
    os.makedirs(dest, exist_ok=True)

    kwargs = dict(
        repo_id=args.repo_id,
        repo_type="dataset",
        revision=args.revision,
        local_dir=dest,
        cache_dir=cache_dir,
    )
    if selected:
        kwargs["allow_patterns"] = patterns_for(selected)
    kwargs["ignore_patterns"] = ["**/real_shots/**"]

    print("Downloading %s -> %s" % (args.repo_id, dest))
    if kwargs.get("allow_patterns"):
        print("  only the selected types (%d)" % len(selected))
    path = snapshot_download(**kwargs)
    print("done: %s" % path)

    lifted = flatten_data_dir(dest)
    if lifted:
        print("  lifted out of data/: %s" % ", ".join(lifted))
    report(dest)
    return 0


def merge_tree(src, dst):
    moved = 0
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s) and os.path.isdir(d):
            moved += merge_tree(s, d)
            continue
        if os.path.isdir(s):
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.move(s, d)
        else:
            if os.path.exists(d):
                if os.path.getsize(d) == os.path.getsize(s):
                    os.remove(s)
                    continue
                os.remove(d)
            shutil.move(s, d)
        moved += 1
    return moved


def flatten_data_dir(dest):
    src = os.path.join(dest, "data")
    if not os.path.isdir(src):
        return []
    lifted = []
    for name in sorted(os.listdir(src)):
        s = os.path.join(src, name)
        d = os.path.join(dest, name)
        if os.path.isdir(s) and os.path.isdir(d):
            merge_tree(s, d)
        else:
            if os.path.exists(d):
                if os.path.isdir(d):
                    shutil.rmtree(d)
                else:
                    os.remove(d)
            shutil.move(s, d)
        lifted.append(name)
    shutil.rmtree(src, ignore_errors=True)
    return lifted


def report(dest):
    total_files = 0
    total_bytes = 0
    per_tree = {}
    for tree in DATASET_TREES:
        base = os.path.join(dest, tree)
        if not os.path.isdir(base):
            continue
        n = 0
        b = 0
        types = 0
        for dirpath, _dirs, files in os.walk(base):
            if "labels.jsonl" in files:
                types += 1
            for f in files:
                p = os.path.join(dirpath, f)
                if os.path.isfile(p):
                    n += 1
                    b += os.path.getsize(p)
        if n:
            per_tree[tree] = (n, b, types)
            total_files += n
            total_bytes += b
    print()
    for tree, (n, b, types) in sorted(per_tree.items()):
        print("  %-8s %5d files in %2d types, %8s" % (tree, n, types, human(b)))
    print("  total    %5d files, %8s" % (total_files, human(total_bytes)))


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="fetch_dataset.py",
        description="Download the full CaptchaOCR dataset from Hugging Face.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python tools/fetch_dataset.py\n"
            "  python tools/fetch_dataset.py --dry-run\n"
            "  python tools/fetch_dataset.py --types haq/mapcha/map GalleryCaptcha/ru-symbols\n"
        ),
    )
    ap.add_argument("--repo-id", default=DEFAULT_REPO_ID, help="HF dataset repo id")
    ap.add_argument(
        "--dest",
        default=os.path.join(REPO_ROOT, DEFAULT_DEST),
        help="destination directory (default: dataset/full)",
    )
    ap.add_argument(
        "--types",
        nargs="+",
        default=[],
        metavar="TYPE",
        help="download only these types, e.g. haq/mapcha/map or GalleryCaptcha/ru-symbols",
    )
    ap.add_argument("--revision", default="main", help="repo revision (default: main)")
    ap.add_argument("--cache-dir", default=None, help="hub cache directory")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print the plan and exit without downloading (no network access)",
    )
    args = ap.parse_args(argv)

    types = find_types()
    if not types:
        print(
            "No dataset types found under dataset/ - the labels.jsonl files are "
            "missing from this checkout.",
            file=sys.stderr,
        )
        return 2

    selected = types
    unknown = []
    if args.types:
        selected, unknown = match_types(types, args.types)
        if not selected:
            print(
                "No known type matches %s. Known types:\n  %s"
                % (", ".join(args.types), "\n  ".join(type_key(t) for t in types)),
                file=sys.stderr,
            )
            return 2

    cache_dir, cache_why = resolve_cache_dir(args.cache_dir)

    if args.dry_run:
        print_plan(args, types, selected, unknown, cache_dir, cache_why)
        return 0

    return do_download(args, types, selected, unknown, cache_dir)


if __name__ == "__main__":
    sys.exit(main())
