# DATASET — где лежит датасет и как его скачать

**Коротко:** 46 типов капчи, 23 000 размеченных PNG (218.2 МиБ), 23 плагина-источника.
Полный датасет лежит на **Hugging Face**, в git-репозитории остались код, разметка и образцы.

| | |
|---|---|
| Типов | **46** — 34 в `dataset/out/`, 12 в `dataset/out_ru/` |
| Размеченных PNG | **23 000** — ровно по 500 на тип |
| Размер (только PNG) | **218.2 МиБ** (228 769 043 Б); с `labels.jsonl` — 224.8 МиБ |
| Плагинов-источников | **23** — 18 в `dataset/out/`, 5 в `dataset/out_ru/` |
| Объединённый алфавит | 129 символов |
| Типов с полосой (`roi`) | 29 из 46 |
| Типов, где `text != answer` | 9 из 46 |
| Эталонных скриншотов (`real_shots/`) | 517 — **не публикуются** (чужие скриншоты) |

## Скачать

```powershell
pip install huggingface_hub
python tools\fetch_dataset.py
```

Скрипт `tools/fetch_dataset.py` качает датасет-репозиторий `Titlehhhh/captchaocr-dataset`
(опубликован 2026-10-22, коммит `6248c5b9b6ce7eb6e917efd7aa3952892beb7cea`:
23 000 PNG + 46 `labels.jsonl`; эталонные скриншоты `real_shots/` на сервер не попали)
в `dataset/full/` (кэш — `HF_HUB_CACHE`/`HF_HOME`, а если общий кэш недоступен — `.hf-cache/`
рядом с репозиторием). Полезные флаги:

```powershell
python tools\fetch_dataset.py --dry-run                       # план, без сети
python tools\fetch_dataset.py --types "haq/mapcha/map" "GalleryCaptcha/ru-symbols"
python tools\fetch_dataset.py --cache-dir .hf-cache           # кэш целиком внутри репозитория
```

`--dry-run` печатает, что именно скачается (46 типов, 23 000 PNG, 218.2 МиБ) и ничего не качает.
Проверено: `python tools\fetch_dataset.py --dry-run` → «types: 46 of 46 known … total : 23000 files,
218.17 MB … dry run: nothing was downloaded, no network request was made».

Без библиотеки тот же набор файлов забирается через `git clone`:

```powershell
git clone https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset dataset/full
```

## Что остаётся в git-репозитории

* генераторы на Java 21 (`dataset/generator/`, `dataset/generator_ru/`) — по ним видно, как
  получена каждая картинка;
* разметка `labels.jsonl` на каждый тип (46 файлов) и `index.html` каждого дерева;
* **образцы**: по 5 картинок на каждый из 46 типов в `dataset/samples/` — 230 PNG, 2.3 МиБ,
  плюс витрина `dataset/samples/index.html`;
* весь код обучения и бенчмарков.

## Почему картинок в репозитории нет

Изначально датасет лежал в git, и история репозитория разрослась до ~142 МБ: git хранит
каждый коммит навсегда, даже если файлы удалить из рабочей копии. Сейчас история переписана —
в git остались только код, разметка и 230 образцов (**10.5 МиБ**, `git count-objects -vH`),
а 23 000 PNG живут отдельно на Hugging Face: там картинки лежат обычными файлами, обновляются
по кускам и качаются по HTTP без git.

Правила `.gitignore` (`dataset/out/**/*.png`, `dataset/out_ru/**/*.png`) убирают 23 000 PNG из
индекса git: `labels.jsonl` и `index.html` остаются отслеживаемыми, а сами картинки живут на
Hugging Face. Заодно из индекса уходят эталонные скриншоты `real_shots/` — чужие скриншоты в
публику не идут.

## Воспроизводимость

Датасет **воспроизводим по типам**: пересборка генераторов даёт те же 46 типов и ту же
разметку. Но **генераторы не засеяны**, так что набор сэмплов каждый раз разный: системные
шрифты AWT те же, а сами случайные значения — новые. Поэтому датасет генерируется один раз и
используется как артефакт.

## Формат данных

Контракт `labels.jsonl`, правило полосы и разница между `text` и `answer` —
[`docs/DATASET_FORMAT.md`](DATASET_FORMAT.md).

## Лицензии данных

Лицензия каждой строки — лицензия плагина-источника, из которого она получена. Подробно —
[`docs/LICENSES.md`](LICENSES.md), таблица плагинов — [`docs/PLUGINS.md`](PLUGINS.md).
