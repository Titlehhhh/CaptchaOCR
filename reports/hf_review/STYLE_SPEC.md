# STYLE_SPEC — карточки CaptchaOCR на Hugging Face

Версия 1.0 · 2026-11-02 · для агентов-переписчиков `dataset_README.md` и `model_README.md`.
Область: только текст и структура; данные, YAML-ключи и числа не меняются.
Проверено по сети: HF docs `model-cards`, `datasets-cards`; карточки Qwen2.5-VL, DeepSeek-OCR,
the_cauldron, DocVQA, TrOCR; API датасета и модели; все 14 badge-URL отдают `200 image/svg+xml`.
Не проверено: санитайзер HF для `<style>` и самодельных якорей — проверять на черновике.

## 1. Принципы

1. **10 секунд.** Первый экран отвечает: что это, сколько этого, насколько хорошо, как запустить.
   Всё остальное — ниже и по желанию.
2. **Один экран — одна мысль.** Не смешивать «что внутри», «как читать метки» и «лицензию».
3. **Число один раз.** Канонический блок чисел (`What's inside` / `Results`); в тексте — словами.
4. **Показать, а не описать.** Картинка captcha убеждает лучше абзаца «this repository holds…».
5. **Честно, но не извиняясь.** «Works on X. Does not work on Y.» вместо «unfortunately, only…».
6. **Читатель, а не автор.** Английский, `you`, императив, предложения ≤ 20 слов.
7. **Внутреннее — приватно, длинное — свёрнуто.** Никаких `C:\Users\...`, `train/runs/...`,
   `.venv-gpu`, `reports/...`, истории «прошлая карточка была неверной»; хвост — в `<details>`.

## 2. Карточка ДАТАСЕТА

| # | Раздел | Цель | Макс. строк |
|---|---|---|---:|
| 0 | YAML front matter | попасть в фильтры, включить viewer, лицензия | 18 |
| 1 | Hero + badges | картинка шести типов + 6–7 статичных badge | 8 |
| 2 | `# CaptchaOCR — …` + one-liner | что это и что получает читатель | 4 |
| 3 | `## What's inside` | 3–4 числа: типы, сэмплы, плагины, размер | 8 |
| 4 | `## Gallery` | 4–6 примеров с ответом под каждым | 14 |
| 5 | `## Quickstart` | 5 строк кода, которые точно работают | 10 |
| 6 | `## Fields` | 13 колонок, одна строка на поле | 18 |
| 7 | `## Types` | таблица 20 типов в `<details>` | 28 |
| 8 | `## Reading the labels` | `text` vs `answer`, `roi = null` — по разу | 8 |
| 9 | `## License` | mixed-per-plugin, куда смотреть | 4 |
| 10 | `## Provenance` | 4 факта происхождения | 8 |
| 11 | `## Limitations` | 3–5 ограничений | 8 |
| 12 | `## Citation` (опционально) | как ссылаться | 5 |

**Первый экран:** hero, название, one-liner, badges, 4 строки «What's inside»; таблиц и кода нет.
Сейчас первым экраном идёт byte-массив `[137, 80, 78, …]` из viewer — это и надо исправить.

**YAML — минимум, который реально работает** (проверено на живом датасете):

```yaml
---
license: other
license_name: mixed-per-plugin-licences
license_link: https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/blob/main/LICENSE
pretty_name: CaptchaOCR — Minecraft anti-bot captchas
task_categories: [image-to-text]
language: [en, ru]
tags: [captcha, ocr, minecraft, anti-bot, synthetic, parquet, image, datasets]
size_categories: 100K<n<1M
configs:
- config_name: default
  data_files: data/*.parquet
---
```

`modality` — **тег** `image`, а не отдельный ключ. Сейчас `modality: image` стоит верхним уровнем,
и страница показывает `Modalities: Tabular · Text`; тег `image` это исправляет.

**Что писать по разделам.** `What's inside` — 20 типов / 13 плагинов, 200 000 изображений, 12 типов
с `roi`, 9 шардов и 1.9 GiB. `Gallery` — 6 кропов с ответом в подписи (`Krypton/map — WU43b`).
`Quickstart` — `load_dataset`, `row["answer"]`, строка про `io.BytesIO`. `Fields` — 13 строк,
`roi` = `[x, y, w, h]`. `Types` — 20 строк в `<details><summary>All 20 types</summary>`, снаружи
только «20 types from 13 plugins». `Reading the labels` — два абзаца, **не** два H2. `Limitations` —
синтетика, не seeded, `roi` нет у 8 типов, 3 типа требуют solver-шага.

## 3. Карточка МОДЕЛИ

| # | Раздел | Цель | Макс. строк |
|---|---|---|---:|
| 0 | YAML front matter | `library_name`, `pipeline_tag`, `base_model`, `datasets` | 20 |
| 1 | Hero + badges | пример «картинка → строка» + 7–8 badge | 8 |
| 2 | `# CaptchaOCR PP-OCRv6 — …` + one-liner | что читает и на чём обучено | 4 |
| 3 | `## Use it in 10 lines` | рабочий вызов без ручной сборки головы | 14 |
| 4 | `## What it supports` | таблица «поддерживает / не поддерживает» | 12 |
| 5 | `## Results` | median/micro + 6 held-out плагинов | 20 |
| 6 | `## Limitations` | 3–5 пунктов, без самобичевания | 8 |
| 7 | `## Training` в `<details>` | рецепт, железо, время | 18 |
| 8 | `## Dataset` | 3 строки + ссылка | 5 |
| 9 | `## License & citation` | база Apache-2.0, производная | 6 |

**Первый экран:** hero (кроп → ответ), название, one-liner, badges, строки `Use it`. Блока «эта
карточка описывает другой чекпойнт» здесь нет — он в `<details>Version history</details>` в конце.

**YAML** оставить как есть (страница уже показывает `Base model`, `Dataset used to train`, `19.2M
params`); сохранить `library_name`, `pipeline_tag`, `base_model`, `datasets`, `license`. `widget:` —
только если он реально запускается; для кастомной архитектуры лучше без него.

**`Use it in 10 lines`** — обёртка, а не 30 строк `model.head.head(...)`. Ручной forward и
greedy-декодирование — в `<details>Manual CTC decoding</details>`. `What it supports` — «Supports»
(12 trained types, band or frame, Latin + Cyrillic) и «Does not support» (3 number-word types, unseen
styles, screenshots without a cropper). `Results` — 4 агрегата и 6 held-out строк, per-type таблица
на 12 строк в `<details>`. `Limitations` не повторяет `Does not support`: протокол и худшие типы.

## 4. Badges

Статичные shields.io: `label-message-color`, пробел → `_`, дефис → `--`, запятая → `%2C`,
процент → `%25`. Никаких динамических badge (`/github/...`, `/pypi/...`) — они ломаются и врут.

**Датасет — 7 штук, одна строка:**

```markdown
![samples](https://img.shields.io/badge/samples-200%2C000-blue)
![types](https://img.shields.io/badge/captcha_types-20-blueviolet)
![plugins](https://img.shields.io/badge/upstream_plugins-13-informational)
![size](https://img.shields.io/badge/size-1.9_GiB-lightgrey)
![format](https://img.shields.io/badge/format-Parquet-150458)
![task](https://img.shields.io/badge/task-image--to--text-success)
![license](https://img.shields.io/badge/license-mixed_per_plugin-orange)
```

По порядку: samples — строки; types — типы; plugins — апстримы; size — вес; format — Parquet; task — задача; license — правовой режим. Все — из `What's inside`.

**Модель — 8 штук:**

```markdown
![base](https://img.shields.io/badge/base-PP--OCRv6_medium_rec-0b5cad)
![params](https://img.shields.io/badge/params-19.2M-informational)
![classes](https://img.shields.io/badge/CTC_classes-18%2C762-blueviolet)
![median](https://img.shields.io/badge/median_exact-88.75%25-brightgreen)
![cer](https://img.shields.io/badge/median_CER-3.44%25-green)
![heldout](https://img.shields.io/badge/held--out_plugins-6-yellow)
![license](https://img.shields.io/badge/license-Apache--2.0-blue)
![task](https://img.shields.io/badge/task-image--to--text-success)
```

По порядку: base — от чего; params — размер; classes — словарь; median — exact; cer — ошибка; heldout — протокол; license — Apache-2.0; task — задача. `%25` → `%`, голый `%` нельзя.

## 5. Hero и галерея

- **Hero:** 1600 × 600 px, PNG/JPG, ≤ 400 КБ, без мелкого текста. 4–6 кропов разных типов в ряд +
  подпись «20 types · 13 plugins»; читается на тёмном и светлом фоне.
- **Галерея:** 4–6 кропов 256 × 256, ширина 160–180 px, 3 в ряд на десктопе / 2 на мобильном.
  Под каждым — ответ: `WU43b`, `30y34`, `6Ch50`.
- **Хостинг:** файлы в репозитории **датасета**: `assets/hero.png`, `assets/gallery/01-krypton-map.png`.
  Галерея — не строки датасета: `image` в Parquet имеет тип `binary`, viewer показывает
  `[137, 80, 78, …]`, а не миниатюру (проверено через `first-rows`).
- **URL:** всегда `https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/resolve/main/assets/hero.png`.
  `blob/main/...` в `<img>` нельзя — это HTML-страница. Относительный путь работает только внутри
  своего репозитория; в карточке модели он уедет в репозиторий модели.
- **Подпись:** `alt` описывает содержимое («Six Minecraft captcha styles: map, code, symbols»), а не
  «image». Файлы не перезаписывать под тем же именем — CDN кеширует; новая версия = новое имя.

## 6. Подводные камни HF

- **YAML ломает всё молча.** Одна кривая кавычка — и карточка не рендерится, метаданные исчезают.
  Проверка: открыть `?raw=true`, front matter должен быть первыми строками.
- **`library_name` + `pipeline_tag`** включают виджет и «Use this model»; без них модель не
  фильтруется по задаче. `base_model` и `datasets` дают боковые ссылки (у нас уже работают).
- **Dataset viewer** читает `configs`/`data_files`; `binary`-колонка не становится картинкой,
  `Image`-feature стала бы, но это пере-экспорт (не проверено; не в этой задаче).
- **`<details>`/`<summary>` поддерживаются** (Qwen2.5-VL, the_cauldron); `<img>`, `<div align>`,
  `<sub>` работают. `<script>`, `<iframe>`, `<style>`, inline-CSS санитайзер вырезает (не проверено).
- **Якоря и ссылки:** заголовки получают auto-id, самодельные `<a name>` могут вырезаться — TOC не
  нужен. Относительные ссылки работают только внутри своего репозитория, межрепозиторные — полный URL.
- **Таблицы:** 20 строк всегда развёрнуты; длинные — в `<details>`. `|` экранировать `\|`, строки
  кода держать ≤ 88 символов. **`license: other`** требует `license_name` **и** `license_link`.
- **Не обещать inference и не добавлять `model-index`:** наша архитектура не запускается в
  «Inference Providers», а неверные поля eval-виджета врут сильнее таблицы.

## 7. Тон и язык

- Английский, `you`, активный залог: «Feed it a crop of the answer band», а не «A crop is fed».
- Одно предложение — одна мысль; ≤ 20 слов; абзац ≤ 3 предложений.
- Числа — только в `What's inside`/`Results`; в тексте «twenty types». `grep -c "200,000"` и
  `grep -c "0.8875"` по карточке должны давать 1.
- Запрещены внутренние пути, имена прогонов (`universal_v1`, `limbo_cyr3` — только в Training),
  `reports/...`, `train/runs/...`, `C:\`, `.venv-gpu`, `--limit-per-type`; CAPS-абзацы,
  «we measured», «our own», «honest numbers», «not a universal solver» чаще одного раза.
- Ограничения — фактом и с областью: «On unseen plugin styles, exact match ranges from 0.57 to 0.98.»
  Не «it fails badly», не «unfortunately».
- Термины при первом употреблении: `roi` (the answer band), CTC (character-level decoder),
  held-out (plugin never seen in training); кириллица и `type_id` — в `code`.

## 8. Разобранные примеры

| Карточка | URL | Что взять |
|---|---|---|
| Qwen2.5-VL-7B-Instruct | https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct | ряд badge сразу под именем; `<details>` для multi-image/batch; «Quickstart» отдельно от деталей |
| DeepSeek-OCR | https://huggingface.co/deepseek-ai/DeepSeek-OCR | центрированный hero, одна строка позиционирования, минимум кода до первого результата |
| the_cauldron (dataset) | https://huggingface.co/datasets/HuggingFaceM4/the_cauldron | hero, один абзац описания, load-команда, пример записи, stats-таблица, `<details>` ссылок, лицензия абзацем |
| TrOCR base handwritten | https://huggingface.co/microsoft/trocr-base-handwritten | `widget.src` с примерами; короткий блок «Intended uses & limitations» |
| DocVQA (dataset) | https://huggingface.co/datasets/lmms-lab/DocVQA | корректные `dataset_info` + `configs`; прозу не копировать — она тонкая |

Общее у сильных: картинка/бейджи в первом экране, короткий «how to use», числа в таблице, длинное
свёрнуто. Лицензия и ограничения у всех мелким шрифтом — у нас это сильная сторона, но не первый экран.

## 9. Анти-паттерны (что убрать из текущих карточек)

**`dataset_README.md`:** 33–34 — история прошлого релиза → `<details>Version history`. 38–48 — таблица
шардов до схемы → «9 shards · 1.9 GiB». 72–115 — 44 строки загрузки → 5 строк + `<details>`. 118–134 —
`roi`/`text` двумя H2 → один `Reading the labels`. 136–162 — таблица 20 типов всегда открыта → `<details>`.
Строка 17 — `modality: image` верхним уровнем → тег `image` (сейчас страница показывает Tabular/Text).
Первый экран — байты `[137, 80, 78, …]` вместо картинок → hero и галерея.

**`model_README.md`:** 27–30 — blockquote про прошлый чекпойнт → конец, `<details>Version history`.
32–56 — таблица файлов на первом экране → свернуть. 73–123 — числа прогона → `<details>Training`.
183–206 — эссе про α → 4 строки + `<details>`. 225–253 — 30 строк `model.head.head(...)` → обёртка,
ручной forward в `<details>`. 314–344 — PowerShell с `C:\Users\Title\...` → убрать локальные пути.
18 762 — 6 раз, `0.8875` — 2 раза → по одному. 344 строки → цель ≤ 170.

## 10. Чек-лист приёмки

- [ ] Первый экран: hero виден без прокрутки, таблиц и кода нет.
- [ ] Название + one-liner ≤ 25 слов; задача понятна без знания проекта.
- [ ] 5–8 статичных badge; каждый URL отдаёт `image/svg+xml`, числа есть в `What's inside`/`Results`.
- [ ] Все картинки — абсолютные `/resolve/main/`, не `/blob/`; `alt` осмысленный.
- [ ] Галерея 4–6 примеров, под каждым ответ; нет `[137, 80, …]` как «примера».
- [ ] `Quickstart` ≤ 10 строк и запускается копипастом.
- [ ] Поля — одна таблица ≤ 13 строк; 20 типов — в `<details>`; `text != answer` и `roi = null` — по разу.
- [ ] Лицензия ≤ 3 строк, `license_name` совпадает с `license`, ссылка на LICENSE живая.
- [ ] Нет `C:\`, `.venv-gpu`, `train/runs/`, `reports/`, названий прогонов вне `<details>`.
- [ ] `grep` по каждому ключевому числу даёт ровно одно вхождение.
- [ ] `Limitations` — 3–5 пунктов, с областью и числом, без «unfortunately» и без рекламы.
- [ ] Все `<details>` закрыты; карточка читается на 390 px; YAML парсится; у модели верные
      base/dataset/params, у датасета — тег `image`.
