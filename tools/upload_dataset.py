"""Опубликовать датасет CaptchaOCR на Hugging Face Hub (существующий репозиторий).

Скрипт заливает в **существующий** публичный репозиторий
``Titlehhhh/captchaocr-dataset`` полный набор PNG и разметки из
``dataset/out`` и ``dataset/out_ru`` — по 500 картинок на тип — плюс карточку
репозитория, машинно-читаемую сводку, файл лицензии и ``.gitattributes``.

Раскладка **та же**, что была в первой публикации, чтобы
``tools/fetch_dataset.py`` продолжал работать без правок::

    data/out/<owner>/<repo>/<type>/NNN.png
    data/out/<owner>/<repo>/<type>/labels.jsonl
    data/out_ru/<Plugin>/<type>/NNN.png
    data/out_ru/<Plugin>/<type>/labels.jsonl

Что скрипт **не** делает (никогда):

* не копирует ничего из ``dataset/out_ru/**/real_shots/**`` — это чужие
  референсные скриншоты апстримных плагинов, они не публикуются;
* не придумывает лицензии: лицензия и режим реконструкции берутся из
  проектной таблицы ``tools/publish_hf.py`` (``PLUGIN_LICENCES``), а режим —
  из поля ``source`` в ``labels.jsonl``;
* не трогает файлы в рабочем дереве: всё считается на лету, в репозиторий
  пишется только то, что перечислено планом.

Повторный запуск **безопасен и докачивает остаток**: файл считается уже
залитым только если совпадает его **содержимое** (sha256 для LFS-файлов,
git-sha1 для обычных), а не только размер. Датасет перерисован, поэтому
картинки 001–100 отличаются от прежних, и они перезаписываются, а не
пропускаются.

Режимы::

    python tools/upload_dataset.py --dry-run   # план, ничего не грузится
    python tools/upload_dataset.py             # загрузка
    python tools/upload_dataset.py --verify    # проверка удалённого дерева
    python tools/upload_dataset.py --prune     # загрузка + удаление устаревших файлов

Загрузка идёт батчами (метки — один батч, дальше по одному типу капчи), а каждый
батч режется на коммиты не больше ``--batch-files`` файлов (по умолчанию 250):
десять тысяч PNG одного типа больше не превращаются в один стомегабайтный
коммит. Ретраи прежние: падение сети не теряет уже залитое, повторный запуск
докачивает остаток.

Сколько потоков отдаётся одному коммиту, задаёт ``--num-threads`` (по умолчанию
16, зажимается в 1..64): это же число — размер пула загрузки LFS, поэтому от него
зависит скорость заливки большого набора.

``--prune`` удаляет из ``data/`` те удалённые файлы, которых больше нет в
локальном дереве (например, типы, убранные из набора), тоже кусками по
``--batch-files``. Карточка, ``LICENSE``, сводка и ``.gitattributes`` не
удаляются никогда, и ничего вне ``data/`` не трогается.

Коды выхода: ``0`` — успех, ``1`` — ошибка, ``2`` — нет авторизации.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import publish_hf as ph  # noqa: E402  — модуль из этого же tools/, read-only

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NO_AUTH = 2

#: Репозиторий назначения — существующий, публичный.
DEFAULT_REPO_ID = "Titlehhhh/captchaocr-dataset"

#: Куда внутри репозитория ложится датасет — та же раскладка, что и раньше.
DATA_PREFIX = "data"

#: Имя машинно-читаемой сводки в корне репозитория.
INVENTORY_NAME = "dataset_inventory.json"

#: Дата текущей перерисовки датасета (факт, а не вычисление).
REGENERATION_DATE = "2026-10-22"

#: Ретраи на один батч (коммит).
MAX_RETRIES = 4
RETRY_SLEEP = 8.0

#: Сколько файлов кладётся в ОДИН коммит (по умолчанию); переопределяется
#: флагом ``--batch-files``. 250 файлов — это единицы мегабайт на коммит.
DEFAULT_BATCH_FILES = 250

#: Сколько потоков отдаётся одному коммиту (``num_threads`` у
#: ``HfApi.create_commit``). Это же число — размер пула загрузки LFS, поэтому
#: именно оно ограничивает скорость заливки больших наборов; по умолчанию хаб
#: ставит 5. Переопределяется флагом ``--num-threads``.
DEFAULT_NUM_THREADS = 16
MIN_NUM_THREADS = 1
MAX_NUM_THREADS = 64

#: Действующее значение ``--num-threads``: его ставит ``main()``, его читают все
#: вызовы ``create_commit`` (одна точка правды).
NUM_THREADS = DEFAULT_NUM_THREADS


def log(message: str = "") -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print(f"ВНИМАНИЕ: {message}", file=sys.stderr, flush=True)


# =====================================================================================
# Сбор данных
# =====================================================================================

def find_types(data_dir: Path, trees: list[str] | None = None) -> list:
    """Все типы капчи (каталоги с ``labels.jsonl``) — без ``real_shots``.

    ``trees`` — если задан, берутся только эти деревья (``out``, ``out_ru``).
    """
    types = ph.find_type_dirs(data_dir)
    if trees:
        wanted = {t.strip().lower() for t in trees if t.strip()}
        types = [t for t in types if t.tree.lower() in wanted]
    return types


def collect(types: list) -> None:
    """Заполнить сводку по каждому типу (числа берутся из ``labels.jsonl``)."""
    for t in types:
        ph.collect_type(t)


def count_real_shots(data_dir: Path) -> tuple[int, int]:
    """Сколько в папках ``real_shots`` референсных скриншотов и файлов всего.

    Их НЕ публикуем. Скриншоты — это PNG; рядом лежат ещё и заметки (.md/.txt),
    поэтому для карточки важны оба числа.
    """
    shots = 0
    files = 0
    for dirpath, dirnames, filenames in os.walk(data_dir):
        if "real_shots" in Path(dirpath).parts:
            for name in filenames:
                files += 1
                if name.lower().endswith(".png"):
                    shots += 1
            dirnames[:] = []
    return shots, files


# =====================================================================================
# Карточка
# =====================================================================================

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
    values = ph.dataset_card_values(inventory, repo_id)
    values.update({
        "LICENCE_SUMMARY": ph.licence_summary_block(inventory),
        "NO_LICENCE_NOTE": ph.no_licence_note(inventory),
        "AGPL_NOTE": ph.agpl_note(inventory),
        "N_REAL_SHOTS": str(real_shots),
        "N_REAL_SHOTS_FILES": str(real_shots_files),
    })
    counts = sorted(set(t["png_files"] for t in inventory["types"]))
    values["IMAGES_PER_TYPE"] = (str(counts[0]) if len(counts) == 1
                                 else " / ".join(str(c) for c in counts))
    values["REPO_BYTES_HUMAN"] = ph.human_bytes(inventory["totals"]["bytes"] + labels_bytes)
    card, leftovers = ph.render_template(CARD_TEMPLATE, values)
    if leftovers:
        warn("в карточке остались незаполненные плейсхолдеры: " + ", ".join(leftovers))
    return card


#: ``.gitattributes`` — стандартный шаблон Hugging Face (PNG и прочие бинарники в LFS).
#: Репозиторий уже содержит такой файл; скрипт его не перезаписывает, если он есть.
GITATTRIBUTES_FALLBACK = (
    "*.png filter=lfs diff=lfs merge=lfs -text\n"
    "*.jsonl text eol=lf\n"
    "*.json text eol=lf\n"
)


# =====================================================================================
# Дайджесты: что уже залито, а что надо перезаписать
# =====================================================================================

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha1(path: Path) -> str:
    """sha1 объекта git для обычного (не-LFS) файла: ``sha1("blob <size>\\0" + data)``."""
    size = path.stat().st_size
    digest = hashlib.sha1()
    digest.update(b"blob %d\0" % size)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remote_digests(api, repo_id: str) -> dict[str, str]:
    """Карта «путь в репозитории -> дайджест содержимого» для уже залитого.

    Для LFS-файлов дайджест — sha256 из ``lfs.sha256``, для обычных — git-sha1 из
    ``blob_id``. Сравнение по **содержимому**, а не по размеру: картинки
    перерисованы, и старые 001–100 надо перезаписать, а не пропустить.
    """
    digests: dict[str, str] = {}
    try:
        entries = list(api.list_repo_tree(repo_id=repo_id, repo_type="dataset",
                                          recursive=True))
    except Exception as exc:  # noqa: BLE001 — репозитория ещё нет
        log(f"  (репозиторий недоступен: {type(exc).__name__})")
        return digests
    for entry in entries:
        path = getattr(entry, "path", None)
        if path is None:
            continue
        lfs = getattr(entry, "lfs", None)
        if lfs is not None and getattr(lfs, "sha256", None):
            digests[path] = str(lfs.sha256)
        else:
            blob_id = getattr(entry, "blob_id", None)
            if blob_id:
                digests[path] = str(blob_id)
    return digests


def local_digest(path: Path, is_lfs: bool) -> str:
    return sha256_file(path) if is_lfs else git_blob_sha1(path)


def is_lfs_remote(path_in_repo: str, digests: dict[str, str], sizes: dict[str, int]) -> bool:
    """Файл на сервере лежит в LFS? Определяем по тому, есть ли у него lfs-дайджест."""
    # lfs-файлы дают 64-символьный sha256, обычные — 40-символьный git-sha1.
    digest = digests.get(path_in_repo, "")
    return len(digest) == 64


# =====================================================================================
# План и загрузка
# =====================================================================================

class Plan:
    """План загрузки: список батчей (имя -> [(путь в репозитории, локальный файл)])."""

    def __init__(self) -> None:
        self.batches: list[tuple[str, list[tuple[str, Path]]]] = []

    def add_batch(self, name: str, items: list[tuple[str, Path]]) -> None:
        if items:
            self.batches.append((name, items))

    def total_files(self) -> int:
        return sum(len(items) for _, items in self.batches)

    def total_bytes(self) -> int:
        return sum(p.stat().st_size for _, items in self.batches for _, p in items)

    def chunk_count(self, batch_files: int) -> int:
        """Сколько коммитов получится, если резать каждый батч по N файлов."""
        return sum(chunk_count(len(items), batch_files) for _, items in self.batches)


def chunk_count(files: int, batch_files: int) -> int:
    """Число кусков по ``batch_files`` файлов (0 файлов — 0 коммитов)."""
    per = max(1, int(batch_files))
    return -(-files // per)


def chunked(items: list, batch_files: int) -> list[list]:
    """Разрезать список на куски не длиннее ``batch_files``."""
    per = max(1, int(batch_files))
    return [items[i:i + per] for i in range(0, len(items), per)]


def build_plan(types: list, digests: dict[str, str]) -> tuple[Plan, list[str]]:
    """План: сначала все ``labels.jsonl`` (аудит-тропа), потом PNG по типам.

    Файл считается уже залитым только если его **содержимое** совпадает с
    локальным; иначе он в плане (перезапись).
    """
    plan = Plan()
    replaced: list[str] = []

    labels_items: list[tuple[str, Path]] = []
    for t in types:
        path_in_repo = f"{DATA_PREFIX}/{t.type_id}/labels.jsonl"
        remote = digests.get(path_in_repo)
        if remote is None or remote != git_blob_sha1(t.labels_path):
            labels_items.append((path_in_repo, t.labels_path))
        else:
            replaced.append(path_in_repo)
    plan.add_batch("labels.jsonl (all types)", labels_items)

    for t in types:
        items: list[tuple[str, Path]] = []
        for png in t.pngs:
            path_in_repo = f"{DATA_PREFIX}/{t.type_id}/{png.name}"
            remote = digests.get(path_in_repo)
            if remote is None or remote != sha256_file(png):
                items.append((path_in_repo, png))
        plan.add_batch(f"png: {t.type_id}", items)
    return plan, replaced


def local_target_paths(types: list) -> set[str]:
    """Полный набор путей, которые ДОЛЖНЫ быть в репозитории для локального дерева.

    Это все ``labels.jsonl`` и все PNG всех типов — не только изменённые файлы
    плана, а весь целевой набор: по нему считается устаревшее (stale).
    """
    paths: set[str] = set()
    for t in types:
        paths.add(f"{DATA_PREFIX}/{t.type_id}/labels.jsonl")
        for png in t.pngs:
            paths.add(f"{DATA_PREFIX}/{t.type_id}/{png.name}")
    return paths


def is_protected_path(path_in_repo: str) -> bool:
    """Файл, который ``--prune`` не удаляет никогда (где бы он ни лежал)."""
    name = path_in_repo.rsplit("/", 1)[-1]
    return (name in {"README.md", INVENTORY_NAME, ".gitattributes"}
            or name.startswith("LICENSE"))


def is_remote_folder(entry) -> bool:
    """Каталог ли это в ``list_repo_tree``.

    В ``huggingface_hub`` >= 1.x у записей нет поля ``type``: каталог приходит
    объектом ``RepoFolder``, у файла есть ``blob_id``/``size``. Старые версии
    отдавали ``type == "directory"`` — поддерживаем оба вида.
    """
    if type(entry).__name__ == "RepoFolder":
        return True
    kind = getattr(entry, "type", None)
    if isinstance(kind, str) and kind.lower() in ("directory", "dir", "folder"):
        return True
    return getattr(entry, "blob_id", None) is None and not hasattr(entry, "size")


def remote_files(api, repo_id: str) -> dict[str, int]:
    """Карта «путь в репозитории -> размер» для всех ФАЙЛОВ удалённого дерева."""
    files: dict[str, int] = {}
    try:
        entries = list(api.list_repo_tree(repo_id=repo_id, repo_type="dataset",
                                          recursive=True))
    except Exception as exc:  # noqa: BLE001 — репозитория ещё нет
        log(f"  (репозиторий недоступен: {type(exc).__name__})")
        return files
    for entry in entries:
        path = getattr(entry, "path", None)
        if path is None or is_remote_folder(entry):
            continue
        files[path] = getattr(entry, "size", 0) or 0
    return files


def is_stale_path(path_in_repo: str, local: set[str]) -> bool:
    """Путь под ``data/``, которого нет локально и который не защищён."""
    return (path_in_repo.startswith(DATA_PREFIX + "/")
            and path_in_repo not in local
            and not is_protected_path(path_in_repo))


def stale_remote_files(remote: dict[str, int], local: set[str]) -> dict[str, int]:
    """Удалённые файлы под ``data/``, которых нет в локальном целевом наборе."""
    return {path: size for path, size in remote.items() if is_stale_path(path, local)}


def stale_type_ids(stale: dict[str, int], types: list) -> list[str]:
    """Каталоги типов, которые есть на сервере, но которых нет локально.

    Берутся только листовые каталоги устаревших файлов: промежуточные
    (``data``, ``data/out``, ``data/out/<owner>``) — не типы и в лог не идут.
    """
    known = {f"{DATA_PREFIX}/{t.type_id}" for t in types}
    directories = {path.rsplit("/", 1)[0] for path in stale}
    leaves = [directory for directory in directories
              if directory not in known
              and not any(other.startswith(directory + "/")
                          for other in directories)]
    return sorted(leaves)


def type_id_of_dir(directory: str) -> str:
    """``data/out/x/y`` -> ``out/x/y`` (для читаемого лога)."""
    prefix = DATA_PREFIX + "/"
    return directory[len(prefix):] if directory.startswith(prefix) else directory


def create_commit_with_retries(api, repo_id: str, operations: list,
                               label: str) -> None:
    """``create_commit`` с ретраями; ``label`` — сообщение коммита и имя в логе."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            api.create_commit(repo_id=repo_id, operations=operations,
                              repo_type="dataset", commit_message=label,
                              num_threads=NUM_THREADS)
            return
        except Exception as exc:  # noqa: BLE001 — сеть может упасть в любой момент
            last_error = exc
            wait = RETRY_SLEEP * attempt
            warn(f"коммит «{label}» не залился (попытка {attempt}/{MAX_RETRIES}): "
                 f"{type(exc).__name__}: {exc}; жду {wait:.0f} с")
            time.sleep(wait)
    raise RuntimeError(f"коммит «{label}» не залился после {MAX_RETRIES} попыток: "
                       f"{last_error}")


def upload_batch(api, repo_id: str, name: str,
                 items: list[tuple[str, Path]],
                 batch_files: int = DEFAULT_BATCH_FILES) -> int:
    """Залить батч кусками по ``batch_files`` файлов: один кусок = один коммит.

    Возвращает число залитых файлов. В сообщении коммита стоит номер куска
    (``... (1/40)``), чтобы история не превращалась в стомегабайтные коммиты.
    """
    from huggingface_hub import CommitOperationAdd

    chunks = chunked(items, batch_files)
    total = len(chunks)
    uploaded = 0
    for index, chunk in enumerate(chunks, start=1):
        operations = [CommitOperationAdd(path_in_repo=path, path_or_fileobj=local)
                      for path, local in chunk]
        create_commit_with_retries(
            api, repo_id, operations,
            f"CaptchaOCR dataset: {name} ({index}/{total})")
        uploaded += len(chunk)
        log(f"    commit {index}/{total}: {name} — {len(chunk)} files")
    return uploaded


def prune_remote(api, repo_id: str, stale: dict[str, int],
                 batch_files: int = DEFAULT_BATCH_FILES) -> tuple[int, int]:
    """Удалить устаревшие файлы кусками по ``batch_files``: кусок = один коммит.

    Возвращает ``(путей, байт)``. Карточка, сводка, ``LICENSE*`` и
    ``.gitattributes`` сюда не попадают (их отфильтровал ``stale_remote_files``).
    """
    from huggingface_hub import CommitOperationDelete

    paths = sorted(stale)
    chunks = chunked(paths, batch_files)
    total = len(chunks)
    deleted = 0
    deleted_bytes = 0
    for index, chunk in enumerate(chunks, start=1):
        operations = [CommitOperationDelete(path_in_repo=path) for path in chunk]
        create_commit_with_retries(
            api, repo_id, operations,
            f"CaptchaOCR dataset: prune stale files ({index}/{total})")
        deleted += len(chunk)
        deleted_bytes += sum(stale[path] for path in chunk)
        log(f"    commit {index}/{total}: prune — {len(chunk)} files")
    return deleted, deleted_bytes


def upload_metadata(api, repo_id: str, files: dict[str, bytes]) -> None:
    """Залить карточку, сводку, LICENSE и ``.gitattributes``."""
    from huggingface_hub import CommitOperationAdd

    operations = [CommitOperationAdd(path_in_repo=path, path_or_fileobj=data)
                  for path, data in files.items()]
    api.create_commit(repo_id=repo_id, operations=operations, repo_type="dataset",
                      commit_message="CaptchaOCR dataset: card, inventory, license",
                      num_threads=NUM_THREADS)


# =====================================================================================
# Проверка
# =====================================================================================

def verify(api, repo_id: str, types: list) -> int:
    """Сверить удалённое дерево с локальным: PNG, labels.jsonl, размер, коммит."""
    try:
        entries = list(api.list_repo_tree(repo_id=repo_id, repo_type="dataset",
                                          recursive=True))
    except Exception as exc:  # noqa: BLE001
        log("MISMATCH")
        log(f"  - не удалось прочитать удалённое дерево: {type(exc).__name__}: {exc}")
        return EXIT_ERROR

    remote_png = 0
    remote_labels = 0
    remote_bytes = 0
    remote_paths: set[str] = set()
    for entry in entries:
        path = getattr(entry, "path", None)
        if path is None:
            continue
        if is_remote_folder(entry):
            continue
        remote_paths.add(path)
        size = getattr(entry, "size", 0) or 0
        if path.endswith(".png"):
            remote_png += 1
            remote_bytes += size
        elif path.endswith("labels.jsonl"):
            remote_labels += 1
            remote_bytes += size

    local_png = sum(t.inventory["png_files"] for t in types)
    local_labels = len(types)
    local_bytes = sum(t.inventory["bytes"] for t in types) + sum(
        t.labels_path.stat().st_size for t in types)
    local_paths = local_target_paths(types)
    stale_count = sum(1 for path in remote_paths if is_stale_path(path, local_paths))

    try:
        info = api.repo_info(repo_id=repo_id, repo_type="dataset")
        sha = getattr(info, "sha", "?")
    except Exception:  # noqa: BLE001
        sha = "?"

    log(f"repo:            {repo_id}")
    log(f"last commit:     {sha}")
    log(f"remote PNG:      {remote_png}")
    log(f"remote labels:   {remote_labels}")
    log(f"remote bytes:    {remote_bytes} ({ph.human_bytes(remote_bytes)})")
    log(f"local PNG:       {local_png}")
    log(f"local labels:    {local_labels}")
    log(f"local bytes:     {local_bytes} ({ph.human_bytes(local_bytes)})")
    log(f"stale remote paths: {stale_count}")

    # История коммитов: публикация — это ДОБАВЛЕНИЕ, история не переписывается.
    log("")
    log("last commits:")
    try:
        commits = list(api.list_repo_commits(repo_id=repo_id, repo_type="dataset"))
        for commit in commits[:3]:
            message = (getattr(commit, "title", "") or "").splitlines()[0]
            log(f"  {getattr(commit, 'commit_id', '?')}  {message}")
    except Exception as exc:  # noqa: BLE001
        log(f"  (не удалось прочитать историю: {type(exc).__name__}: {exc})")

    problems: list[str] = []
    if remote_png != local_png:
        problems.append(f"PNG: remote {remote_png} != local {local_png}")
    if remote_labels != local_labels:
        problems.append(f"labels.jsonl: remote {remote_labels} != local {local_labels}")
    for extra in ("README.md", INVENTORY_NAME, ".gitattributes"):
        if extra not in remote_paths:
            problems.append(f"missing {extra}")
    for t in types:
        if f"{DATA_PREFIX}/{t.type_id}/labels.jsonl" not in remote_paths:
            problems.append(f"missing {DATA_PREFIX}/{t.type_id}/labels.jsonl")
        missing = [png.name for png in t.pngs
                   if f"{DATA_PREFIX}/{t.type_id}/{png.name}" not in remote_paths]
        if missing:
            problems.append(f"{t.type_id}: {len(missing)} PNG missing "
                            f"(e.g. {missing[:3]})")

    if problems:
        log("MISMATCH")
        for problem in problems[:50]:
            log(f"  - {problem}")
        if len(problems) > 50:
            log(f"  ... and {len(problems) - 50} more")
        return EXIT_ERROR
    log("OK")
    return EXIT_OK


# =====================================================================================
# main
# =====================================================================================

def clamp_num_threads(value: int) -> int:
    """Зажать ``--num-threads`` в ``[MIN_NUM_THREADS, MAX_NUM_THREADS]``."""
    clamped = max(MIN_NUM_THREADS, min(MAX_NUM_THREADS, int(value)))
    if clamped != int(value):
        warn(f"--num-threads {value} вне диапазона "
             f"[{MIN_NUM_THREADS}, {MAX_NUM_THREADS}], использую {clamped}")
    return clamped


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Опубликовать датасет CaptchaOCR на HF Hub (существующий репозиторий).")
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID,
                        help="репозиторий назначения (dataset)")
    parser.add_argument("--data-dir", default=str(REPO_ROOT / "dataset"),
                        help="корень дерева датасета (по умолчанию <repo>/dataset)")
    parser.add_argument("--dry-run", action="store_true",
                        help="напечатать план и выйти, ничего не грузя")
    parser.add_argument("--verify", action="store_true",
                        help="проверить удалённое дерево и выйти")
    parser.add_argument("--prune", action="store_true",
                        help="после заливки удалить из data/ файлы, которых больше нет "
                             "в локальном дереве (устар. типы и лишние PNG)")
    parser.add_argument("--batch-files", type=int, default=DEFAULT_BATCH_FILES,
                        metavar="N",
                        help=f"файлов в одном коммите и в одном куске prune-а "
                             f"(по умолчанию {DEFAULT_BATCH_FILES})")
    parser.add_argument("--num-threads", type=int, default=DEFAULT_NUM_THREADS,
                        metavar="N",
                        help=f"потоков на один коммит (num_threads у create_commit; "
                             f"это же размер пула загрузки LFS). Допустимо "
                             f"{MIN_NUM_THREADS}..{MAX_NUM_THREADS}, по умолчанию "
                             f"{DEFAULT_NUM_THREADS} (у хаба 5)")
    parser.add_argument("--token", default=None, help="HF-токен (иначе из окружения/кэша)")
    parser.add_argument("--private", action="store_true",
                        help="создать репозиторий приватным (по умолчанию — публичный)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    global NUM_THREADS

    args = parse_args(argv)
    data_dir = Path(args.data_dir).resolve()
    if args.batch_files < 1:
        warn(f"--batch-files {args.batch_files} < 1, использую 1")
        args.batch_files = 1
    NUM_THREADS = clamp_num_threads(args.num_threads)

    token = ph.require_token(args.token)
    api = ph.api_for(token)
    user = ph.whoami_name(api)
    log(f"token owner:     {user or '(unknown)'}")
    log(f"repo:            {args.repo_id} (dataset)")
    log(f"data dir:        {data_dir}")

    types = find_types(data_dir)
    collect(types)
    inventory = ph.build_inventory(types, data_dir)
    real_shots, real_shots_files = count_real_shots(data_dir)

    log(f"types found:     {len(types)}")
    log(f"png found:       {sum(t.inventory['png_files'] for t in types)}")
    log(f"labels found:    {len(types)}")
    log(f"real_shots (not published): {real_shots} PNG in {real_shots_files} files")

    # Ни один файл из real_shots не должен попасть в план.
    for t in types:
        assert "real_shots" not in t.type_id.split("/"), t.type_id

    if args.verify:
        return verify(api, args.repo_id, types)

    # Согласованность: в каждом типе число PNG должно совпадать с числом строк меток.
    mismatched = [(t.type_id, t.inventory["png_files"], t.inventory["samples"])
                  for t in types
                  if t.inventory["png_files"] != t.inventory["samples"]]
    for type_id, pngs, rows in mismatched:
        warn(f"тип {type_id}: {pngs} PNG против {rows} строк в labels.jsonl")

    if not args.dry_run:
        # 1. Убедиться, что репозиторий существует (существующий — не создаём новый).
        ph.ensure_repo(api, args.repo_id, "dataset", token, args.private, False, user)

    log("")
    log("=== Дайджесты удалённых файлов ===")
    digests = remote_digests(api, args.repo_id)
    log(f"remote files:    {len(digests)}")
    plan, unchanged = build_plan(types, digests)

    local_paths = local_target_paths(types)
    labels_to_add = sum(1 for _, items in plan.batches for path, _ in items
                        if path.endswith("labels.jsonl"))
    png_to_add = plan.total_files() - labels_to_add
    chunks = plan.chunk_count(args.batch_files)

    stale: dict[str, int] = {}
    stale_dirs: list[str] = []
    stale_bytes = 0
    if args.prune:
        stale = stale_remote_files(remote_files(api, args.repo_id), local_paths)
        stale_dirs = stale_type_ids(stale, types)
        stale_bytes = sum(stale.values())

    log("")
    log("=== План загрузки ===")
    log(f"types:                 {len(types)}")
    log(f"local target paths:    {len(local_paths)}")
    log(f"unchanged (skipped):   {len(unchanged)}")
    log(f"labels to add:         {labels_to_add}")
    log(f"PNG to add:            {png_to_add}")
    log(f"files to upload:       {plan.total_files()}")
    log(f"bytes to upload:       {plan.total_bytes()} ({ph.human_bytes(plan.total_bytes())})")
    log(f"batches:               {len(plan.batches)}")
    log(f"chunks (--batch-files {args.batch_files}): {chunks}")
    log(f"threads per commit: {NUM_THREADS}")
    for name, items in plan.batches[:6]:
        log(f"  - {name}: {len(items)} files")
    if len(plan.batches) > 6:
        log(f"  ... and {len(plan.batches) - 6} more batches")

    if args.prune:
        log("")
        log("=== Prune ===")
        log(f"stale remote paths:    {len(stale)}")
        log(f"stale bytes:           {stale_bytes} ({ph.human_bytes(stale_bytes)})")
        log(f"stale type ids:        {len(stale_dirs)}")
        log(f"prune chunks (--batch-files {args.batch_files}): "
            f"{chunk_count(len(stale), args.batch_files)}")
        for directory in stale_dirs[:50]:
            log(f"  - {type_id_of_dir(directory)}")
        if len(stale_dirs) > 50:
            log(f"  ... and {len(stale_dirs) - 50} more type ids")

    if args.dry_run:
        log("")
        log("DRY RUN: nothing was uploaded, nothing was deleted.")
        return EXIT_OK

    # 2. Карточка, сводка, LICENSE, .gitattributes — одним коммитом.
    labels_bytes = sum(t.labels_path.stat().st_size for t in types)
    card = build_card(inventory, args.repo_id, real_shots, real_shots_files, labels_bytes)
    license_text, leftovers = ph.render_dataset_license(inventory, args.repo_id)
    if leftovers:
        warn("в LICENSE остались плейсхолдеры: " + ", ".join(leftovers))
    inventory_bytes = json.dumps(inventory, ensure_ascii=False, indent=2).encode("utf-8")
    metadata = {
        "README.md": card.encode("utf-8"),
        INVENTORY_NAME: inventory_bytes,
        "LICENSE": license_text.encode("utf-8"),
    }
    # .gitattributes: не трогаем, если на сервере уже есть (это LFS-шаблон хаба).
    if ".gitattributes" not in digests:
        metadata[".gitattributes"] = GITATTRIBUTES_FALLBACK.encode("utf-8")
    log("")
    log("=== Метаданные ===")
    for name, data in metadata.items():
        log(f"  {name}: {len(data)} bytes")
    upload_metadata(api, args.repo_id, metadata)
    log("  uploaded.")

    # 3. Метки (сначала) и PNG (потом, по типам), кусками по --batch-files.
    log("")
    log("=== Данные ===")
    uploaded = 0
    for index, (name, items) in enumerate(plan.batches, start=1):
        uploaded += upload_batch(api, args.repo_id, name, items, args.batch_files)
        log(f"  [{index}/{len(plan.batches)}] {name}: {len(items)} files "
            f"(всего {uploaded}/{plan.total_files()})")

    log("")
    log(f"uploaded {uploaded} files in {chunks} data commits")

    # 4. Prune: удалить устаревшие файлы (после добавлений), кусками.
    if args.prune:
        log("")
        log("=== Prune ===")
        log(f"stale remote paths:    {len(stale)}")
        log(f"stale bytes:           {stale_bytes} ({ph.human_bytes(stale_bytes)})")
        log(f"stale type ids:        {len(stale_dirs)}")
        for directory in stale_dirs[:50]:
            log(f"  - {type_id_of_dir(directory)}")
        if len(stale_dirs) > 50:
            log(f"  ... and {len(stale_dirs) - 50} more type ids")
        deleted, deleted_bytes = prune_remote(api, args.repo_id, stale, args.batch_files)
        log(f"  deleted {deleted} files ({ph.human_bytes(deleted_bytes)}) "
            f"in {chunk_count(len(stale), args.batch_files)} commits")

    # 5. Проверка удалённого дерева.
    log("")
    log("=== Проверка ===")
    return verify(api, args.repo_id, types)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        warn(f"{type(exc).__name__}: {exc}")
        raise SystemExit(EXIT_ERROR)
