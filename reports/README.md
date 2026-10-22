# Отчёты CaptchaOCR — индекс (22.10.2026)

> В командах внутри отчётов пути — те, что были на машине автора; для переносимых версий см.
> `docs/HOW_TO_TRAIN.md`.

## Где мой отчёт

**Открыть `reports/HTML/index.html`** — это тот самый один отчёт: контакт-листы всех 46 типов датасета,
таблицы моделей, все измеренные числа и пошаговая инструкция «как запустить самому».
Всё остальное в `reports/` — либо **измеренные результаты** (JSON, который нельзя править руками),
либо отчёты отдельных прогонов. Старые и заменённые отчёты лежат в `reports/archive/`
(карта — внизу страницы и в `reports/archive/README.md`).

## Коротко: главные числа на сейчас

| что | значение | где измерено |
|---|---|---|
| Датасет | **46 типов × 500 = 23 000 PNG** (на диске ещё 517 эталонных скриншотов — они не публикуются) | `dataset/out/`, `dataset/out_ru/`; публикация — `reports/HF_DATASET_UPLOAD.md` |
| Датасет опубликован | <https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset> (коммит `6248c5b9…`) | `reports/HF_DATASET_UPLOAD.md` |
| Лучшая готовая модель, **по полосе** | **PP-OCRv6_medium_rec = 0.552** exact match (micro, 29 типов с полосой, 580 предметов) | `reports/bench_models/ppocrv6-medium.json` → `modes.band.full.metrics.roi_types.acc_micro` |
| …**по целому кадру** | тот же чекпоинт — **0.035** (в 16 раз хуже: решает кроппер, а не модель) | тот же JSON → `modes.frame.full.metrics.roi_types.acc_micro` |
| Наш CRNN+CTC с нуля, **невиданные плагины** | **0.381 micro** exact match (4 удержанных типа, 1999 картинок; медиана по типам 0.372) | `reports/TRAINING_CRNN_BIG.json` → `held_out.micro_over_images` |
| Наш CRNN+CTC, свои типы | 1.000 (медиана) — это запоминание, а не обобщение | `reports/TRAINING_CRNN_BIG.json` → `memorisation_gap` |
| Дообучение PP-OCRv6 на новом датасете | нулевой шаг 0.588 медиана → после дообучения 0.480 (хуже) → **с интерполяцией весов (WiSE-FT α=0.4) 0.638 / 0.612 micro** | `reports/TRAINING_PPOCR_V6_BIG.json` → `verdict`, `weight_interpolation` |
| TrOCR-small-printed (1 эпоха) на тех же 7 типах | **0.20 %** медиана против 58.8 % у нетронутого PP-OCRv6 и в 5 раз медленнее | `reports/TRAINING_TROCR_BIG.json` |
| Модель на Hugging Face | **веса загружены** (8 файлов, 77 085 348 Б) в <https://huggingface.co/Titlehhhh/captchaocr-ppocrv6> — карточка была создана раньше, без весов | `reports/HF_MODEL_UPLOAD.md` (история: `reports/HF_PUBLISH_REPORT.md`) |

## Отчёты этой сессии (живые)

| файл | что меряет | числа актуальны? | первоисточник (source of truth) |
|---|---|---|---|
| `HTML/index.html` | **сводный отчёт владельцу**: датасет глазами, архитектура, таблица моделей, замеры, инструкция запуска | да (собран 22.10 15:22) | собирает: `dataset/**/labels.jsonl`, `reports/bench_models/*.json`, `reports/TRAINING_*_BIG.*` |
| `HTML/make_report.py` | генератор этого HTML (не отчёт) | да | сам скрипт + `HTML/img/types.json` |
| `HTML/img/sheet_01…03.png`, `img/types.json`, `img/types_table.html` | контакт-листы 46 типов и таблица «тип → полоса/группа» | да (по текущему датасету) | `dataset/**/labels.jsonl` |
| `TRAINING_CRNN_BIG.md` + `.json` | наш CRNN+CTC на новом датасете (500/тип), type-held-out: 7 типов учили, 4 удержали | **да** | `train/run/crnn_big/` → `val_report.json`, `eval_train_types.json`, `eval_heldout_types.json`, `train.log` |
| `TRAINING_PPOCR_V6_BIG.md` + `.json` | дообучение PP-OCRv6_medium_rec на новом датасете + интерполяция весов | **да** | `train/run_ppocr/big/result.json`, `train/run_ppocr/big/log.txt` |
| `TRAINING_TROCR_BIG.md` + `.json` | TrOCR-small-printed на тех же 7 удержанных типах против PP-OCRv6 | **да** | `train/run/trocr_big/result.json`, `train/run/trocr_big/log.txt` |
| `HF_DATASET_UPLOAD.md` | как опубликован датасет 46×500 = 23 000 PNG в `Titlehhhh/captchaocr-dataset` | да | проверки HF API в самом отчёте, коммит `6248c5b9…` |
| `GEN_PARALLEL.md` | **параллельный рендер** `dev.captcha.Gen`: флаг `--jobs N`, ускорение на 36 воркерах — `out` 120.1 → **16.1 с (×7.5)**, `out_ru` 562.6 → **24.1 с (×23.3)**; доказательство потокобезопасности и что не проверено | да | `dataset/generator/dev/captcha/Gen.java`; прогоны — `build/par_*` |
| `HF_PUBLISH_REPORT.md` | публикация датасета и карточки модели на HF | на момент отчёта — **карточка без весов** (веса выложены позже, см. следующую строку) | `HfApi.repo_info(...)` в отчёте |
| `HF_MODEL_UPLOAD.md` | выгрузка **настоящих весов** в `Titlehhhh/captchaocr-ppocrv6` (8 файлов, 77 085 348 Б, `model.safetensors` 76 747 448 Б) + проверка, что модель грузится и предсказывает | да | `HfApi.upload_file(...)` / `from_pretrained(...)` в самом отчёте |
| `WEBAPP.md` | локальное веб-приложение для распознавания (http.server, без зависимостей) | да | `webapp/app.py`, проверки по HTTP в отчёте |

> Отчёты этой сессии, которые ещё дописываются, появятся здесь же: выгрузка весов модели на HF —
> `reports/HF_MODEL_UPLOAD.md` (уже создан), остальные — сюда же, с пометкой «дописывается».

## Измеренные результаты — остаются на месте, их нельзя править

`reports/` хранит измерения. JSON-файлы **не редактируются** (AGENTS.md §8): чтобы «улучшить» модель,
бенчмарк перезапускают.

| файл | что меряет | числа актуальны? | первоисточник |
|---|---|---|---|
| `bench_models/ppocrv6-medium.json` | PP-OCRv6_medium_rec, единый протокол: 46 типов × 20 = 920 предметов, вход «полоса» и «кадр» | **да** — 0.552 band / 0.035 frame | `bench/bench_models.py` |
| `bench_models/ppocrv5-mobile.json`, `ppocrv5-cyrillic.json`, `doctr-crnn-ru.json`, `grafj-crnn.json`, `grafj-crnn-base.json`, `grafj-convtr.json`, `txtcaptcha-crnn.json`, `anuashok-v3.json`, `emelnov-mailru.json`, `trocr-base-printed.json`, `easyocr.json` | те же 12 чужих моделей по тому же протоколу, с предсказаниями и разбивкой по типам | **да** | `bench/bench_models.py` |
| `bench_models/errors_*.png` (4) | контакт-листы ошибок: у кого какие типы рассыпались | да | из тех же JSON |
| `bench_models/T2_*.json` (11) | наш CRNN → ONNX → int8: паритет torch/ONNX (5.7e-6), скорость, квантизация, рантайм-паритет | **да** | `train/export_onnx.py`, `bench/export_onnx.py` |
| `eval_main_final.json` | чекпоинт минимальной модели по типам: 6 типов — exact 100/100, 4 типа — 0 | числа верны **для того прогона** (старый рендер 100/тип) | `train/eval_ckpt.py` → `train/run/foldA` |
| `bench_per_type.json` | наша модель против баз, по типам, на legacy-наборе 64 картинки | **старый протокол** (64 предмета), все значения 0.000 | `train/bench_per_type.py` |
| `bench_results.json` | HF-модели по старому протоколу: 13 типов × 8 = 104 картинки, вход — **целый кадр** (anuashok 0.077) | **устарело** (старый рендер, разные входы) — заменено `bench_models/*.json` | `bench/bench_hf.py` |
| `bench_results_onnx.json` | сырые ONNX-капчи (captCHAD, phpwind) по тому же старому протоколу | **устарело** — заменено `bench_models/*.json` | `bench/bench_onnx.py` |
| `bench_results_others.json` | EasyOCR, Graf-J CRNN/conv-transformer, Florence (104 картинки) | **устарело и оспорено** (`reviews/C2_technical.md` в архиве): 0.115 EasyOCR не воспроизводится | `bench/bench_others.py` |
| `subagent_results.json` | первые шесть субагентов-генераторов (только метки, без перечитывания картинок) | **устарело**: записывает `LagBug/XProtect/different` с `count: 30`, в дереве 500 | `dataset/out/*.jsonl` тех дней |

## Отчёты, которые остаются, но считать их «свежими» нельзя

| файл | что это | статус | чем заменён / с чем сверять |
|---|---|---|---|
| `TRAINING_PPOCR_V6.md` + `.json` | первое дообучение PP-OCRv6 (100 картинок на тип, LR 1e-4), **остановлено автором на 6-й эпохе из 30** | измерения верны **для старого рендера** (100/тип) | `TRAINING_PPOCR_V6_BIG.md`/`.json` (новый датасет, 500/тип) |
| `TRAINING_MINIMAL_LATIN.md` | минимальная модель с нуля: 10 латинских типов, 4-фолд; 1.000 на своих типах и 0.000 на невиданных (доказано подменой пикселей) | измерения верны **для старого рендера**; «0.000 на невиданных» уже не актуально | `TRAINING_CRNN_BIG.md`/`.json` (0.381 micro на 4 невиданных типах) |
| `MODEL_PLAN.md` | план первой модели: архитектура, аугментация, обучение, публикация | частично исполнен (см. врезку в начале файла) | фактические числа — в `TRAINING_*_BIG.*` |
| `SITE_CAPTCHAS.md` | разбор группы типов GalleryCaptcha: версия → плагин | актуально (апстрим-исследование, не измерение) | — |
| `LIMBOFILTER_IDENTIFICATION.md` | идентификация семейства числовых слов как Elytrium/LimboFilter (AGPL-3.0) | актуально | — |
| `PUZZLE_OBJECT_FAMILIES.md` | семейства puzzle (V4/V5/V52/V53) и object (V8): апстрим-охота | актуально; объект-семейство V8 **не идентифицировано** | — |
| `RU_PLUGINS_CAPTCHA_VERIFYZ_SMARTCAPTCHA.md` | апстрим-разбор CaptchaVerifyZ и SmartCaptcha (декомпиляция, Modrinth, SpigotMC) | актуально | — |
| `research3/DATASET_AUDIT.md` | аудит 46 типов: полосы, пригодность к обучению, сплит | числа — **по старому рендеру** (100/тип) | `TRAINING_PPOCR_V6_BIG.json` → `dataset` (текущий расклад) |
| `research3/MODEL_LANDSCAPE.md` | обзор готовых моделей + замеры скорости/VRAM на 1080 Ti | обзор актуален; цифра «0.40» — старый бенчмарк | `bench_models/ppocrv6-medium.json` (0.552 / 0.035) |
| `research3/TRAINING_METHODS.md` | методы обучения + рецепт (объём, разнообразие, аугментации, дистилляция) | актуально; **сам помечает `research2/E` как заменённый** | измеренные прогоны — `TRAINING_*_BIG.*` |
| `research3/recommended_recipe.json` | машинно-читаемый рецепт (гиперпараметры, сплит, бюджет) | описывает план; часть параметров уже исполнена | `TRAINING_PPOCR_V6_BIG.json` → `split`, `training_run` |

## Картинки-улики (не отчёты, а доказательства)

| файл | что на ней | для какого отчёта |
|---|---|---|
| `roi_bands_minimal.png`, `roi_frames_minimal.png`, `roi_bands_borderline.png` | разрезанные полосы и кадры с нарисованной полосой — по 10 типам минимальной модели | `TRAINING_MINIMAL_LATIN.md` §4 |
| `augmented_minimal.png`, `augmented_minimal_noaffine.png` | контакт-лист 200 аугментированных сэмплов (со вторым — без геометрического джиттера) | `TRAINING_MINIMAL_LATIN.md`, `HANDOVER.md` §M1 |

## Архив: старый путь → новый путь

Старые отчёты **не удалены**, а переехали (`git mv`, история сохранена). Причина в каждом случае —
одной строкой в `reports/archive/README.md`.

| было | стало |
|---|---|
| `reports/captcha_report.html` | `reports/archive/2026-10-02-old-html/captcha_report.html` |
| `reports/captcha_pdf_embedded.html` | `reports/archive/2026-10-02-old-html/captcha_pdf_embedded.html` |
| `reports/CAPTCHA_OCR_REPORT.md` | `reports/archive/2026-10-21-old-baselines/CAPTCHA_OCR_REPORT.md` |
| `reports/PUBLISH_NOTES.md` | `reports/archive/2026-10-21-old-baselines/PUBLISH_NOTES.md` |
| `reports/research/00_SYNTHESIS.md`, `00_SYNTHESIS.pdf`, `briefs/*.md` | `reports/archive/2026-10-21-research-wave1/research/…` |
| `reports/CAPTCHA_SYSTEM_OVERVIEW.md` | `reports/archive/2026-10-22-overview/CAPTCHA_SYSTEM_OVERVIEW.md` |
| `reports/research2/*.md` (9 файлов) | `reports/archive/2026-10-22-research-wave2/research2/…` |
| `reports/reviews/*.md` (4 файла) | `reports/archive/2026-10-22-reviews/reviews/…` |

Ссылки внутри архивных файлов остались на старые пути — это сделано намеренно, чтобы не менять
содержимое отчётов. Первоисточники чисел, на которые они ссылаются, остались в `reports/`
(`bench_models/*.json`, `bench_results*.json`, `eval_main_final.json`).

## Правила для этой папки

1. **JSON результатов не править** (AGENTS.md §8) — перезапустить измерение.
2. Новый отчёт → строка в этом файле: что меряет, актуальны ли числа, первоисточник.
3. Отчёт, который заменён более свежим измерением, → `reports/archive/<дата>-<тема>/` через `git mv` + строка в `reports/archive/README.md`.
4. Один browsable-отчёт — `reports/HTML/index.html`; он и есть ответ на «где мой отчёт».
