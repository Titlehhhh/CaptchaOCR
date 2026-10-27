"""The command line of the Parquet export.

    python tools/export_parquet.py --dry-run        # print the plan, write nothing
    python tools/export_parquet.py --out build/parquet
    python tools/export_parquet.py --out build/parquet --upload
    python tools/export_parquet.py --out build/parquet --verify
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from .common import human_bytes, log, warn
except ImportError:  # run as a plain script
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
    from tools.parquet_export.common import human_bytes, log, warn
from .index import DatasetIndex, Sample, TREES, build_index
from .shards import plan_shards, shard_name, write_shard
from .hub import (EXIT_ERROR, EXIT_OK, api_for, resolve_token, upload, verify_remote)
from .card import build_readme

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "dataset"
DEFAULT_OUT_DIR = REPO_ROOT / "build" / "parquet"
DEFAULT_REPO_ID = "Titlehhhh/captchaocr-dataset"

#: Default target size of one Parquet shard (250 MiB).
DEFAULT_TARGET_MB = 250

#: Prefix inside the Hub repository where the shards are uploaded.
DATA_PREFIX = "data"

EXIT_NO_AUTH = 2


@dataclass
class ExportResult:
    index: DatasetIndex
    shards: list[tuple[Path, int]]

    @property
    def total_bytes(self) -> int:
        return sum(size for _, size in self.shards)


def print_plan(index: DatasetIndex, shards: list[list[Sample]], target_bytes: int,
               out_dir: Path, data_dir: Path) -> None:
    total_rows = sum(info.samples for info in index.types.values())
    log("=== CaptchaOCR Parquet export plan ===")
    log(f"dataset root:          {data_dir}")
    log(f"target shard size:     {target_bytes:,} B ({human_bytes(target_bytes)})")
    log(f"types:                 {len(index.types)}")
    log(f"samples:               {total_rows:,}")
    log(f"PNG bytes:             {index.total_png_bytes:,} B "
        f"({human_bytes(index.total_png_bytes)})")
    log(f"estimated Parquet:     {index.estimated_parquet_bytes:,} B "
        f"({human_bytes(index.estimated_parquet_bytes)})")
    log(f"shards:                {len(shards)}")
    log(f"output:                {out_dir}")
    log("")
    log("per tree:")
    for tree in TREES:
        if tree not in index.types_per_tree:
            continue
        log(f"  {tree:<8} {index.types_per_tree[tree]:>2} types  "
            f"{index.samples_per_tree.get(tree, 0):>7,} samples  "
            f"{index.bytes_per_tree.get(tree, 0):>13,} B "
            f"({human_bytes(index.bytes_per_tree.get(tree, 0))})")
    log("")
    log("per type:")
    for type_id in sorted(index.types):
        info = index.types[type_id]
        log(f"  {type_id:<55} {info.samples:>7,} samples  "
            f"{info.png_bytes:>12,} B  roi {info.roi_rows:>6,}/{info.samples:<6,}  "
            f"text!=answer {info.text_ne_answer:>6,}")
    if index.missing_png:
        log("")
        warn(f"{len(index.missing_png)} label rows reference a missing PNG, "
             f"e.g. {index.missing_png[:3]}")


def export(data_dir: Path, out_dir: Path, target_bytes: int,
           quiet: bool = False) -> ExportResult:
    """Build the index, write the shards and the README.  Returns the result."""
    index = build_index(data_dir)
    if not index.samples:
        raise RuntimeError(f"no samples found under {data_dir}")
    if index.missing_png:
        raise RuntimeError(
            f"{len(index.missing_png)} label rows reference a missing PNG "
            f"(e.g. {index.missing_png[:5]})")
    shards = plan_shards(index.samples, target_bytes)
    total = len(shards)
    data_out = out_dir / DATA_PREFIX
    data_out.mkdir(parents=True, exist_ok=True)

    # Scratch output only: remove shards from a previous export in this directory.
    for old in sorted(data_out.glob("*.parquet")):
        old.unlink()
        if not quiet:
            log(f"  removed old scratch shard: {old.name}")

    written: list[tuple[Path, int]] = []
    rows_done = 0
    total_rows = len(index.samples)
    for number, chunk in enumerate(shards):
        path = data_out / shard_name(number, total)
        size = write_shard(path, chunk)
        written.append((path, size))
        rows_done += len(chunk)
        log(f"  shard {number + 1}/{total}: {path.name} — {len(chunk):,} rows, "
            f"{size:,} B ({human_bytes(size)})  [{rows_done:,}/{total_rows:,}]")

    readme = build_readme(index, written, regeneration_date="2026-10-24")
    (out_dir / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    log("")
    log(f"wrote {len(written)} shards, {total_rows:,} rows, "
        f"{sum(size for _, size in written):,} B "
        f"({human_bytes(sum(size for _, size in written))})")
    log(f"wrote {out_dir / 'README.md'}")
    return ExportResult(index=index, shards=written)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="export_parquet.py",
        description="Export the CaptchaOCR PNG dataset (dataset/out + dataset/out_ru) "
                    "to Parquet shards and publish them to the Hugging Face dataset "
                    "repository Titlehhhh/captchaocr-dataset.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="print the export plan (samples, shards, bytes, per-tree "
                           "breakdown, target shard size) and exit; writes nothing")
    mode.add_argument("--upload", action="store_true",
                      help="export if needed, upload the shards and README, then delete "
                           "the old loose-PNG tree under data/out and data/out_ru")
    mode.add_argument("--verify", action="store_true",
                      help="list the remote tree and verify that only Parquet shards "
                           "remain; exits non-zero on a mismatch")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, metavar="DIR",
                        help=f"output directory (default: {DEFAULT_OUT_DIR}); shards go "
                             f"to <DIR>/data, the card to <DIR>/README.md")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, metavar="DIR",
                        help=f"dataset tree root (default: {DEFAULT_DATA_DIR})")
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID,
                        help=f"destination dataset repository (default: {DEFAULT_REPO_ID})")
    parser.add_argument("--target-mb", type=int, default=DEFAULT_TARGET_MB, metavar="N",
                        help=f"target shard size in MiB (default: {DEFAULT_TARGET_MB})")
    parser.add_argument("--token", default=None,
                        help="HF token (default: $HF_TOKEN, the stored CLI token, or "
                             ".hf-cache/token)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_dir = args.data_dir.resolve()
    out_dir = args.out.resolve()
    target_bytes = max(1, int(args.target_mb)) * 1024 * 1024

    if args.dry_run:
        index = build_index(data_dir)
        if not index.samples:
            raise RuntimeError(f"no samples found under {data_dir}")
        shards = plan_shards(index.samples, target_bytes)
        print_plan(index, shards, target_bytes, out_dir, data_dir)
        if index.missing_png:
            log("")
            log("DRY RUN: nothing was written.")
            return EXIT_ERROR
        log("")
        log("DRY RUN: nothing was written, nothing was uploaded, nothing was deleted.")
        return EXIT_OK

    if args.verify:
        token = resolve_token(args.token)
        if not token:
            warn("no HF token found; trying anonymous access (public repository)")
        api = api_for(token)
        return verify_remote(api, args.repo_id, out_dir)

    if args.upload:
        token = resolve_token(args.token)
        if not token:
            warn("no HF token found: set HF_TOKEN or pass --token")
            return EXIT_NO_AUTH
        api = api_for(token)
        return upload(api, args.repo_id, out_dir, DEFAULT_DATA_DIR,
                      DEFAULT_TARGET_MB * 1024 * 1024, export)

    export(data_dir, out_dir, target_bytes)
    return EXIT_OK


def run() -> int:
    try:
        return main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        warn(f"{type(exc).__name__}: {exc}")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(run())
