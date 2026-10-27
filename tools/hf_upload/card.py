"""The dataset card of the Hugging Face repository - and the numbers in it.

Every number of the card is computed from ``labels.jsonl`` at upload time; nothing is
typed by hand.  The template is a plain string with ``{PLACEHOLDER}`` markers and the
helpers of ``tools.publish_hf.cards`` fill them in.
"""

from tools.publish_hf.cards import (agpl_note, dataset_card_values,
                                    licence_summary_block, no_licence_note,
                                    render_template)
from tools.publish_hf.utils import human_bytes, warn

CARD_TEMPLATE = """---
license: other
license_name: mixed-per-plugin-licences
tags:
- captcha
- ocr
- minecraft
- anti-bot
- synthetic
language:
- en
- ru
library_name: datasets
format: imagefolder
modality: image
size_categories: 10K<n<100K
---

# CaptchaOCR dataset — captchas of Minecraft anti-bot plugins, rendered

**{N_TYPES} captcha types · {N_PNG_FILES} labelled PNG ({IMAGES_PER_TYPE} per type) ·
{N_PLUGINS} upstream plugins · {TOTAL_BYTES_HUMAN}**

This repository holds the images and the labels of the CaptchaOCR captcha dataset: the
captchas that open-source Minecraft anti-bot plugins draw, re-rendered by **this project's own
generators**, with a machine-readable label for every image.

**Every PNG here is our own render** — {N_PNG_FILES} images drawn by our Java generators.
No picture, page or answer taken from a third-party service is published here; the reference
screenshots of the upstream plugins stay in the project's working tree.

The dataset is published as **plain files** (PNG + `labels.jsonl`), not as a loading script:
every sample is a PNG next to a one-line JSON record, so any training loop can read it
without `datasets`, without a network round-trip and without trusting remote code.

## What is inside

| | |
|---|---|
| captcha types | **{N_TYPES}** |
| labelled samples | **{N_SAMPLES}** |
| PNG files | **{N_PNG_FILES}** |
| upstream plugins | **{N_PLUGINS}** |
| trees | {N_TREES} |
| size of the PNG files | {TOTAL_BYTES_HUMAN} ({TOTAL_BYTES} B) |
| size of the whole repository (PNG + `labels.jsonl` + card) | ≈ {REPO_BYTES_HUMAN} |
| types with an answer band (`roi`) | {N_TYPES_WITH_ROI} (rows with: {N_ROWS_WITH_ROI}, without: {N_ROWS_WITHOUT_ROI}) |
| types where `text != answer` | {N_TYPES_TEXT_NE_ANSWER} |
| reconstruction modes | faithful {N_FAITHFUL_TYPES} · clean-room {N_CLEAN_ROOM_TYPES} · reconstructed {N_RECONSTRUCTED_TYPES} |
| combined alphabet size | {ALPHABET_SIZE} symbols |

### How this release was made

* **46 captcha types × {IMAGES_PER_TYPE} images = {N_PNG_FILES} PNG.** Every type was
  re-rendered on **2026-10-22** on the author's machine with the project's **Java 21**
  generators (`dataset/generator` and `dataset/generator_ru`), then validated and uploaded.
* This dataset is a **machine artefact**. The generators are **not seeded**: the fonts are the
  same, but the samples themselves are random, so a re-render of the same type produces a
  *different* set of pictures. The images here are one particular render of 2026-10-22 — the
  generators and the labels are the reproducible part, the pixels are not.
* The reference screenshots of the upstream plugins (the `real_shots/` folders of the Russian
  tree — {N_REAL_SHOTS} reference screenshots, {N_REAL_SHOTS_FILES} files in total) are **not
  published here** — see *What is NOT published* below.

### Layout

```
{LAYOUT}
```

Concretely, the local generator tree `{DATA_DIR}` is uploaded as-is under `data/`:

* `data/<tree>/<...>/<type>/NNN.png` — the images,
* `data/<tree>/<...>/<type>/labels.jsonl` — the labels of that type,
* `README.md` — this card,
* `LICENSE` — the per-plugin licence breakdown of the data (the same table as below, plus what
  each licence means for you),
* `dataset_inventory.json` — the machine-readable summary of everything below,
* `.gitattributes` — the Git LFS rules for the binary files.

{TREE_TABLE}

## The label format

One JSON object per line, one line per image, UTF-8:

| field | meaning |
|---|---|
| `file` | PNG name in the same directory (`001.png` …) |
| `plugin` | upstream plugin the type came from |
| `captcha` | captcha type inside that plugin |
| `answer` | what the player has to type into the answer field |
| `text` | what is actually **drawn** on the picture (differs from `answer` in some types) |
| `prompt` | the task text as the plugin shows it |
| `roi` | the answer band `[x, y, w, h]`, or `null` if the answer is not in the frame |
| `width`, `height` | PNG size |
| `source` | where the type came from: upstream class and method (`file#method`) — the audit trail |

**`text` is the target for a recogniser, `answer` is the answer for a solver.** In the types
where they differ (Russian number words, arithmetic), the `text -> answer` conversion is a
separate step, not an OCR task.

**The band rule:** a band that does not fit into the frame is not a band; in that case
`roi` = `null`.

## The types

{TYPE_TABLE}

## The plugins and their licences

Each row of the dataset comes from a different upstream plugin, and those plugins do **not**
share one licence. The licence of the data is the licence of the plugin the row came from —
check the column before you use the data. The `mode` column says how the type was rebuilt:

* **faithful** — the upstream algorithm was re-implemented exactly, including its defects;
* **clean-room** — rebuilt from the upstream behaviour without copying its assets;
* **reconstructed** — *measured from reference screenshots* and rebuilt from scratch, so the
  pixels are not the upstream ones.

{PLUGIN_TABLE}

### Licence by licence

{LICENCE_SUMMARY}

`source` in every `labels.jsonl` row points at the upstream class and method the type was
re-implemented from, so the provenance of each row can be audited without trusting this table.

{RECONSTRUCTED_LIST}

## Alphabets

The labels are not pure ASCII: some types are Russian number words, some are arithmetic
expressions, some contain spaces and punctuation.

{ALPHABET_LIST}

## What is NOT published here

* **The reference screenshots of the upstream plugins.** The author's working tree contains
  {N_REAL_SHOTS} reference screenshots of other people's plugins ({N_REAL_SHOTS_FILES} files in
  total in the `real_shots/` directories of the Russian tree). They are other people's images:
  they are **not** part of this repository and are not redistributed in any form. Every published
  PNG is our own render.
* No picture, page or answer taken from a third-party commercial service is published here.
* No model weights, no training logs, no measured-result files — this repository is data only.

## How to load it

The dataset is a directory of files. The shortest way:

```python
import json
from pathlib import Path

root = Path("data")           # clone of the repository
for labels in root.rglob("labels.jsonl"):
    for line in labels.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        image = labels.parent / row["file"]     # PNG next to the label
        band = row["roi"]                        # [x, y, w, h] or None
        answer = row["answer"]                  # what the player types
        drawn = row["text"]                     # what is drawn
```

`dataset_inventory.json` in the root of the repository is the per-type summary: sample count,
alphabet, label lengths, presence of the band, licence. Read it to build a list of training
types without walking the pictures.

## Provenance and honesty

* **Every published image is our own render.** All {N_PNG_FILES} PNG in this repository were
  produced by this project's **own Java generators** — not by a live server, not by a
  third-party service, and not by copying anybody else's pictures. The renders reproduce the
  upstream algorithms (font, palette, noise, layout, even the upstream defect), but the pixels
  are a re-render, not a screenshot of a real session.
* The reference screenshots of the upstream plugins are **not** part of this repository: they
  are other people's images, they stay in the project's working tree and are not redistributed.
* **{N_FAITHFUL_TYPES} of the {N_TYPES} types are faithful ports** — the upstream algorithm was
  re-implemented exactly, including its defects.
* **{N_CLEAN_ROOM_TYPES} types are clean-room reconstructions**, and {N_RECONSTRUCTED_TYPES}
  are marked `reconstructed`: they were **measured from reference screenshots** and rebuilt
  from scratch, so they are *not* faithful ports and their pixels are not the upstream ones.
  The list is below, with the provenance string each type carries in `labels.jsonl`.

* Numbers in this card are computed from `labels.jsonl` by `tools/upload_dataset.py` at
  upload time; they are not typed by hand.

## Licence

* The **data** is published under the licences of the upstream plugins, one per type — see the
  plugin table above. There is no single licence for the whole dataset; that is what the YAML
  field `license_name: mixed-per-plugin-licences` means.
* The **file `LICENSE`** in the root of this repository holds the same breakdown in full: the
  per-plugin table, what each licence means for you, and an explicit note about the plugins that
  granted no licence at all.
* The **generator code** of the project is under a separate licence.
* A user of this dataset must comply with the licence of the plugin each row came from.
"""


def build_card(inventory: dict, repo_id: str, real_shots: int, real_shots_files: int,
               labels_bytes: int) -> str:
    """Собрать карточку репозитория (все числа — из ``labels.jsonl``)."""
    values = dataset_card_values(inventory, repo_id)
    values.update({
        "LICENCE_SUMMARY": licence_summary_block(inventory),
        "NO_LICENCE_NOTE": no_licence_note(inventory),
        "AGPL_NOTE": agpl_note(inventory),
        "N_REAL_SHOTS": str(real_shots),
        "N_REAL_SHOTS_FILES": str(real_shots_files),
    })
    counts = sorted(set(t["png_files"] for t in inventory["types"]))
    values["IMAGES_PER_TYPE"] = (str(counts[0]) if len(counts) == 1
                                 else " / ".join(str(c) for c in counts))
    values["REPO_BYTES_HUMAN"] = human_bytes(inventory["totals"]["bytes"] + labels_bytes)
    card, leftovers = render_template(CARD_TEMPLATE, values)
    if leftovers:
        warn("в карточке остались незаполненные плейсхолдеры: " + ", ".join(leftovers))
    return card
