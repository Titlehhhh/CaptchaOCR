
from pathlib import Path

from .common import human_bytes
from .index import DatasetIndex
from .shards import shard_rows

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
* The generators are **not seeded**: the samples are random.  The images here are one particular
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
