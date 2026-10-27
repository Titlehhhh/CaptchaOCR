# Отчёты CaptchaOCR — указатель (27.10.2026)

> Это **указатель**, а не пересказ: по каждому файлу — одна строка: **что меряет**, **когда измерено**,
> **актуален или архив**, **где первоисточник**. Числа живут в измеренных файлах; здесь — ссылки на них.
>
> В командах внутри отчётов пути — те, что были на машине автора; для переносимых версий см.
> `docs/HOW_TO_TRAIN.md`.

---

## Где мой отчёт

**Открыть `reports/HTML/index.html`** — это тот самый один browsable-отчёт: контакт-листы типов
датасета, таблицы моделей, все измеренные числа и пошаговая инструкция «как запустить самому».
Он **собирается скриптом** (`reports/HTML/make_gallery.py`), а не пишется руками.

Всё остальное в `reports/` — либо **измеренные результаты** (JSON, который нельзя править руками),
либо отчёты отдельных сессий. Всё, что заменено более свежим измерением или больше не описывает
состояние проекта, лежит в `reports/archive/` (карта — в `reports/archive/README.md` и в
`reports/archive/2026-10-27-cleanup/README.md`).

## Главные числа (на сейчас)

| что | значение | где измерено |
|---|---|---|
| Датасет на диске | **21 тип × 10 000 = 210 000 PNG** (12 в `dataset/out`, 9 в `dataset/out_ru`) + 517 эталонных скриншотов (не публикуются) | `dataset/out/`, `dataset/out_ru/` |
| Датасет на Hugging Face | **20 типов / 200 000 PNG** в parquet, репозиторий `Titlehhhh/captchaocr-dataset`, коммит `dd4d7479…`; тип `out_ru/LimboFilter/digits` **ещё не опубликован** | `reports/HF_DATASET_UPLOAD.md` (публикация 22.10) + состояние репозитория, проверенное 27.10 |
| Модель опубликована | `Titlehhhh/captchaocr-ppocrv6` = **`universal_v1`**: веса `27eb6fec…` (26.10), карточка `37556a88…` (27.10), 8 файлов, 77 128 999 Б; голова на 18 762 класса, **без интерполяции весов** (α = 1.0) | `train/MODEL_CARD.md`, `HANDOVER.md`; **в `reports/` отчёта о текущей публикации нет** (см. `HF_MODEL_UPLOAD.md` ниже) |
| Опубликованная `universal_v1` (18 типов / 11 400 примеров, 6 удержанных) | median exact **0.8875**, CER 0.0344, micro **0.7797**, CER 0.0755 (нулевой шаг: median 0.875, micro 0.6499) | `train/runs/ppocrv6/universal_v1/result.json`, `reports/TRAINING_LIMBO_DIGITS.md` §8 |
| Кроппер («глаз» перед моделью) | **6/6** на скриншотах владельца; на 840 сэмплах: oracle **69 %**, кроппер **62 %**, весь кадр **44 %** | `reports/CROPPER.md` §2.2 |
| Лучшая чужая модель по полосе | PP-OCRv6_medium_rec — **0.552** exact (micro, 29 типов с полосой); по целому кадру — **0.035** | `reports/bench_models/ppocrv6-medium.json` |
| Наш CRNN+CTC с нуля (невиданные плагины) | **0.381** micro / 0.372 median (4 удержанных типа, 1 999 картинок) | `reports/TRAINING_CRNN_BIG.json` |
| Дообучение PP-OCRv6 (WiSE-FT α = 0.4) | нулевой шаг 0.588 median → 0.480 → **0.638 / 0.612 micro** | `reports/TRAINING_PPOCR_V6_BIG.json` |

---

## Правила папки — как отчёт попадает в репозиторий

1. **Измеренный результат не правится руками** (AGENTS.md §8). Чтобы «улучшить» модель, замер
   переигрывают и кладут **новый** файл. JSON в `reports/` можно **перемещать** (в архив) — но не
   редактировать: ни байта.
2. **Новый отчёт → строка в этом файле**: что меряет, дата измерения, актуален ли, где первоисточник.
3. **Отчёт, который заменён более свежим измерением** (или больше не описывает состояние проекта) →
   `reports/archive/<дата>-<тема>/` через `git mv` + строка в `reports/archive/<папка>/README.md`.
   История файла сохраняется: `git log --follow <путь>`.
4. **Вывод скрипта, который воспроизводится, в git не лежит** — ровно как картинки датасета
   (ADR 0004). Пример: `reports/HTML/img/t/**` — это копии сэмплов датасета, которые делает
   `make_gallery.py`; они исключены из git (`reports/HTML/img/t/.gitignore`), на машине владельца
   остаются, и `index.html` открывается полностью. Восстановить в свежем клоне:
   `git checkout <commit>^ -- reports/HTML/img/t` (см. `.gitignore` в этой папке).
5. **Отчёт, на который ссылается живой документ** (`HANDOVER.md`, `AGENTS.md`, `docs/`, `agents/`,
   `README.md` или код), **в архив не уезжает**, даже если его числа устарели: перенос сломал бы
   ссылку в документе, который править нельзя. В указателе такой отчёт помечен «устарел, но остаётся»
   — с причиной.
6. **Дата измерения** — это когда получены числа, а не когда правили файл. У отчёта без измерения
   (апстрим-разбор, обзор) в графе даты — дата исследования.
7. **Отчёт без первоисточника — не отчёт.** Либо числа, либо документ, который можно перечитать.

---

## A. Живые отчёты — актуальны

| файл | что меряет / что это | дата | состояние | первоисточник |
|---|---|---|---|---|
| `HTML/index.html` | **сводный browsable-отчёт владельцу**: датасет глазами, архитектура, таблица моделей, замеры, runbook | 22.10.2026 | актуален; собирается скриптом; **таблица моделей и все числа моделей — для модели 22.10** (WiSE-FT α = 0.4, коммит `43a65582…`), сейчас опубликована другая (`universal_v1`) | `reports/model_scoreboard.json`, `reports/bench_models/*.json`, `reports/TRAINING_*_BIG.*` |
| `HTML/make_gallery.py` | генератор галереи: пишет `index.html` **и** копирует сэмплы в `img/t/**` | 22.10.2026 | актуален | сам скрипт + `HTML/img/types.json` |
| `HTML/make_report.py` | генератор контакт-листов `HTML/img/sheet_*.png` и `HTML/img/types.json` | 22.10.2026 | актуален | `dataset/**/labels.jsonl` |
| `HTML/make_scoreboard.py` | замер модели (на 22.10 — WiSE-FT α = 0.4, `train/run_ppocr/big/export_soup/`) по всем 46 типам → `reports/model_scoreboard.json` | 22.10.2026 | активен **для модели 22.10**; сейчас опубликована `universal_v1` — замер **не переигран** и не переиграть его без старого рендера 46×500 (его больше нет: на диске 21 тип) | `train/run_ppocr/big/export_soup/` |
| `HTML/img/sheet_01…03.png` | контакт-листы типов (3.4 МБ) | 22.10.2026 | актуален (по рендеру 46×500); те же листы опубликованы на HF (`gallery/sheet_*.png`) | `dataset/**/labels.jsonl` |
| `HTML/img/types.json`, `HTML/img/types_table.html` | метаданные типов: группа, размер кадра, полоса, наличие solver'а | 22.10.2026 | актуален | `dataset/**/labels.jsonl` |
| `HTML/img/t/**` (276 PNG, 2.7 МБ) | копии 6 сэмплов каждого типа для лайтбокса | 22.10.2026 | **вывод скрипта → вне git** (правило 4); на диске владельца остаются | `dataset/**` |
| `CROPPER.md` | кроппер: дизайн (три слоя + голосование моделью) и измеренные числа | **27.10.2026** | актуален; §2.2 переизмерён через код приложения, §2.3 — проверка измерителем | `reports/cropper/eval_cropper*.json` + замер через `App.predict_frame` |
| `GALLERY_BUILT.md` | замер модели 22.10 по всем 46 типам (median 0.651 / micro 0.502) и что построено в галерее | 22.10.2026 | актуален **для модели 22.10** (WiSE-FT α = 0.4); это **первоисточник чисел** `model_scoreboard.json` | `reports/model_scoreboard.json` |
| `GEN_PARALLEL.md` | параллельный рендер `dev.captcha.Gen --jobs N`: `out` 120.1 → **16.1 с (×7.5)**, `out_ru` 562.6 → **24.1 с (×23.3)**, доказательство потокобезопасности | 22.10.2026 | актуален | `dataset/generator/dev/captcha/Gen.java`, прогоны `build/par_*` |
| `HF_DATASET_UPLOAD.md` | публикация датасета на HF: sha256 каждого PNG, проверки API | 22.10.2026 | актуален **на момент публикации**; на HF датасет переиздан позже (теперь parquet, 20 типов / 200 000 PNG, коммит `dd4d7479…`) | проверки HF API в самом отчёте |
| `HF_MODEL_UPLOAD.md` | выгрузка весов в `Titlehhhh/captchaocr-ppocrv6` (8 файлов, 77 085 348 Б) + проверка «грузится и предсказывает» | 22.10.2026 | **устарел по сути**: описывает публикацию WiSE-FT α = 0.4, которой на HF **больше нет**; текущая публикация — `universal_v1` (веса `27eb6fec…`, карточка `37556a88…`), и её описание лежит в `train/MODEL_CARD.md` и `HANDOVER.md` — **в `reports/` отчёта о ней нет** | `HfApi.upload_file(...)` / `from_pretrained(...)` в самом отчёте |
| `LIMBOFILTER_IDENTIFICATION.md` | идентификация семейства русских числовых слов как Elytrium/LimboFilter (AGPL-3.0) | 21.10.2026 | актуален (апстрим-исследование, не измерение) | `research/`, `docs/adr/0001` |
| `MODEL_PLAN.md` | план первой модели: архитектура, аугментация, обучение, публикация | 21.10.2026 | частично исполнен (врезка в начале файла) | фактические числа — в `TRAINING_*_BIG.*`; ревью — `docs/adr/0002` |
| `PUZZLE_OBJECT_FAMILIES.md` | семейства puzzle (V4/V5/V52/V53) и object (V8): апстрим-охота | 21.10.2026 | актуален; объект-семейство V8 **не идентифицировано** | `docs/adr/0003` |
| `RESEARCH_CYRILLIC_VOCAB.md` | исследование: откуда взять кириллицу для CTC (три рецепта) | 26.10.2026 | актуален (обзор, не измерение) | — |
| `RU_PLUGINS_CAPTCHA_VERIFYZ_SMARTCAPTCHA.md` | апстрим-разбор CaptchaVerifyZ и SmartCaptcha (декомпиляция, Modrinth, SpigotMC) | 21.10.2026 | актуален | `docs/adr/0003` |
| `SITE_CAPTCHAS.md` | разбор группы типов GalleryCaptcha: версия → плагин | 21.10.2026 | актуален | `docs/adr/0001`, `docs/adr/0003` |
| `TRAINING_CRNN_BIG.md` + `.json` | наш CRNN+CTC на датасете 500/тип, type-held-out: 7 типов учили, 4 удержали | 22.10.2026 | актуален | `train/runs/crnn/crnn_big/` → `make_report.py` |
| `TRAINING_LIMBO_DIGITS.md` | кириллическая сессия: чекпоинт `universal_v1`, рецепт «replay mix», 6/6 на скриншотах владельца | 26.10.2026 | актуален | `train/runs/ppocrv6/*` |
| `TRAINING_PPOCR_V6_BIG.md` + `.json` | дообучение PP-OCRv6_medium_rec на 500/тип + WiSE-FT α = 0.4 | 22.10.2026 | актуален | `train/run_ppocr/big/` |
| `TRAINING_TROCR_BIG.md` + `.json` | TrOCR-small-printed на тех же 7 типах: не лучше и в 5 раз медленнее | 22.10.2026 | актуален | `train/run/trocr_big/` |
| `UNLIMITED_OCR.md` | разбор Baidu Unlimited OCR 2: что переносится, и измеренный эксперимент с полосами-кандидатами | 27.10.2026 | актуален | `webapp/cropper.py::strip_candidates` |
| `TRAINING_MINIMAL_LATIN.md` | минимальная модель с нуля: 10 латинских типов, 4-фолд, скорости лоадера и GPU-шага | 21.10.2026 | **устарел по сути** («0.000 на невиданных» уже не верно), но **остаётся**: на его числа ссылаются `HANDOVER.md`, `docs/INPUT_PIPELINE.md`, `docs/OCR_MODELS_101.md`, `docs/pipeline-design.md`, `bench/export_onnx.py` | `train/run/foldA`, `train/eval_ckpt.py` |
| `TRAINING_PPOCR_V6.md` + `.json` | первое дообучение PP-OCRv6 (100 картинок на тип), автор остановил на 6-й эпохе из 30 | 21.10.2026 | **устарел по сути** (старый рендер), но **остаётся**: `docs/HOW_TO_TRAIN.md` цитирует его числа | `train/finetune_ppocr.py` (первый прогон) |
| `WEBAPP.md` | локальное веб-приложение (http.server, без зависимостей): что построено, проверки по HTTP | 22.10.2026 | **частично устарел** («30/30» на демо-свипе больше не применимо — см. `CROPPER.md` §5), но **остаётся**: на него ссылаются `README.md`, `HANDOVER.md`, `webapp/README.md` | `webapp/app.py` |

## B. Измеренные результаты — JSON, который не правится

| файл | что меряет | дата | состояние | первоисточник |
|---|---|---|---|---|
| `model_scoreboard.json` | модель 22.10 (WiSE-FT α = 0.4) по всем 46 типам: micro 0.502, median 0.651; 7 удержанных — 0.6123 / 0.638 | 22.10.2026 | активен **для модели 22.10**; **его читает код** (`make_gallery.py`, `make_scoreboard.py`, `tools/publish_gallery.py`) — поэтому остаётся; сейчас опубликована другая модель (`universal_v1`), её замер лежит в `train/runs/ppocrv6/universal_v1/result.json` и `train/MODEL_CARD.md` | `train/run_ppocr/big/export_soup/` |
| `bench_models/*.json` — 12 моделей | единый протокол: 46 типов × 20 = 920 предметов, вход «полоса» и «кадр» | 22.10.2026 | актуален; источник таблицы моделей в HTML-отчёте | `bench/bench_models.py` |
| `bench_models/T2_*.json` — 13 файлов | наш CRNN → ONNX → int8: паритет torch/ONNX (5.7e-6), скорость, квантизация, рантайм-паритет | 22.10.2026 | актуален | `train/export_onnx.py`, `bench/export_onnx.py` |
| `bench_models/errors_*.png` — 4 | контакт-листы ошибок бенчмарка: у кого какие типы рассыпались | 22.10.2026 | актуален (следствие тех же JSON) | из `bench_models/*.json` |
| `cropper/eval_cropper.json` | кроппер **без** слоя полос: oracle 0.6679 / кроппер 0.5357 / кадр 0.4357 (840) | 27.10.2026 | устарел (заменён следующим файлом и замером через приложение), но **остаётся**: это первоисточник своих чисел | `webapp/eval_cropper.py` |
| `cropper/eval_cropper_v2.json` | то же **со** слоем полос: 0.6679 / 0.5845 / 0.4357 | 27.10.2026 | устарел по кропперу (сейчас 0.6226), но **остаётся**: первоисточник своих чисел | `webapp/eval_cropper.py` |
| `cropper/boxes.png` (5.3 МБ) | рамки, которые выбрал кроппер | 27.10.2026 | остаётся вместе со своим отчётом `CROPPER.md` (который актуален) | `webapp/cropper.py` |
| `bench_results.json` | HF-модели по **старому** протоколу: 13 типов × 8 = 104 картинки, вход — целый кадр (anuashok 0.077) | 21.10.2026 | **устарел** (старый рендер, другие входы) — заменён `bench_models/*.json`; **остаётся**: его читают `bench/show_bench.py` и `train/compare_baselines.py` | `bench/bench_hf.py` |
| `bench_results_onnx.json` | сырые ONNX-капчи (captCHAD, phpwind), старый протокол | 21.10.2026 | **устарел**; **остаётся** — читает `train/compare_baselines.py` | `bench/bench_onnx.py` |
| `bench_results_others.json` | EasyOCR, Graf-J CRNN / conv-transformer, Florence (104 картинки) | 21.10.2026 | **устарел и оспорен** (`archive/2026-10-22-reviews/reviews/C2_technical.md`: 0.115 EasyOCR не воспроизводится); **остаётся** — читает `train/compare_baselines.py`, цитируется в `docs/adr/0002` | `bench/bench_others.py` |
| `bench_per_type.json` | наша модель против баз, по типам, на legacy-наборе (64 картинки) | 21.10.2026 | **устарел** (старый протокол, все значения 0.000); **остаётся**: на него ссылается `TRAINING_MINIMAL_LATIN.md` | `train/bench_per_type.py` |
| `eval_main_final.json` | чекпоинт минимальной модели по типам: 6 типов — exact 100/100, 4 типа — 0 | 21.10.2026 | числа верны **для старого рендера** (100/тип); **остаётся**: на него ссылается `TRAINING_MINIMAL_LATIN.md` | `train/eval_ckpt.py` → `train/run/foldA` |

## C. Исследования и обзоры (не измерения)

| файл | что это | дата | состояние | первоисточник |
|---|---|---|---|---|
| `research3/DATASET_AUDIT.md` | аудит 46 типов: полосы, пригодность к обучению, сплит | 22.10.2026 | частично устарел — числа считались по старому рендеру (100/тип) | `dataset/**/labels.jsonl` |
| `research3/MODEL_LANDSCAPE.md` | обзор готовых моделей + замеры скорости/VRAM на 1080 Ti | 22.10.2026 | актуален; цифра «0.40» — старый бенчмарк | `bench_models/ppocrv6-medium.json` |
| `research3/TRAINING_METHODS.md` | методы обучения + рецепт (объём, разнообразие, аугментации, дистилляция) | 22.10.2026 | актуален | измеренные прогоны — `TRAINING_*_BIG.*` |
| `research3/recommended_recipe.json` | машинно-читаемый рецепт (гиперпараметры, сплит, бюджет) | 22.10.2026 | описывает план; часть параметров уже исполнена | `TRAINING_PPOCR_V6_BIG.json` → `split`, `training_run` |

## D. Картинки-улики (не отчёты, а доказательства)

| файл | что на ней | размер | судьба |
|---|---|---|---|
| `roi_bands_minimal.png` | разрезанные полосы 10 типов минимальной модели | 2.6 МБ | **остаётся** — при отчёте `TRAINING_MINIMAL_LATIN.md` §4, на неё ссылается `HANDOVER.md` |
| `roi_bands_borderline.png` | то же по исключённым типам с полосой | 2.3 МБ | **остаётся** — там же |
| `roi_frames_minimal.png` | кадр с нарисованной полосой, 5 сэмплов на тип | 552 КБ | **остаётся** — там же |
| `augmented_minimal.png` | контакт-лист 200 аугментированных сэмплов | 696 КБ | **остаётся** — там же и в `HANDOVER.md` §M1 |
| `augmented_minimal_noaffine.png` | тот же лист без геометрического джиттера | 670 КБ | **остаётся** — там же |
| `HTML/img/sheet_01…03.png` | контакт-листы типов | 3.4 МБ | **остаётся** — это лицо HTML-отчёта; те же файлы опубликованы на HF |
| `HTML/img/t/**` | копии сэмплов для лайтбокса | 2.7 МБ | **вне git** (вывод скрипта, правило 4) |
| `cropper/boxes.png` | рамки кроппера | 5.3 МБ | **остаётся** — при `CROPPER.md` |
| `bench_models/errors_*.png` | ошибки бенчмарка | 4 файла | **остаются** — при `bench_models/*.json` |

---

## Архив: старый путь → новый путь

Старые отчёты **не удалены**, а переехали (`git mv`, история сохранена). Причина в каждом случае —
одной строкой в `reports/archive/README.md` (общая карта) и в `README.md` внутри папки архива.

| было | стало | причина |
|---|---|---|
| `reports/ALT_RENDERER_PROBE.md` | `reports/archive/2026-10-27-cleanup/ALT_RENDERER_PROBE.md` | разовый ответ владельцу про альтернативный рендерер; живых ссылок нет |
| `reports/GALLERY_OPTIONS.md` | `reports/archive/2026-10-27-cleanup/GALLERY_OPTIONS.md` | разведка вариантов галереи, заменена `GALLERY_BUILT.md` |
| `reports/HF_PUBLISH_REPORT.md` | `reports/archive/2026-10-27-cleanup/HF_PUBLISH_REPORT.md` | состояние карточки HF **без весов**; заменено `HF_MODEL_UPLOAD.md` |
| `reports/TRAINING_LIMBO_DIGITS_crashlog.md` | `reports/archive/2026-10-27-cleanup/TRAINING_LIMBO_DIGITS_crashlog.md` | краш-лог неудачного прогона; итог — в `TRAINING_LIMBO_DIGITS.md` |
| `reports/subagent_results.json` | `reports/archive/2026-10-27-cleanup/subagent_results.json` | помечен **stale** в `agents/AGENT_LOG.md` (строка 1): 30 сэмплов вместо 100/500 |
| `reports/captcha_report.html` | `reports/archive/2026-10-02-old-html/captcha_report.html` | формат устарел |
| `reports/captcha_pdf_embedded.html` | `reports/archive/2026-10-02-old-html/captcha_pdf_embedded.html` | картинки вшиты в разметку |
| `reports/CAPTCHA_OCR_REPORT.md` | `reports/archive/2026-10-21-old-baselines/CAPTCHA_OCR_REPORT.md` | базовые линии по старому протоколу (104 картинки) |
| `reports/PUBLISH_NOTES.md` | `reports/archive/2026-10-21-old-baselines/PUBLISH_NOTES.md` | публикация переделана |
| `reports/research/00_SYNTHESIS.md`, `00_SYNTHESIS.pdf`, `briefs/*.md` | `reports/archive/2026-10-21-research-wave1/research/…` | входные брифы и первый синтез |
| `reports/CAPTCHA_SYSTEM_OVERVIEW.md` | `reports/archive/2026-10-22-overview/CAPTCHA_SYSTEM_OVERVIEW.md` | предшественник нынешнего HTML-отчёта |
| `reports/research2/*.md` (9 файлов) | `reports/archive/2026-10-22-research-wave2/research2/…` | нарративы заменены измерениями |
| `reports/reviews/*.md` (4 файла) | `reports/archive/2026-10-22-reviews/reviews/…` | снимки старого состояния |

Ссылки внутри архивных файлов остались на старые пути — это сделано намеренно, чтобы не менять
содержимое отчётов. Первоисточники чисел, на которые они ссылаются, остались в `reports/`
(`bench_models/*.json`, `bench_results*.json`, `eval_main_final.json`, `bench_per_type.json`).

---

## Что изменилось 27.10.2026 (уборка `reports/`)

* **В архив уехали 5 файлов** (`reports/archive/2026-10-27-cleanup/`) — перемещены через `git mv`,
  содержимое не тронуто; причины — в `reports/archive/2026-10-27-cleanup/README.md`.
* **`reports/HTML/img/t/**` (276 PNG) убраны из индекса git** — это вывод `make_gallery.py`
  (копии сэмплов датасета), а не вход. На машине владельца файлы остались, `index.html` открывается
  полностью; в свежем клоне картинок лайтбокса не будет — см. `reports/HTML/img/t/.gitignore`.
  Измерено: 46 из 276 совпадают байт-в-байт с витриной `dataset/samples/<тип>/001.png` (она в git),
  а **230 — уникальны**: это сэмплы старого рендера 46×500, которого нет больше ни на диске, ни на
  Hugging Face (там новый рендер, parquet). Последняя копия 230 картинок — история git, её не чистить.
* **`reports/README.md` переписан** как указатель: одна строка на отчёт — что меряет, дата измерения,
  актуален или архив, где первоисточник; плюс правила папки (как отчёт попадает в репозиторий).
* **`reports/CROPPER.md` переизмерен**: §2.2 — новые числа (замер через код приложения, 27.10.2026),
  §2.3 — проверка измерителем, §5.1 — расхождение «измеритель vs приложение».
* **Ни один измеренный JSON не изменён** — `git diff --numstat -- 'reports/*.json' 'reports/bench_models/*.json'`
  пуст; `reports/HTML/index.html` тоже не тронут.

## Чего в `reports/` не хватает (записано, чтобы не потерялось)

1. **Нет отчёта о текущей публикации модели.** `reports/HF_MODEL_UPLOAD.md` описывает публикацию
   WiSE-FT α = 0.4 (22.10), которой на HF больше нет; опубликованная сейчас `universal_v1`
   (веса `27eb6fec…`, карточка `37556a88…`) описана в `train/MODEL_CARD.md` и в `HANDOVER.md`.
2. **Нет замера `universal_v1` по всем 46 типам.** Таблица модель/замер в `reports/HTML/index.html`
   и в `reports/model_scoreboard.json` — для модели 22.10. Переиграть `make_scoreboard.py` нельзя
   «как есть»: на диске 21 тип, а замер ждёт 46 (старый рендер не сохранился).
3. **Нет отчёта о публикации типа `out_ru/LimboFilter/digits`** (10 000 PNG, открытая работа по
   `HANDOVER.md` §M7).
