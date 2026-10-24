"""Export the generated CaptchaOCR PNG dataset to Parquet shards and publish them.

The dataset tree lives in ``dataset/out`` (12 types) and ``dataset/out_ru``
(8 types); every type directory holds ``NNN.png`` files plus one
``labels.jsonl`` row per image.  This script turns that loose-PNG layout into a
small number of Parquet shards -- one row per sample, with the raw PNG bytes in
the ``image`` column -- so the Hugging Face repository can be loaded with
``datasets.load_dataset`` or with plain ``pyarrow``.

Modes::

    python tools/export_parquet.py --dry-run        # print the plan, write nothing
    python tools/export_parquet.py --out build/parquet
    python tools/export_parquet.py --out build/parquet --upload
    python tools/export_parquet.py --out build/parquet --verify

``--upload`` uploads ``<out>/data/*.parquet`` under ``data/`` and
``<out>/README.md`` to the repository root, then deletes every remaining file
under ``data/out/`` and ``data/out_ru/`` (the old loose PNG tree) in chunks of
1000 paths per commit.  It never deletes ``README.md``,
``dataset_inventory.json``, ``LICENSE*``, ``.gitattributes`` or anything
outside those two prefixes.

Only ``pyarrow`` is required to build the shards -- not ``datasets``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DEFAULT_DATA_DIR = REPO_ROOT / "dataset"
DEFAULT_OUT_DIR = REPO_ROOT / "build" / "parquet"
DEFAULT_REPO_ID = "Titlehhhh/captchaocr-dataset"

#: Trees of the local dataset, in the order samples are written.
TREES = ("out", "out_ru")

#: Prefix inside the Hub repository where the shards are uploaded.
DATA_PREFIX = "data"

#: Old loose-PNG locations on the Hub -- the only paths ``--upload`` deletes.
OLD_TREE_PREFIXES = ("data/out/", "data/out_ru/")

#: Default target size of one Parquet shard (250 MiB).
DEFAULT_TARGET_MB = 250

#: Rough per-row overhead (label strings, page indexes) used only for planning.
ROW_OVERHEAD_BYTES = 384

#: Rows written per row group / per in-memory batch.
ROW_GROUP_SIZE = 2048

#: Delete protocol (see the task contract).
DELETE_CHUNK_PATHS = 1000
DELETE_NUM_THREADS = 24
UPLOAD_NUM_THREADS = 8
MAX_RETRIES = 5
RETRY_SLEEP = 8.0

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NO_AUTH = 2

PROTECTED_NAMES = frozenset({"README.md", "dataset_inventory.json", ".gitattributes"})
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


# -------------------------------------------------------------------------------------
# Small helpers
# -------------------------------------------------------------------------------------

def log(message: str = "") -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr, flush=True)


def human_bytes(size: float) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024.0 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{value:.1f} TiB"


def is_old_tree_path(path: str) -> bool:
    """True for deletable paths under the retired ``data/out`` / ``data/out_ru`` trees."""
    if not path.startswith(OLD_TREE_PREFIXES):
        return False
    return not is_protected_path(path)


def is_protected_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name in PROTECTED_NAMES or name.startswith("LICENSE")


def is_remote_folder(entry) -> bool:
    """Directory detection that works with huggingface_hub >= 1.x and older."""
    if type(entry).__name__ == "RepoFolder":
        return True
    kind = getattr(entry, "type", None)
    if isinstance(kind, str) and kind.lower() in ("directory", "dir", "folder"):
        return True
    return getattr(entry, "blob_id", None) is None and not hasattr(entry, "size")


# -------------------------------------------------------------------------------------
# Dataset index
# -------------------------------------------------------------------------------------

@dataclass
class Sample:
    tree: str
    type_id: str
    path: Path
    file: str
    plugin: str
    captcha: str
    answer: str
    text: str | None
    prompt: str | None
    roi: list[int] | None
    width: int
    height: int
    source: str
    png_bytes: int

    @property
    def estimated_bytes(self) -> int:
        return self.png_bytes + ROW_OVERHEAD_BYTES


@dataclass
class TypeInfo:
    tree: str
    type_id: str
    plugin: str
    captcha: str
    labels_path: Path
    samples: int = 0
    png_bytes: int = 0
    roi_rows: int = 0
    text_ne_answer: int = 0


@dataclass
class DatasetIndex:
    samples: list[Sample] = field(default_factory=list)
    types: dict[str, TypeInfo] = field(default_factory=dict)
    missing_png: list[str] = field(default_factory=list)
    samples_per_tree: dict[str, int] = field(default_factory=dict)
    bytes_per_tree: dict[str, int] = field(default_factory=dict)
    types_per_tree: dict[str, int] = field(default_factory=dict)

    @property
    def total_png_bytes(self) -> int:
        return sum(s.png_bytes for s in self.samples)

    @property
    def estimated_parquet_bytes(self) -> int:
        return sum(s.estimated_bytes for s in self.samples)


def find_label_files(data_dir: Path) -> list[tuple[str, Path]]:
    """All ``labels.jsonl`` under the known trees, in deterministic order.

    ``real_shots`` directories are reference screenshots and are never part of
    the published dataset; they are skipped explicitly.
    """
    found: list[tuple[str, Path]] = []
    for tree in TREES:
        base = data_dir / tree
        if not base.is_dir():
            warn(f"tree not found: {base}")
            continue
        for labels in sorted(base.rglob("labels.jsonl")):
            if "real_shots" in labels.parts:
                continue
            found.append((tree, labels))
    return found


def build_index(data_dir: Path) -> DatasetIndex:
    """Read every ``labels.jsonl`` and stat every referenced PNG.

    Read-only: this function never creates or writes a file.
    """
    index = DatasetIndex()
    for tree, labels_path in find_label_files(data_dir):
        type_id = labels_path.parent.relative_to(data_dir).as_posix()
        if not type_id.startswith(tree + "/"):
            type_id = f"{tree}/{type_id}"
        info = TypeInfo(tree=tree, type_id=type_id, plugin="", captcha="",
                        labels_path=labels_path)
        with open(labels_path, encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                png_path = labels_path.parent / row["file"]
                try:
                    png_bytes = png_path.stat().st_size
                except OSError:
                    index.missing_png.append(f"{type_id}/{row['file']}")
                    png_bytes = 0
                roi = row.get("roi")
                if roi is None:
                    roi_value = None
                else:
                    roi_value = [int(v) for v in roi]
                sample = Sample(
                    tree=tree,
                    type_id=type_id,
                    path=png_path,
                    file=str(row["file"]),
                    plugin=str(row["plugin"]),
                    captcha=str(row["captcha"]),
                    answer="" if row.get("answer") is None else str(row["answer"]),
                    text=None if row.get("text") is None else str(row["text"]),
                    prompt=None if row.get("prompt") is None else str(row["prompt"]),
                    roi=roi_value,
                    width=int(row["width"]),
                    height=int(row["height"]),
                    source="" if row.get("source") is None else str(row["source"]),
                    png_bytes=png_bytes,
                )
                if not info.plugin:
                    info.plugin = sample.plugin
                    info.captcha = sample.captcha
                info.samples += 1
                info.png_bytes += png_bytes
                if roi_value is not None:
                    info.roi_rows += 1
                if sample.text is not None and sample.answer is not None \
                        and sample.text != sample.answer:
                    info.text_ne_answer += 1
                index.samples.append(sample)
        if info.samples == 0:
            warn(f"empty labels file, skipped: {type_id}")
            continue
        index.types[type_id] = info
        index.samples_per_tree[tree] = index.samples_per_tree.get(tree, 0) + info.samples
        index.bytes_per_tree[tree] = index.bytes_per_tree.get(tree, 0) + info.png_bytes
        index.types_per_tree[tree] = index.types_per_tree.get(tree, 0) + 1
    return index


# -------------------------------------------------------------------------------------
# Shard planning
# -------------------------------------------------------------------------------------

def plan_shards(samples: list[Sample], target_bytes: int) -> list[list[Sample]]:
    """Greedily pack samples, in order, into shards of about ``target_bytes``."""
    target = max(1, int(target_bytes))
    shards: list[list[Sample]] = []
    current: list[Sample] = []
    current_bytes = 0
    for sample in samples:
        estimated = sample.estimated_bytes
        if current and current_bytes + estimated > target:
            shards.append(current)
            current = []
            current_bytes = 0
        current.append(sample)
        current_bytes += estimated
    if current:
        shards.append(current)
    return shards


def shard_name(index: int, total: int) -> str:
    return f"train-{index:05d}-of-{total:05d}.parquet"


# -------------------------------------------------------------------------------------
# Parquet schema and writing
# -------------------------------------------------------------------------------------

def parquet_schema():
    import pyarrow as pa

    return pa.schema([
        pa.field("image", pa.binary(), nullable=False),
        pa.field("file", pa.string(), nullable=False),
        pa.field("type_id", pa.string(), nullable=False),
        pa.field("plugin", pa.string(), nullable=False),
        pa.field("captcha", pa.string(), nullable=False),
        pa.field("answer", pa.string(), nullable=False),
        pa.field("text", pa.string(), nullable=True),
        pa.field("prompt", pa.string(), nullable=True),
        pa.field("roi", pa.list_(pa.int32()), nullable=True),
        pa.field("width", pa.int32(), nullable=False),
        pa.field("height", pa.int32(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("tree", pa.string(), nullable=False),
    ])


def build_table(samples: list[Sample]):
    """Build one Arrow table from a batch of samples (no inference surprises)."""
    import pyarrow as pa

    schema = parquet_schema()
    images = []
    for sample in samples:
        payload = sample.path.read_bytes()
        if not payload.startswith(PNG_MAGIC):
            raise RuntimeError(f"not a PNG: {sample.path}")
        images.append(payload)
    arrays = [
        pa.array(images, type=pa.binary()),
        pa.array([s.file for s in samples], type=pa.string()),
        pa.array([s.type_id for s in samples], type=pa.string()),
        pa.array([s.plugin for s in samples], type=pa.string()),
        pa.array([s.captcha for s in samples], type=pa.string()),
        pa.array([s.answer for s in samples], type=pa.string()),
        pa.array([s.text for s in samples], type=pa.string()),
        pa.array([s.prompt for s in samples], type=pa.string()),
        pa.array([s.roi for s in samples], type=pa.list_(pa.int32())),
        pa.array([s.width for s in samples], type=pa.int32()),
        pa.array([s.height for s in samples], type=pa.int32()),
        pa.array([s.source for s in samples], type=pa.string()),
        pa.array([s.tree for s in samples], type=pa.string()),
    ]
    return pa.Table.from_arrays(arrays, schema=schema)


def write_shard(path: Path, samples: list[Sample]) -> int:
    """Write one Parquet shard and return its byte size on disk."""
    import pyarrow.parquet as pq

    with pq.ParquetWriter(
        path,
        parquet_schema(),
        compression="snappy",
        use_dictionary=["type_id", "plugin", "captcha", "source", "tree"],
    ) as writer:
        for start in range(0, len(samples), ROW_GROUP_SIZE):
            batch = samples[start:start + ROW_GROUP_SIZE]
            writer.write_table(build_table(batch), row_group_size=ROW_GROUP_SIZE)
    return path.stat().st_size


# -------------------------------------------------------------------------------------
# README
# -------------------------------------------------------------------------------------

README_HEADER = """---
license: other
license_name: mixed-per-plugin-licences
pretty_name: CaptchaOCR
task_categories:
- image-to-text
language:
- en
- ru
tags:
- captcha
- ocr
- minecraft
- anti-bot
- synthetic
- parquet
modality: image
size_categories: 100K<n<1M
configs:
- config_name: default
  data_files: data/*.parquet
---

# CaptchaOCR — Minecraft anti-bot captchas as Parquet

**{N_TYPES} captcha types · {N_SAMPLES} labelled samples · {N_SHARDS} Parquet shards ·
{IMAGE_BYTES} of PNG bytes · {TOTAL_BYTES} total**

This repository holds the **CaptchaOCR** dataset: captchas drawn by open-source Minecraft
anti-bot plugins, re-rendered by this project's **own Java 21 generators**, one row per
image, with every label field preserved byte-for-byte in Parquet.

The previous release stored loose `PNG + labels.jsonl` files under `data/out/` and
`data/out_ru/`.  That tree has been replaced by these shards; the label values are unchanged.

## Files

| shard | rows | bytes |
|---|---|---|
{SHARD_TABLE}

The shards are ordinary Parquet files: one row per sample, the raw PNG bytes in `image`,
and all label columns alongside.  A shard is about 250 MiB; the row order is deterministic
(tree, then type, then `labels.jsonl` order).

## Schema

| column | Arrow type | nullable | meaning |
|---|---|---|---|
| `image` | `binary` | no | the raw PNG file bytes (decode with PIL / OpenCV) |
| `file` | `string` | no | PNG file name inside its type directory (`001.png` …) |
| `type_id` | `string` | no | type path, e.g. `out/Archy-X/Krypton/map` or `out_ru/LimboFilter/symbols` |
| `plugin` | `string` | no | upstream plugin the type came from |
| `captcha` | `string` | no | captcha type inside that plugin |
| `answer` | `string` | no | what the player has to type into the answer field |
| `text` | `string` | **yes** | what is actually **drawn** on the picture; may be `null` |
| `prompt` | `string` | **yes** | the task text as the plugin shows it; may be `null` |
| `roi` | `list<int32>` | **yes** | answer band `[x, y, w, h]`, or `null` if the band is not in the frame |
| `width` | `int32` | no | PNG width in pixels |
| `height` | `int32` | no | PNG height in pixels |
| `source` | `string` | no | where the type came from: upstream class and method (`file#method`) |
| `tree` | `string` | no | `out` or `out_ru` |

## How to load it

With 🤗 `datasets` (it reads the Parquet shards directly; no loading script, no remote code):

```python
import io

from datasets import load_dataset
from PIL import Image

ds = load_dataset("Titlehhhh/captchaocr-dataset", split="train")
print(ds)                     # rows: {N_SAMPLES}
row = ds[0]
image = Image.open(io.BytesIO(row["image"]))
band = row["roi"]             # [x, y, w, h] or None
```

Filter by type while loading:

```python
ds = load_dataset("Titlehhhh/captchaocr-dataset", split="train")
subset = ds.filter(lambda row: row["type_id"] == "out/haq/mapcha/map")
```

Without `datasets` — plain `pyarrow` (or pandas):

```python
import io
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

table = pq.read_table("data")                      # a directory of Parquet shards
# or one shard: table = pq.read_table("data/train-00000-of-000{N_SHARDS_PAD}.parquet")
rows = table.to_pylist()                           # each row has the columns above
image = Image.open(io.BytesIO(rows[0]["image"]))

# column-projected / filtered read (predicate pushdown, no image decode):
answers = pq.read_table("data", columns=["type_id", "answer"])
map_rows = pq.read_table("data", filters=[("type_id", "=", "out/haq/mapcha/map")])

# pandas fallback:
# df = table.to_pandas()
```

## The band rule: `roi` may be `null`

`roi` is the rectangle `[x, y, w, h]` of the **answer band** inside the image — the crop a
recogniser should read.  **A band that does not fit into the frame is not a band**, and in
that case `roi` is `null`.  Never crop those rows: pass the whole image, or skip them.  A
row with `roi` set can still contain other text (captions, prompts) outside the band, so use
the rectangle rather than assuming the answer fills the frame.

## `text` may differ from `answer`

* `answer` — what the player types into the answer field.
* `text` — what is actually drawn on the picture.

For most types they are identical.  In some types (Russian number words, arithmetic, word
problems) the drawn text differs from the typed answer; converting one to the other is a
separate solver step, not an OCR task.  **Train a recogniser on `text`; evaluate a solver on
`answer`.**

## The {N_TYPES} types

{TYPE_TABLE}

`roi` coverage counts rows whose band is present; `text != answer` counts rows where the
drawn string and the typed answer differ.

## Provenance and honesty

* **Every image is our own render.**  All {N_SAMPLES} PNGs were produced by this project's
  **Java 21 generators** (`dataset/generator` and `dataset/generator_ru`), not by a live
  server, not by a third-party service, and not by copying anybody else's pictures.
* The renders reproduce the upstream algorithms (font, palette, noise, layout, even upstream
  defects), but the pixels are a re-render, not a screenshot of a real session.
* The generators are **not seeded**: the samples are random.  The images are one particular
  render ({REGENERATION_DATE}); the labels and generators are the reproducible part.
* Reference screenshots of the upstream plugins (`real_shots/` in the working tree) are
  **not** published here: they are other people's images.
* No picture, page or answer taken from a third-party commercial service is published here.
* Numbers in this card are computed from `labels.jsonl` by `tools/export_parquet.py` at
  export time; they are not typed by hand.

## Licence

The data is published under the licence of the upstream plugin each row came from — there is
no single licence for the whole dataset, hence `license_name: mixed-per-plugin-licences`.
The repository's `LICENSE` file holds the per-plugin breakdown and what each licence means
for you.  A user of this dataset must comply with the licence of the plugin each row came
from.
"""


def build_readme(index: DatasetIndex, shards: list[tuple[Path, int]],
                 regeneration_date: str) -> str:
    total_rows = sum(info.samples for info in index.types.values())
    total_bytes = sum(size for _, size in shards)
    image_bytes = index.total_png_bytes
    shard_table = "\n".join(
        f"| `{path.name}` | {rows:,} | {size:,} |"
        for (path, size), rows in zip(shards, shard_rows(shards))
    )
    type_lines = [
        "| `type_id` | plugin | captcha | samples | `roi` rows | `text != answer` |",
        "|---|---|---|---:|---:|---:|",
    ]
    for type_id in sorted(index.types):
        info = index.types[type_id]
        type_lines.append(
            f"| `{type_id}` | `{info.plugin}` | `{info.captcha}` | {info.samples:,} | "
            f"{info.roi_rows:,} | {info.text_ne_answer:,} |"
        )
    values = {
        "N_TYPES": f"{len(index.types):,}",
        "N_SAMPLES": f"{total_rows:,}",
        "N_SHARDS": str(len(shards)),
        "N_SHARDS_PAD": f"{len(shards):05d}",
        "IMAGE_BYTES": human_bytes(image_bytes),
        "TOTAL_BYTES": human_bytes(total_bytes),
        "SHARD_TABLE": shard_table,
        "TYPE_TABLE": "\n".join(type_lines),
        "REGENERATION_DATE": regeneration_date,
    }
    text = README_HEADER
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def shard_rows(shards: list[tuple[Path, int]]) -> list[int]:
    """Read the row counts back from the written shards (cheap footer reads)."""
    import pyarrow.parquet as pq

    return [pq.ParquetFile(path).metadata.num_rows for path, _ in shards]


# -------------------------------------------------------------------------------------
# Export
# -------------------------------------------------------------------------------------

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


# -------------------------------------------------------------------------------------
# Hugging Face Hub
# -------------------------------------------------------------------------------------

def resolve_token(explicit: str | None) -> str | None:
    """Token from --token, the environment/CLI, or the project's .hf-cache/token."""
    if explicit:
        return explicit.strip()
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    try:
        from huggingface_hub import get_token

        stored = get_token()
        if stored:
            return stored
    except Exception:  # noqa: BLE001 -- token discovery is best-effort
        pass
    token_file = REPO_ROOT / ".hf-cache" / "token"
    try:
        value = token_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    except OSError:
        pass
    return None


def api_for(token: str | None):
    from huggingface_hub import HfApi

    return HfApi(token=token)


def list_remote_files(api, repo_id: str) -> dict[str, int]:
    """Map every remote file path to its size (folders are skipped)."""
    entries = api.list_repo_tree(repo_id=repo_id, repo_type="dataset", recursive=True)
    files: dict[str, int] = {}
    for entry in entries:
        path = getattr(entry, "path", None)
        if path is None or is_remote_folder(entry):
            continue
        files[path] = getattr(entry, "size", 0) or 0
    return files


def create_commit_with_retries(api, repo_id: str, operations: list, message: str,
                               num_threads: int, what: str) -> None:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            api.create_commit(repo_id=repo_id, operations=operations,
                              repo_type="dataset", commit_message=message,
                              num_threads=num_threads)
            return
        except Exception as exc:  # noqa: BLE001 -- network failure is retryable
            last_error = exc
            wait = RETRY_SLEEP * attempt
            warn(f"{what} failed (attempt {attempt}/{MAX_RETRIES}): "
                 f"{type(exc).__name__}: {exc}; retrying in {wait:.0f} s")
            time.sleep(wait)
    raise RuntimeError(f"{what} failed after {MAX_RETRIES} attempts: {last_error}")


def upload_shards(api, repo_id: str, shards: list[tuple[Path, int]]) -> None:
    from huggingface_hub import CommitOperationAdd

    log("")
    log("=== Upload Parquet shards ===")
    total = len(shards)
    for number, (path, size) in enumerate(shards, start=1):
        operation = CommitOperationAdd(
            path_in_repo=f"{DATA_PREFIX}/{path.name}", path_or_fileobj=path)
        create_commit_with_retries(
            api, repo_id, [operation],
            f"CaptchaOCR: Parquet shard {path.name} ({number}/{total})",
            UPLOAD_NUM_THREADS, f"upload {path.name}")
        log(f"  uploaded {number}/{total}: data/{path.name} "
            f"({size:,} B, {human_bytes(size)})")


def upload_readme(api, repo_id: str, out_dir: Path) -> None:
    from huggingface_hub import CommitOperationAdd

    readme = out_dir / "README.md"
    if not readme.is_file():
        raise RuntimeError(f"README not found: {readme}")
    operation = CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=readme)
    create_commit_with_retries(api, repo_id, [operation],
                               "CaptchaOCR: Parquet dataset card",
                               UPLOAD_NUM_THREADS, "upload README.md")
    log(f"  uploaded README.md ({readme.stat().st_size:,} B)")


def delete_old_png_tree(api, repo_id: str, remote_files: dict[str, int]) -> int:
    """Delete every remote path under data/out and data/out_ru in 1000-path chunks."""
    from huggingface_hub import CommitOperationDelete

    old_paths = sorted(path for path in remote_files if is_old_tree_path(path))
    if not old_paths:
        log("  no old loose-PNG paths found under data/out or data/out_ru")
        return 0
    total_bytes = sum(remote_files[path] for path in old_paths)
    chunks = [old_paths[i:i + DELETE_CHUNK_PATHS]
              for i in range(0, len(old_paths), DELETE_CHUNK_PATHS)]
    log("")
    log("=== Delete old loose-PNG tree ===")
    log(f"  paths: {len(old_paths):,} ({human_bytes(total_bytes)}) in "
        f"{len(chunks)} chunks of up to {DELETE_CHUNK_PATHS} paths")
    deleted = 0
    for number, chunk in enumerate(chunks, start=1):
        operations = [CommitOperationDelete(path_in_repo=path) for path in chunk]
        create_commit_with_retries(
            api, repo_id, operations,
            f"CaptchaOCR: remove old PNG tree ({number}/{len(chunks)})",
            DELETE_NUM_THREADS,
            f"delete chunk {number}/{len(chunks)}")
        deleted += len(chunk)
        log(f"  chunk {number}/{len(chunks)}: deleted {len(chunk):,} paths "
            f"({deleted:,}/{len(old_paths):,})")
    log(f"  deleted {deleted:,} paths in {len(chunks)} commits")
    return deleted


def upload(api, repo_id: str, out_dir: Path) -> int:
    data_dir = out_dir / DATA_PREFIX
    local_shards = sorted(data_dir.glob("*.parquet"))
    if not local_shards:
        log("no local Parquet shards, exporting first")
        result = export(DEFAULT_DATA_DIR, out_dir, DEFAULT_TARGET_MB * 1024 * 1024)
        shards = result.shards
    else:
        shards = [(path, path.stat().st_size) for path in local_shards]
        log(f"using {len(shards)} existing local shards in {data_dir}")
    upload_shards(api, repo_id, shards)
    upload_readme(api, repo_id, out_dir)

    # Re-list right before deleting: only the old PNG tree is touched.
    remote_files = list_remote_files(api, repo_id)
    delete_old_png_tree(api, repo_id, remote_files)

    # Final state (also the body of --verify).
    log("")
    return verify_remote(api, repo_id, out_dir)


def verify_remote(api, repo_id: str, out_dir: Path) -> int:
    """Verify the remote repository against the local shard set."""
    local_shards = sorted((out_dir / DATA_PREFIX).glob("*.parquet"))
    try:
        remote_files = list_remote_files(api, repo_id)
    except Exception as exc:  # noqa: BLE001
        log(f"MISMATCH: cannot list remote tree: {type(exc).__name__}: {exc}")
        return EXIT_ERROR

    remote_parquet = {path: size for path, size in remote_files.items()
                      if path.startswith(DATA_PREFIX + "/") and path.endswith(".parquet")}
    remote_png = {path: size for path, size in remote_files.items()
                  if path.startswith(DATA_PREFIX + "/") and path.lower().endswith(".png")}
    old_left = {path: size for path, size in remote_files.items()
                if is_old_tree_path(path)}
    parquet_bytes = sum(remote_parquet.values())

    log("=== Remote verification ===")
    log(f"repo:                     {repo_id}")
    log(f"local shards:             {len(local_shards)}")
    log(f"remote Parquet files:     {len(remote_parquet)}")
    log(f"remote Parquet bytes:     {parquet_bytes:,} B ({human_bytes(parquet_bytes)})")
    log(f"remote PNG under data/:   {len(remote_png)}")
    log(f"remote files in old tree: {len(old_left)}")
    log(f"README.md present:        {'README.md' in remote_files}")

    problems: list[str] = []
    if len(remote_parquet) != len(local_shards):
        problems.append(f"Parquet count: remote {len(remote_parquet)} != "
                        f"local {len(local_shards)}")
    if remote_png:
        problems.append(f"{len(remote_png)} PNG still under data/")
    missing = [path.name for path in local_shards
               if f"{DATA_PREFIX}/{path.name}" not in remote_parquet]
    if missing:
        problems.append(f"{len(missing)} local shard(s) missing remotely: {missing[:5]}")
    if "README.md" not in remote_files:
        warn("README.md is missing at the repository root")
    if old_left:
        problems.append(f"{len(old_left)} old-tree file(s) remain under data/out or "
                        f"data/out_ru")

    if problems:
        log("MISMATCH")
        for problem in problems:
            log(f"  - {problem}")
        return EXIT_ERROR
    log("OK")
    return EXIT_OK


# -------------------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------------------

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
        return upload(api, args.repo_id, out_dir)

    export(data_dir, out_dir, target_bytes)
    return EXIT_OK


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        warn(f"{type(exc).__name__}: {exc}")
        raise SystemExit(EXIT_ERROR)
