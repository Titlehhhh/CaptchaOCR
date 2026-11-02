
from pathlib import Path

from .common import human_bytes
from .index import DatasetIndex

REPO_ID = "Titlehhhh/captchaocr-dataset"
ASSET_BASE = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/assets"
LICENSE_URL = f"https://huggingface.co/datasets/{REPO_ID}/blob/main/LICENSE"

GALLERY = [
    ("out/Archy-X/Krypton/map", "Krypton map captcha with a five-letter code"),
    ("out/haq/mapcha/map", "mapcha map captcha with a four-letter code"),
    ("out/LagBug/XProtect/code", "XProtect chat code captcha"),
    ("out_ru/LimboFilter/symbols", "LimboFilter Cyrillic symbol captcha"),
    ("out_ru/GalleryCaptcha/ru-web", "Reconstructed web captcha, 150 by 90 pixels"),
    ("out_ru/CaptchaVerifyZ/map", "CaptchaVerifyZ map captcha in capital letters"),
]

HERO_ALT = ("Six captcha styles from Minecraft anti-bot plugins: map codes, a chat code, "
            "Cyrillic symbols and a web captcha")

PLUGIN_LICENCES = {
    "Archy-X/Krypton": ("no licence (all rights reserved)", "clean-room"),
    "BotFilter": ("BSD-2-Clause + запрет на коммерческий хостинг", "clean-room"),
    "CaptchaVerifyZ": ("all rights reserved (Modrinth)", "clean-room"),
    "GalleryCaptcha": ("не установлена (см. source в labels.jsonl)", "reconstructed"),
    "InstantlyMoist/Captcha": ("MIT", "faithful"),
    "JSH32/Minecaptcha": ("MIT", "faithful"),
    "LagBug/XProtect": ("MIT", "faithful"),
    "LimboFilter": ("AGPL-3.0", "clean-room"),
    "haq/mapcha": ("MIT", "faithful"),
    "irootdev/AnBot": ("GPL-3.0", "clean-room"),
    "jonesdevelopment/sonar": ("GPL-3.0", "clean-room"),
    "just-captcha/ProstoCaptcha": ("MIT", "faithful"),
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA": (
        "no licence file (all rights reserved)", "clean-room"),
}

LICENCE_TEXT = {
    "no licence (all rights reserved)": "No licence — all rights reserved",
    "no licence file (all rights reserved)": "No licence file — all rights reserved",
    "all rights reserved (Modrinth)": "All rights reserved (Modrinth)",
    "BSD-2-Clause + запрет на коммерческий хостинг": "BSD-2-Clause, no commercial hosting",
    "не установлена (см. source в labels.jsonl)": "Not established (see `source`)",
}

README_HEADER = """---
license: other
license_name: mixed-per-plugin-licences
license_link: {LICENSE_URL}
pretty_name: CaptchaOCR — Minecraft anti-bot captchas
task_categories: [image-to-text]
language: [en, ru]
tags: [captcha, ocr, minecraft, anti-bot, synthetic, parquet, image]
size_categories: 100K<n<1M
configs:
- config_name: default
  data_files: data/*.parquet
---

<img src="{ASSET_BASE}/hero.png" alt="{HERO_ALT}" width="100%">

# CaptchaOCR — Minecraft anti-bot captchas as training data

Minecraft anti-bot captchas, re-rendered by this project's Java 21 generators and packed one image per Parquet row: image, answer, drawn text and answer band.

{BADGES}

## What's inside

- **{N_TYPES} captcha types** from **{N_PLUGINS} upstream names** — {N_FAITHFUL} pixel-faithful ports, {N_CLEAN_ROOM} clean-room reimplementations, {N_RECONSTRUCTED} reconstructions with no upstream plugin.
- **{N_SAMPLES} images**, 10,000 per type, one Parquet row each, with every label field from `labels.jsonl` in the same row.
- **{N_SHARDS} Parquet shards, {TOTAL_BYTES}** — {SHARD_RANGE} each, no loading script, no remote code.
- **`roi` in {N_TYPES_WITH_ROI} of {N_TYPES} types** — {N_ROWS_WITH_ROI} answer bands; the other {N_ROWS_WITHOUT_ROI} rows need the whole frame.

## Gallery

Six examples of these types, answer under each image.

{GALLERY_TABLE}

## Quickstart

```python
import io
from datasets import load_dataset
from PIL import Image

ds = load_dataset("{REPO_ID}", split="train")
row = ds[0]
image = Image.open(io.BytesIO(row["image"])); print(row["answer"], row["roi"])
```

<details>
<summary>Filter one type, or read a shard with pyarrow</summary>

```python
ds = load_dataset("{REPO_ID}", split="train")
subset = ds.filter(lambda row: row["type_id"] == "out/haq/mapcha/map")

import pyarrow.parquet as pq

table = pq.read_table("data/train-00000-of-{N_SHARDS_PAD}.parquet",
                      columns=["type_id", "answer"])
```

`train-00000-of-{N_SHARDS_PAD}.parquet` is the first of {N_SHARDS} shards; the row order is
deterministic (tree, type, `labels.jsonl` order).
</details>

## Fields

| column | type | meaning |
|---|---|---|
| `image` | `binary` | raw PNG bytes; decode with `PIL.Image.open(io.BytesIO(...))` |
| `file` | `string` | file name inside the type directory (`001.png` …) |
| `type_id` | `string` | type path, e.g. `out/Archy-X/Krypton/map` |
| `plugin` | `string` | upstream plugin, e.g. `haq/mapcha` |
| `captcha` | `string` | captcha style inside the plugin, e.g. `map` |
| `answer` | `string` | what the player types into the answer field |
| `text` | `string`, nullable | what is drawn on the image |
| `prompt` | `string`, nullable | task text the plugin shows |
| `roi` | `list<int32>`, nullable | answer band `[x, y, w, h]` |
| `width` | `int32` | PNG width in pixels |
| `height` | `int32` | PNG height in pixels |
| `source` | `string` | upstream class and method that produced the style |
| `tree` | `string` | `out` (Latin) or `out_ru` (Cyrillic) |

`text` is what is drawn; `answer` is what the player types. They differ in {N_TYPES_TEXT_NE_ANSWER} types, where a solver step converts one to the other — train a recogniser on `text`, evaluate a solver on `answer`. `roi` is the answer band; when the band does not fit the frame, `roi` is `null`, so pass the whole image and never crop those rows.

## Types

{N_TYPES} types from {N_PLUGINS} upstream names. `roi` rows count rows with the band present; `text ≠ answer` counts rows where the drawn string differs from the typed answer.

<details>
<summary>All {N_TYPES} types</summary>

| type_id | plugin | captcha | samples | roi rows | text ≠ answer | mode | license |
|---|---|---|---:|---:|---:|---|---|
{TYPE_TABLE}

This snapshot holds {N_TYPES} of the 21 types in the generator tree. `out_ru/LimboFilter/digits` was rendered after the snapshot and is not published here.
</details>

## License

Each row carries the license of the upstream plugin it came from, so the dataset as a whole is mixed (`license_name: mixed-per-plugin-licences`). Several upstream licenses forbid commercial hosting or reserve all rights, so check the table before you ship anything. Full text: [LICENSE]({LICENSE_URL}).

<details>
<summary>Licenses by upstream plugin</summary>

| plugin | types | samples | license | mode |
|---|---|---:|---|---|
{PLUGIN_TABLE}

`mode` says how close the pixels are to the upstream plugin: **faithful** is a port of the upstream drawing code, **clean-room** is a reimplementation from the algorithm, **reconstructed** means no upstream plugin was available.
</details>

## Provenance

- Every image is a re-render by the Java 21 generators in this repository, not a screenshot and not a copy.
- {N_FAITHFUL} types are pixel-faithful ports, {N_CLEAN_ROOM} are clean-room reimplementations, {N_RECONSTRUCTED} are reconstructed from reference screenshots.
- The generators are not seeded: this is one random render ({REGENERATION_DATE}). The labels and the generator code are the reproducible part.
- The upstream reference screenshots that guided the reconstructions are not published; they are other people's images.
- No image, page or answer from a third-party commercial service is included.

## Limitations

- Synthetic images: fonts, noise and layout follow the plugin algorithms, not a live server, so expect a gap on real screenshots.
- {N_TYPES_WITHOUT_ROI} types have no `roi`; there the answer band is not in the frame, so feed the whole image.
- {N_TYPES_TEXT_NE_ANSWER} types put a solver step between the drawn string and the answer; OCR alone does not solve them.
- Other anti-bot plugins are not represented: the snapshot stops at the types listed above.
"""


def short_label(type_id: str) -> str:
    parts = type_id.split("/")[1:]
    return "/".join(parts[-2:])


def licence_text(value: str) -> str:
    return LICENCE_TEXT.get(value, value)


def gallery_answers(index: DatasetIndex) -> dict[str, str]:
    wanted = {type_id for type_id, _ in GALLERY}
    answers: dict[str, str] = {}
    for sample in index.samples:
        if sample.type_id not in wanted:
            continue
        if sample.type_id not in answers or sample.file == "001.png":
            answers[sample.type_id] = sample.answer
    return answers


def build_readme(index: DatasetIndex, shards: list[tuple[Path, int]],
                 regeneration_date: str, inventory: dict | None = None) -> str:
    total_rows = sum(info.samples for info in index.types.values())
    total_bytes = sum(size for _, size in shards)
    inventory_types = {t["type_id"]: t for t in (inventory or {}).get("types", [])}
    inventory_plugins = {p["plugin"]: p for p in (inventory or {}).get("plugins", [])}

    def meta(plugin: str) -> tuple[str, str]:
        entry = inventory_plugins.get(plugin)
        if entry:
            return licence_text(entry["licence"]), entry["mode"]
        licence, mode = PLUGIN_LICENCES.get(
            plugin, ("not established (see `source`)", "unknown"))
        return licence_text(licence), mode

    type_rows = []
    modes: dict[str, int] = {}
    rows_with_roi = 0
    types_with_roi = 0
    types_text_ne_answer = 0
    for type_id in sorted(index.types):
        info = index.types[type_id]
        entry = inventory_types.get(type_id, {})
        roi_rows = int(entry.get("rows_with_roi", info.roi_rows))
        text_ne_answer = int(entry.get("rows_text_ne_answer", info.text_ne_answer))
        licence, mode = meta(info.plugin)
        modes[mode] = modes.get(mode, 0) + 1
        rows_with_roi += roi_rows
        types_with_roi += 1 if roi_rows else 0
        types_text_ne_answer += 1 if text_ne_answer else 0
        type_rows.append(
            f"| `{type_id}` | `{info.plugin}` | `{info.captcha}` | {info.samples:,} | "
            f"{roi_rows:,} | {text_ne_answer:,} | {mode} | {licence} |")

    plugin_rows = []
    for plugin in sorted({info.plugin for info in index.types.values()}):
        types = [info for info in index.types.values() if info.plugin == plugin]
        licence, mode = meta(plugin)
        plugin_rows.append(
            f"| `{plugin}` | {len(types)} | {sum(t.samples for t in types):,} | "
            f"{licence} | {mode} |")

    answers = gallery_answers(index)
    cells = []
    for number, (type_id, alt) in enumerate(GALLERY, start=1):
        answer = answers.get(type_id, "")
        cells.append(
            f'<img src="{ASSET_BASE}/gallery/{number:02d}.png" width="170" alt="{alt}">'
            f"<br><sub>`{short_label(type_id)}` — `{answer}`</sub>")
    gallery_table = "\n".join([
        "| " + " | ".join(cells[:3]) + " |",
        "|---|---|---|",
        "| " + " | ".join(cells[3:]) + " |",
    ])

    sizes = sorted(size for _, size in shards)
    shard_range = f"{sizes[0] // 2**20}–{round(sizes[-1] / 2**20)} MiB"
    badges = "\n".join([
        f"![samples](https://img.shields.io/badge/samples-{total_rows:,}-blue)",
        f"![types](https://img.shields.io/badge/captcha_types-{len(index.types)}-blueviolet)",
        f"![plugins](https://img.shields.io/badge/upstream_plugins-{len(plugin_rows)}-informational)",
        f"![size](https://img.shields.io/badge/size-{human_bytes(total_bytes).replace(' ', '_')}-lightgrey)",
        "![format](https://img.shields.io/badge/format-Parquet-150458)",
        "![task](https://img.shields.io/badge/task-image--to--text-success)",
        "![license](https://img.shields.io/badge/license-mixed_per_plugin-orange)",
    ]).replace(",", "%2C")

    values = {
        "REPO_ID": REPO_ID,
        "ASSET_BASE": ASSET_BASE,
        "LICENSE_URL": LICENSE_URL,
        "HERO_ALT": HERO_ALT,
        "BADGES": badges,
        "GALLERY_TABLE": gallery_table,
        "N_TYPES": f"{len(index.types):,}",
        "N_SAMPLES": f"{total_rows:,}",
        "N_PLUGINS": str(len(plugin_rows)),
        "N_SHARDS": str(len(shards)),
        "N_SHARDS_PAD": f"{len(shards):05d}",
        "TOTAL_BYTES": human_bytes(total_bytes),
        "SHARD_RANGE": shard_range,
        "N_TYPES_WITH_ROI": str(types_with_roi),
        "N_TYPES_WITHOUT_ROI": str(len(index.types) - types_with_roi),
        "N_ROWS_WITH_ROI": f"{rows_with_roi:,}",
        "N_ROWS_WITHOUT_ROI": f"{total_rows - rows_with_roi:,}",
        "N_TYPES_TEXT_NE_ANSWER": str(types_text_ne_answer),
        "N_FAITHFUL": str(modes.get("faithful", 0)),
        "N_CLEAN_ROOM": str(modes.get("clean-room", 0)),
        "N_RECONSTRUCTED": str(modes.get("reconstructed", 0)),
        "REGENERATION_DATE": regeneration_date,
        "TYPE_TABLE": "\n".join(type_rows),
        "PLUGIN_TABLE": "\n".join(plugin_rows),
    }
    text = README_HEADER
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text
