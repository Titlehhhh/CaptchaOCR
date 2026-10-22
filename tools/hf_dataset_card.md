---
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
size_categories: 1K<n<10K
---

# CaptchaOCR dataset — captchas of Minecraft anti-bot plugins, rendered

**{N_TYPES} captcha types · {N_SAMPLES} labelled PNG · {N_PLUGINS} upstream plugins · {TOTAL_BYTES_HUMAN}**

This repository holds the images and the labels of the CaptchaOCR captcha dataset: the
captchas that open-source Minecraft anti-bot plugins draw, re-rendered by **this project's own
generators**, with a machine-readable label for every image.

**Every PNG here is our own render** — {N_PNG_FILES} images drawn by our Java generators.
No picture, page or answer taken from a third-party service is published here; the reference
screenshots of the upstream plugins stay in the project's working tree.

The dataset is published as **plain files** (PNG + `labels.jsonl`), not as a loading script:
every sample is a PNG next to a one-line JSON record, so any training loop can read it
without `datasets`, without a network round-trip and without trusting remote code.

## What these captchas look like

Real frames from this dataset — one per style. The caption gives the type and the **gold answer**
from `labels.jsonl` (what the player has to type). Paths are relative to the root of this
repository.

| | | |
|---|---|---|
| ![Map captcha](data/out/haq/mapcha/map/001.png) | ![Web captcha](data/out_ru/GalleryCaptcha/ru-web/001.png) | ![Cyrillic symbols](data/out_ru/LimboFilter/symbols/001.png) |
| `haq/mapcha/map` — 128×128 Minecraft map, 4 Latin characters · answer `s8TO` | `GalleryCaptcha/ru-web` — 150×90 web-style captcha, white background · answer `DpZ7D` | `LimboFilter/symbols` — 128×128, dark background, 3 Cyrillic characters · answer `ЪМИ` |
| ![Puzzle frame](data/out_ru/LimboFilter/framed2x2/001.png) | ![GUI scene](data/out/LagBug/XProtect/gui/001.png) | ![Digits in an anvil GUI](data/out/n1zamu/NCaptcha/anvil/001.png) |
| `LimboFilter/framed2x2` — 256×256, 2×2 puzzle frame, the number spelled out in words · answer `638` | `LagBug/XProtect/gui` — 380×260 GUI scene (chat log + inventory) · answer `Glowstone` | `n1zamu/NCaptcha/anvil` — 420×150 anvil GUI, digits · answer `28612` |

Every picture above is a render of this project's own generators — see
*Provenance and honesty* below.

## What is inside

| | |
|---|---|
| типов (captcha types) | **{N_TYPES}** |
| размеченных сэмплов | **{N_SAMPLES}** |
| PNG-файлов | **{N_PNG_FILES}** |
| плагинов-источников | **{N_PLUGINS}** |
| деревьев | {N_TREES} |
| суммарный размер | {TOTAL_BYTES_HUMAN} ({TOTAL_BYTES} Б) |
| типов с полосой (`roi`) | {N_TYPES_WITH_ROI} (строк с полосой: {N_ROWS_WITH_ROI}, без: {N_ROWS_WITHOUT_ROI}) |
| типов, где `text != answer` | {N_TYPES_TEXT_NE_ANSWER} |
| режимов реконструкции | faithful {N_FAITHFUL_TYPES} · clean-room {N_CLEAN_ROOM_TYPES} · reconstructed {N_RECONSTRUCTED_TYPES} |
| размер объединённого алфавита | {ALPHABET_SIZE} символов |

### Раскладка

One layout, mirroring the generator's output tree:

```
{LAYOUT}
```

Concretely, the local generator tree `{DATA_DIR}` is uploaded as-is under `data/`:

* `data/<tree>/<...>/<type>/NNN.png` — the images,
* `data/<tree>/<...>/<type>/labels.jsonl` — the labels of that type,
* `README.md` — this card,
* `LICENSE` — the per-plugin licence breakdown of the data (the same table as below, plus what
  each licence means for you),
* `dataset_inventory.json` — the machine-readable summary of everything below.

{TREE_TABLE}

## The label format

One JSON object per line, one line per image, UTF-8:

| поле | смысл |
|---|---|
| `file` | имя PNG в этом же каталоге (`001.png` …) |
| `plugin` | плагин-источник |
| `captcha` | тип капчи внутри плагина |
| `answer` | что игрок вводит в поле ответа |
| `text` | что **нарисовано** на картинке (в части типов отличается от `answer`) |
| `prompt` | текст задания, как его показывает плагин |
| `roi` | полоса с ответом `[x, y, w, h]` или `null`, если ответа в кадре нет |
| `width`, `height` | размер PNG |
| `source` | откуда взялся тип: класс и метод апстрима (`file#method`) — аудит-тропа |

**`text` — это цель для распознавателя, `answer` — это ответ для solver'а.** В типах, где
они различаются (русские числительные, арифметика), преобразование `text -> answer` — отдельный
шаг, а не задача OCR.

**Правило полосы:** полоса, которая не помещается в кадр, — это не полоса; в этом случае `roi` = `null`.

## The types

{TYPE_TABLE}

## The plugins and their licences

Each row of the dataset comes from a different upstream plugin, and those plugins do **not**
share one licence. The licence of the data is the licence of the plugin the row came from —
check the column before you use the data.

{PLUGIN_TABLE}

`source` in every `labels.jsonl` row points at the upstream class and method the type was
re-implemented from, so the provenance of each row can be audited without trusting this table.

## Alphabets

The labels are not pure ASCII: some types are Russian number words, some are arithmetic
expressions, some contain spaces and punctuation.

{ALPHABET_LIST}

## How to load it

The dataset is a directory of files. The shortest way:

```python
import json, os
from pathlib import Path

root = Path("data")           # клон репозитория
for labels in root.rglob("labels.jsonl"):
    for line in labels.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        image = labels.parent / row["file"]     # PNG рядом с меткой
        band = row["roi"]                        # [x, y, w, h] или None
        answer = row["answer"]                  # что вводит игрок
        drawn = row["text"]                     # что нарисовано
```

`dataset_inventory.json` в корне репозитория — сводка по типам: число сэмплов, алфавит,
длины меток, наличие полосы, лицензия. Её удобно читать, чтобы построить список
обучающих типов, не обходя картинки.

## Provenance and honesty

* **Every published image is our own render.** All {N_PNG_FILES} PNG in this repository were
  produced by this project's **own Java generators** — not by a live server, not by a
  third-party service, and not by copying anybody else's pictures. The renders reproduce the
  upstream algorithms (font, palette, noise, layout, the defect), but the pixels are a
  re-render, not a screenshot of a real session.
* The reference screenshots of the upstream plugins are **not** part of this repository: they
  are other people's images, they stay in the project's working tree and are not redistributed.
* **{N_FAITHFUL_TYPES} of the {N_TYPES} types are faithful ports** — the upstream algorithm was
  re-implemented exactly, including its defects.
* **{N_CLEAN_ROOM_TYPES} types are clean-room reconstructions**, and {N_RECONSTRUCTED_TYPES}
  are marked `reconstructed`: they were **measured from reference screenshots** and rebuilt
  from scratch, so they are *not* faithful ports and their pixels are not the upstream ones.
  The list is below, with the provenance string each type carries in `labels.jsonl`.

{RECONSTRUCTED_LIST}

* Numbers in this card are computed from `labels.jsonl` by `tools/publish_hf.py` at upload time;
  they are not typed by hand.

## Licence

* The **data** is published under the licences of the upstream plugins, one per type — see the
  plugin table above. There is no single licence for the whole dataset; that is what the YAML
  field `license_name: mixed-per-plugin-licences` means.
* The **file `LICENSE`** in the root of this repository holds the same breakdown in full: the
  per-plugin table, what each licence means for you, and an explicit note about the plugins that
  granted no licence at all.
* The **generator code** of the project is under a separate licence.
* A user of this dataset must comply with the licence of the plugin each row came from.
