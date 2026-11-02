# Публикация карточек и ассетов на Hugging Face — 2026-11-02

Агент №7. Загрузка выполнена с `HfApi(token=...)` (`.venv-gpu\Scripts\python.exe`,
`huggingface_hub 1.33.0`), токен из `.hf-cache/token`, `HF_HOME` = `.hf-cache`.
Порядок из брифа соблюдён: **ассеты → README датасета → README модели**.
Каждый файл — отдельный коммит, сообщения по-английски.

Итог: **10 коммитов** (8 ассетов + 2 карточки), все 8 URL картинок отдают `200 image/png`
побайтово равные локальным файлам, обе карточки на хабе **посимвольно** равны локальным,
все 14 badge-URL отдают `200 image/svg+xml`, 404 нет ни одного, dataset viewer после
≈9 минут переиндексации поднялся (`viewer: true`, 200 000 строк, 13 колонок).

## 1. Коммиты

Шаг 1 — ассеты в `Titlehhhh/captchaocr-dataset` (repo_type `dataset`), 8 файлов, 8 коммитов:

| файл в репозитории | локальный файл | байт | коммит |
|---|---|---:|---|
| `assets/hero.png` | `build/hf_assets/hero.png` | 134 484 | `1cac1c7cf570edf5a3552f8daa6537dc2f35b37b` |
| `assets/model_hero.png` | `build/hf_assets/model_hero.png` | 84 072 | `06c85bb300870a72092074860668d1882ad1273a` |
| `assets/gallery/01.png` | `build/hf_assets/gallery/01.png` | 6 293 | `8fc2a6d6d64b93b2aff91bab4f99432a1bf117da` |
| `assets/gallery/02.png` | `build/hf_assets/gallery/02.png` | 33 316 | `fbccdce74b65e938e1975f596a24da7bd0254b83` |
| `assets/gallery/03.png` | `build/hf_assets/gallery/03.png` | 21 566 | `363df851dc2c209c45dc504b49c49d63f4081b8f` |
| `assets/gallery/04.png` | `build/hf_assets/gallery/04.png` | 38 726 | `33cc8d822c2e94acc260168ca4a3edfc891d1fc1` |
| `assets/gallery/05.png` | `build/hf_assets/gallery/05.png` | 12 458 | `02c851508af522432ac0feb919981ff7ee653b8f` |
| `assets/gallery/06.png` | `build/hf_assets/gallery/06.png` | 22 665 | `7a3d9cf324ce14cd259261db8f97c9c771de38ad` |

Шаг 2 — README датасета, источник `build/hf_assets/dataset_README.preview.md` (10 797 Б):

| коммит | файл |
|---|---|
| `bea8f13286cb6882362810f3869bda6bd66ebedc` | `README.md` (датасет) |

Шаг 3 — README модели, источник `train/MODEL_CARD.md` (8 403 Б):

| коммит | файл |
|---|---|
| `93fab1117d231e6abac2a4f2d8b45ed9685d7c6d` | `README.md` (модель) |

Время коммитов по данным API: 11:10:35 … 11:11:13 UTC (HF отдаёт UTC).
Текущие head: датасет `bea8f13286cb…`, модель `93fab1117d23…`.

## 2. Область изменений (доказательство, что чужое не тронуто)

Сравнение дерева блобов через `GET /api/datasets/…/tree/<rev>?recursive=true`
между прежним `dd4d7479a95f…` и текущим `main`:

- **добавлено 8 файлов** — `assets/hero.png`, `assets/model_hero.png`, `assets/gallery/01..06.png`;
- **изменён 1 файл** — `README.md`;
- **удалено 0**;
- **14 защищённых файлов совпадают по oid**: `LICENSE`, 9 × `data/train-0000N-of-00009.parquet`,
  `dataset_inventory.json`, 3 × `gallery/sheet_0N.png`. Ни байта не изменилось.

Файлы модели не тронуты вообще: в репозитории модели изменён только `README.md`,
`model.safetensors`, `config.json`, `preprocessor_config.json`, `processor_config.json`,
`character_list.txt`, `finetune_meta.json` — прежние.

## 3. URL → HTTP статус

Замер: `requests` с токеном, редиректы разрешены, сначала `HEAD`, при 403/405 — `GET`.
Итоговый прогон: **26 URL, 0 неудачных** (2 README + `LICENSE` + 8 ассетов + 14 badge + viewer);
PNG дополнительно проверены по сигнатуре `\x89PNG`, а не только по `content-type`.

| URL | статус | content-type |
|---|---|---|
| `…/datasets/Titlehhhh/captchaocr-dataset/raw/main/README.md` | 200 | text/plain |
| `…/Titlehhhh/captchaocr-ppocrv6/raw/main/README.md` | 200 | text/plain |
| `…/datasets/…/resolve/main/assets/hero.png` | 200 | image/png |
| `…/datasets/…/resolve/main/assets/model_hero.png` | 200 | image/png |
| `…/datasets/…/resolve/main/assets/gallery/01.png` | 200 | image/png |
| `…/datasets/…/resolve/main/assets/gallery/02.png` | 200 | image/png |
| `…/datasets/…/resolve/main/assets/gallery/03.png` | 200 | image/png |
| `…/datasets/…/resolve/main/assets/gallery/04.png` | 200 | image/png |
| `…/datasets/…/resolve/main/assets/gallery/05.png` | 200 | image/png |
| `…/datasets/…/resolve/main/assets/gallery/06.png` | 200 | image/png |
| `…/datasets/…/resolve/main/LICENSE` | 200 | text/plain |
| `…/datasets/…/resolve/main/data/train-00000-of-00009.parquet` (HEAD) | 200 | application/octet-stream |

Badge-URL — 14 уникальных, все `200 image/svg+xml` (7 из карточки датасета, 7 из карточки модели):

```
samples-200%2C000-blue            captcha_types-20-blueviolet       upstream_plugins-13-informational
size-1.9_GiB-lightgrey            format-Parquet-150458             task-image--to--text-success
license-mixed_per_plugin-orange   base-PP--OCRv6_medium_rec-0b5cad  params-19.2M-informational
CTC_classes-18%2C762-blueviolet   median_exact-88.75%25-brightgreen median_CER-3.44%25-green
held--out_plugins-6-yellow        license-Apache--2.0-blue
```

**404 среди картинок и badge — ни одного.** Ассеты не просто отдают 200: скачанный файл
**побайтово равен** локальному (сверка `sha256`, все 8 — `identical: true`, `image/png`).

## 4. README на хабе == локальный

| репозиторий | локально | на хабе | sha256 (оба) | посимвольно |
|---|---:|---:|---|---|
| датасет | 10 797 Б | 10 797 Б | `edf57ee7661a7eed…` | да |
| модель | 8 403 Б | 8 403 Б | `4bbae8cf472bbefd…` | да |

Перевод строк **совпадает**: оба файла локально и на хабе в LF, `\r\n` нет ни в одном
(`crlf_local: false`, `crlf_remote: false`). То есть совпадение буквальное, не «после нормализации».

YAML front matter парсится у обеих карточек (`yaml.safe_load`):

- датасет: `license: other`, `license_name: mixed-per-plugin-licences`, `task_categories: [image-to-text]`,
  `tags: [captcha, ocr, minecraft, anti-bot, synthetic, parquet, image]`, `size_categories: 100K<n<1M`,
  `configs: [{config_name: default, data_files: data/*.parquet}]`;
- модель: `license: apache-2.0`, `library_name: transformers`, `pipeline_tag: image-to-text`,
  `datasets: [Titlehhhh/captchaocr-dataset]`,
  `base_model: [PaddlePaddle/PP-OCRv6_medium_rec_safetensors]`.

## 5. API хаба — фактические значения

`GET https://huggingface.co/api/datasets/Titlehhhh/captchaocr-dataset`:

| поле | значение | требуется | ок |
|---|---|---|---|
| `cardData.license_name` | `mixed-per-plugin-licences` | то же | да |
| `cardData.tags` | содержит `image` | содержит | да |
| `cardData.size_categories` | `100K<n<1M` | то же | да |
| `cardData.task_categories` | `["image-to-text"]` | — | — |
| `sha` | `bea8f13286cb…` | — | — |

`GET https://huggingface.co/api/models/Titlehhhh/captchaocr-ppocrv6`:

| поле | значение | требуется | ок |
|---|---|---|---|
| `cardData.base_model` | `["PaddlePaddle/PP-OCRv6_medium_rec_safetensors"]` | непусто | да |
| `cardData.datasets` | `["Titlehhhh/captchaocr-dataset"]` | непусто | да |
| `pipeline_tag` | `image-to-text` | то же | да |
| `library_name` | `transformers` | то же | да |
| `safetensors.total` | `19 186 154` (все F32) | 19 186 154 | да |

Все восемь утверждений — `true` (проверка скриптом, не глазами).

## 6. Скриншоты «после»

Снято headless Edge (`--headless=new`, `--force-device-scale-factor=1`, `--hide-scrollbars`,
`--virtual-time-budget=20000`), отдельный профиль `%TEMP%\edge-hfpub`, не профиль живого браузера.
Файлы: `reports/hf_review/shots/after-{dataset,model}-{desktop,mobile}.png`.

| файл | размер кадра | что видно |
|---|---|---|
| `after-dataset-desktop.png` | 1440×3000 | сверху viewer (Split train · 200k rows, 13 колонок, первые строки `Wu43b`, `30y34`, `3d4D9`, `0Ch58`), ниже hero (шесть стилей, `Wu43b`, `Captcha … ly8r`, `5dqnZ9`, схема, `eVejm`, `AYKZB`), строка из 7 badge, заголовок и лид, затем галерея 6 картинок с подписями `тип — ответ` |
| `after-model-desktop.png` | 1440×3000 | hero «кадр → полоса по `roi` → декодированное `ly8r`», ряд из 8 badge, затем Results: таблица median/micro и таблица невиданных плагинов |
| `after-dataset-mobile.png` | 390×2000 | viewer с 200k rows, ниже hero и badge-ряд, галерея начинается в кадре |
| `after-model-mobile.png` | 390×2000 | hero «кадр → полоса → `ly8`» и badge-ряд видны |

Проверено по пикселям, а не по HTML:

- **hero виден** на всех четырёх — картинки отрисованы, не пустые рамки;
- **галерея видна** на десктопе датасета целиком (6 из 6, подписи `Krypton/map — Wu43b` …
  `CaptchaVerifyZ/map — AYKZB`), на мобильном — начало;
- **битых картинок нет**: ни одной иконки «сломанного изображения», ни пустого места под `<img>`;
- **badge-ряд на месте**: 7 у датасета, 8 у модели, все отрисованы в цвете;
- **карточка начинается не с таблицы и не с кода**: у датасета первым идёт hero, за ним заголовок,
  лид и badge; у модели — hero, затем заголовок и badge, код начинается только в разделе
  «Use it in 10 lines» (y≈520). Первая таблица у модели — в «What it supports» (y≈900).

Оговорка про датасет: **самую верхнюю часть страницы занимает не карточка, а dataset viewer** —
это хром хаба, он показывается над карточкой у любого датасета с живым viewer'ом и карточкой
не управляется. До публикации на его месте стояла плашка «The dataset viewer should be available
soon», то есть место было тем же. Карточка начинается с hero на y≈600.

Мобильный кадр обрезан справа — **это свойство хаба, а не карточки**: Hub держит ширину
layout ≈600 px и при 390 не переразлагается, в кадре остаётся левая часть. То же самое
зафиксировано в `reports/hf_review/SHOTS.md` (строки 88–90) на прошлой, ещё не опубликованной
версии карточки — значит поведение не изменилось от нашей правки. На мобильном Hub также
ставит сайдбар (Downloads, Safetensors, Tree) **выше** карточки, поэтому у модели hero начинается
около y≈1100, а у датасета ещё ниже — под viewer'ом (y≈1600); порядок задаёт Hub, карточка на
него не влияет.

## 7. Dataset viewer

**Жив, проверено после публикации.** Между коммитом и готовностью viewer'а прошло ≈9 минут
переиндексации: у датасета сменился revision (`dd4d7479…` → `bea8f132…`), а viewer пересобирает
конфиг на каждый новый revision.

Состояние в процессе (честный лог, чтобы было видно, что «сразу после» он был не готов):

```
16:14:45  is-valid   → 200 {"preview":false,"viewer":false,"search":false,"filter":false,"statistics":false}
16:15:07  info       → 200 {"dataset_info":{},"pending":[{"kind":"config-info","config":"default",…}],"failed":[]}
16:15:08  first-rows → 500 {"error":"The server is busier than usual and the response is not ready yet. Please retry later."}
```

`pending` без `failed` — очередь пересборки, а не ошибка карточки. Сервис при этом был жив:
контрольные `is-valid` для `stanfordnlp/imdb` и `nyu-mll/glue` в то же время отдавали
`200 {"viewer":true,…}`.

Состояние после готовности:

```
16:20:29  is-valid   → 200 {"preview":true,"viewer":true,"search":false,"filter":false,"statistics":false}
16:20:39  first-rows → 200, 180 412 Б, 100 строк
          features: [image, file, type_id, plugin, captcha, answer, text, prompt, roi, width, height, source, tree]
          row0:   type_id out/Archy-X/Krypton/map, answer Wu43b, text Wu43b, roi [42,70,29,8], 128×128
          row99:  answer 2tBoU, type out/Archy-X/Krypton/map
16:20:40  size       → 200 num_rows 200 000, num_columns 13, parquet 2 047 757 145 Б
```

Строки есть, 13 колонок на месте, `image` приходит как байты PNG (`137, 80, 78, 71, …`).
`first-rows` не отдаёт `num_rows_total` в этом ответе — общее число строк берётся из `size`
(200 000). `search`/`filter`/`statistics` пока `false` — это отдельные возможности viewer'а,
они досчитываются позже; для «viewer жив» достаточно `preview`/`viewer` = `true`, что и получено.
Скриншоты в разделе 6 пересняты **после** этого момента и показывают уже живую таблицу.

## 8. Что не проверено

- **Анонимный доступ.** Все проверки шли с токеном и с этой машины; как страница и ассеты
  отдаются незалогиненному посетителю из другого региона, не проверялось (CDN-кэш не обойдён).
- **`search` / `filter` / `statistics` viewer'а** на момент замера `false`. Это отдельные
  возможности, они досчитываются позже; проверено только `preview`/`viewer`.
- **Мобильный кадр 390** снят в Edge без touch-эмуляции (UA десктопный). Layout при этом
  мобильный (одна колонка), но это не настоящий телефон — как в `SHOTS.md`, строка 202.
- **Firefox/Safari** не проверялись.
- **Светлая тема** отдельно не снималась: кадры сделаны в тёмной теме Hub.
- **Карточки на узких экранах** обрезаны справа (см. раздел 6) — проверено только то, что
  обрез идёт от Hub, а не от нашей разметки; как это лечится, не выяснялось.

## 9. Расхождения и замечания

1. Первый прогон проверки дал `404` на `https://huggingface.co/Titlehhhh/captchaocr-dataset/raw/main/README.md`
   — это **ошибка моего скрипта**, а не хаба: у датасетов raw-URL живёт под `/datasets/`.
   С правильным префиксом — `200` и побайтовое совпадение. В таблице раздела 3 стоит правильный URL.
2. Все 8 ассетов загружены отдельными коммитами (как требовал бриф «по одному `upload_file`»),
   поэтому «три шага» — это 10 коммитов, а не 3. Логические шаги и их SHA перечислены в разделе 1.
3. Каталог `assets/` на хабе новый; прежние `gallery/sheet_01..03.png` не тронуты и по-прежнему
   лежат отдельно — карточка на них больше не ссылается, но и не удаляет их.
4. **Viewer был не готов ≈9 минут** (коммит карточки — 16:11 по локальным часам, `viewer: true` —
   16:20).
   Это штатная переиндексация нового revision, но она выглядит как поломка: страница показывает
   «The dataset viewer should be available soon», а `first-rows` отдаёт 500 с текстом «busier than
   usual». Если проверять сразу после публикации — легко принять за регресс карточки; проверять
   нужно через `is-valid`, где видно `pending` без `failed`.
