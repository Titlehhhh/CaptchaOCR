# ONBOARDING — что делать, если вы открыли этот репозиторий

Маршрут для человека или для нового агента. Найдите свою цель и идите по ней; всё остальное
можно дочитать потом. **Числа в этом файле — текущие** (датасет: 46 типов × 500 = 23 000 PNG,
модель опубликована с весами). Если документация расходится с измерениями — **правы измерения**
(см. `reports/`).

## Коротко: что это за проект

**CaptchaOCR** — лаборатория моделей для решения Minecraft-капч. Две половины:

| половина | что это | где |
|---|---|---|
| **Датасет** | Java 21-генераторы, которые заново отрисовывают капчи 23 открытых Minecraft-плагинов-антиботов — 46 типов, **23 000** размеченных PNG | `dataset/generator/`, `dataset/generator_ru/` → `dataset/out/`, `dataset/out_ru/` |
| **Модели** | харнессы для чужих OCR-моделей, свой CRNN+CTC с нуля и дообучение PP-OCRv6 с интерполяцией весов | `bench/`, `train/` |

Опубликовано на Hugging Face: **датасет** <https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset>
и **модель с весами** <https://huggingface.co/Titlehhhh/captchaocr-ppocrv6>.

## Четыре типичные цели

| Я хочу | Что делать | Подробности |
|---|---|---|
| **Посмотреть капчи** | открыть витрину в браузере | [`dataset/samples/index.html`](../dataset/samples/index.html) — по 5 картинок на каждый из 46 типов, с золотыми ответами и поиском. Ничего устанавливать не надо. Витрина — выдержка из **текущего** рендера (500 на тип, 22.10.2026); полный набор — на Hugging Face |
| **Скачать датасет** | одна команда | `python tools\fetch_dataset.py` — скачивает опубликованный датасет (23 000 PNG) в `dataset/full/`. Флаги: `--dry-run`, `--types`, `--cache-dir`. Подробности — [`docs/DATASET.md`](DATASET.md) |
| **Обучить модель** | runbook + отдельная среда | [`docs/HOW_TO_TRAIN.md`](HOW_TO_TRAIN.md) — полный маршрут: обучение → остановка → продолжение → оценка → интерполяция → экспорт → публикация. Флаги тренажёра CRNN — [`train/README.md`](../train/README.md) |
| **Добавить свой тип капчи** | один Java-файл | `dataset/generator/dev/captcha/gens/<Имя>.java` — класс с публичным конструктором без аргументов, реализующий `dev.captcha.Cg`. Реестр править не надо: `dev.captcha.Gen` находит классы рефлексией. House rules — [`dataset/generator/AGENTS.md`](../dataset/generator/AGENTS.md) |

## Что здесь вообще есть

| | |
|---|---|
| `dataset/generator/`, `dataset/generator_ru/` | генераторы на Java 21: 46 типов капчи от 23 плагинов |
| `dataset/out/`, `dataset/out_ru/` | сгенерированный датасет: **46 типов × 500 PNG** + `labels.jsonl` (по 500 строк на тип) |
| `dataset/out_ru/*/real_shots/` | **517** эталонных скриншотов чужих плагинов — только на диске, **не публикуются** |
| `dataset/samples/` | витрина: 230 PNG + `dataset/samples/index.html` (выдержка из текущего рендера) |
| `train/` | своя модель CRNN+CTC, тренажёр, дообучение PP-OCRv6, интерполяция весов, экспорт в HF |
| `bench/` | харнессы для чужих OCR-моделей, единый протокол `bench/bench_models.py` |
| `tools/` | чекеры меток и полос, скрипт скачивания датасета, загрузка и проверка публикаций на HF |
| `webapp/` | локальная браузерная демка (порт 8765, офлайн, без зависимостей) |
| `reports/` | измеренные результаты: индекс — [`reports/README.md`](../reports/README.md), отчёт — [`reports/HTML/index.html`](../reports/HTML/index.html), старое — `reports/archive/` |
| `docs/` | эта документация |

## Окружение этой машины

| что | где | примечание |
|---|---|---|
| Java 21 | JDK 21 в `I:\ForAndroid\Java\21`; `JAVA_HOME` задан на уровне пользователя Windows | **`java`/`javac` НЕ на `PATH`** — зовите `"$env:JAVA_HOME\bin\javac.exe"` |
| Python с GPU | `.venv-gpu\Scripts\python.exe` (`torch 2.14.1+cu126`) | системный `python` — **CPU-only**, обучать на нём нельзя |
| GPU | GTX 1080 Ti, 11.8 ГБ | VLM-модели сюда не помещаются |
| Hugging Face | токен в `.hf-cache\token`, нужен `$env:HF_HOME` = путь к `.hf-cache` | токен не печатать и не коммитить |
| PowerShell | только Windows PowerShell 5.1, бинаря `pwsh` нет | выполнение `.ps1` заблокировано → **`build.ps1` запустить нельзя** |

Полная таблица путей и слоёв окружения — [`docs/LOCAL_ENV.md`](LOCAL_ENV.md).

## Шаг 1. Собрать генераторы (нужно только для пересборки датасета)

`build.ps1` на этой машине **запустить нельзя** — выполняйте логику инлайн:

```powershell
$javac = if ($env:JAVA_HOME) { "$env:JAVA_HOME\bin\javac.exe" } else { "javac" }
$java  = if ($env:JAVA_HOME) { "$env:JAVA_HOME\bin\java.exe"  } else { "java" }
$core  = Get-ChildItem -File dataset\generator\dev\captcha\*.java | % FullName   # общие классы: без них RU-дерево не собирается

& $javac -encoding UTF-8 -d build\classes    -sourcepath dataset\generator    $core (Get-ChildItem -Recurse -Filter *.java dataset\generator    | % FullName)
& $javac -encoding UTF-8 -d build\classes_ru -sourcepath dataset\generator_ru $core (Get-ChildItem -Recurse -Filter *.java dataset\generator_ru | % FullName)
```

> **Не пересобирайте датасет, если не хотите его переписать.** Генераторы **не засеяны**: при
> пересборке картинки будут другими (шрифты AWT те же, случайные значения — новые), а
> `labels.jsonl` и `dataset/out/index.html` в git изменятся. Датасет — артефакт, а не функция.

## Шаг 2. Перегенерировать и провалидировать датасет

```powershell
& $java "-Djava.awt.headless=true" -cp build\classes    dev.captcha.Gen      dataset\out    500
& $java "-Djava.awt.headless=true" -cp build\classes    dev.captcha.Validate dataset\out
& $java "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Gen      dataset\out_ru 500
& $java "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Validate dataset\out_ru
python tools\restore_real_shots.py     # вернуть real_shots/ после пересборки
```

`Gen <outDir> <count>` рисует все генераторы, пишет PNG, `labels.jsonl` на тип и `dataset/out/index.html`.
`Validate <outDir>` печатает `n / minColors / blank / dupes / labels` по типам. Все три работают
headless. Ожидаемо: **34 типа в `dataset/out/` и 12 в `dataset/out_ru/`**, по **500** PNG на тип
(23 000 суммарно) + **517** эталонных скриншотов.

## Шаг 3. Проверить метки и полосы

```powershell
python tools\check_labels_and_roi.py dataset\out
python tools\check_labels_and_roi.py dataset\out_ru
python tools\check_band_vs_answer.py dataset\out_ru
```

Правило полосы и контракт `labels.jsonl` — [`docs/DATASET_FORMAT.md`](DATASET_FORMAT.md);
термины (`text` vs `answer`, группы A/B/C) — [`docs/GLOSSARY.md`](GLOSSARY.md).

## Шаг 4. Обучить — две разные ветки

### 4a. Наша модель CRNN+CTC с нуля

```powershell
.venv-gpu\Scripts\python.exe train\train.py --trees both --epochs 80 `
    --val-types "haq/mapcha/map" "CaptchaVerifyZ/map"
```

Разбор кривой потерь, плато all-blank CTC, правило полосы — [`train/AGENTS.md`](../train/AGENTS.md)
и [`train/README.md`](../train/README.md). Измеренный результат большого прогона:
1.000 на типах, на которых учили, и **0.372 медиана / 0.381 micro** на 4 невиданных типах
(`reports/TRAINING_CRNN_BIG.md`).

### 4b. Дообучение PP-OCRv6 (то, что опубликовано)

```powershell
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\run_ppocr\big `
    --epochs 20 --batch-size 32 --lr 1e-5 --head-lr 1e-5 `
    --workers 6 --eval-every 1 --save-every 100 --max-minutes 36
```

* `--lr 1e-5` — **не поднимайте до 1e-4**: при 1e-4 дообучение ухудшало метрику (0.600 → 0.410).
* Первые ~41 с скрипт тратит на **нулевой шаг** (замер предобученной модели). Ориентир:
  медиана **≈ 0.588**, micro **≈ 0.56**. Если ниже 0.3 — сломан вход (кроп по полосе, BGR, нормализация).
* Сплит — **по целым плагинам**, никогда random split.

### Остановка и продолжение

| как | что происходит |
|---|---|
| `--max-minutes N` | мягкая остановка: скрипт доходит до конца эпохи, пишет `ckpt\final.pt`, выходит с кодом 0 |
| Ctrl+C | теряется только текущий батч; все `ckpt\step_*.pt` валидны |
| потерялось окно | `Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*\.venv-gpu\*" } | Stop-Process -Force` |

Продолжение — **та же команда, тот же `--out` и те же гиперпараметры**, плюс `--resume`:

```powershell
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\run_ppocr\big `
    --epochs 20 --batch-size 32 --lr 1e-5 --head-lr 1e-5 `
    --workers 6 --eval-every 1 --save-every 100 --max-minutes 120 --resume
```

`--resume` берёт **новейший** файл из `ckpt\` и восстанавливает модель + оптимизатор + scheduler +
GradScaler + номер эпохи и шага — это точное продолжение, а не «начать заново». `--epochs` при
продолжении должен быть **тем же**: OneCycleLR рассчитан на `steps_per_epoch × epochs`.
`--init-from` — другое: загружает **только веса** и создаёт **новый** цикл обучения с новым LR.

## Шаг 5. Оценить без обучения

```powershell
# нулевой шаг: меряем предобученную модель на наших типах и выходим
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\run_ppocr\zerostep `
    --zero-step --limit-per-type 20
```

> ⚠️ `--eval-only` **в одиночку** не делает того, что читается в названии: он только пропускает
> нулевой шаг, после чего обучение идёт дальше. Правильный флаг «оценить и выйти» —
> `--zero-step` **без** `--eval-only`.

Оценка обученного чекпоинта без обучения — в [`docs/HOW_TO_TRAIN.md`](HOW_TO_TRAIN.md) §4.2.

## Шаг 6. Интерполировать веса с базой (шаг 2 рецепта публикации)

```powershell
.venv-gpu\Scripts\python.exe train\soup_eval.py
```

Скрипт берёт `train\run_ppocr\big\best.pt`, меряет 7 значений α тем же пайплайном (те же 7
удержанных типов, те же 3 500 картинок) и пишет рядом `train/run_ppocr/big/soup.json`
и `../train/run_ppocr/big/soup_best.pt`.

`θ(α) = α·θ_дообученной + (1−α)·θ_предобученной`; α = 0 — база, α = 1 — чистое дообучение.
Измеренная сетка: 0.00 → 0.588 · 0.25 → 0.620 · **0.40 → 0.638 (публикуем это)** · 0.50 → 0.614 ·
0.60 → 0.592 · 0.75 → 0.542 · 1.00 → 0.480 (медиана exact по 7 типам).

> ⚠️ **α и эпоху выбирали на том же удержанном наборе**, на котором потом измеряли, → 0.638 —
> оптимистичная оценка. На втором удержанном наборе выбор не проверялся.

## Шаг 7. Экспортировать и опубликовать

```powershell
$env:HF_HOME="C:\Users\Title\Projects\CapthaModel\.hf-cache"
$env:HF_HUB_CACHE="C:\Users\Title\Projects\CapthaModel\.hf-cache"

# экспорт весов в папку Hugging Face
.venv-gpu\Scripts\python.exe train\export_ppocr_hf.py --ckpt train\run_ppocr\big\soup_best.pt `
    --out train\run_ppocr\big\export

# выкладка
hf auth whoami                                   # ✓ Logged in / user: Titlehhhh
hf upload Titlehhhh/captchaocr-ppocrv6 train\run_ppocr\big\export --repo-type model
```

> **Никогда не публикуйте чистое дообучение** (`best.pt` без интерполяции) — оно на **10.8 п.п.**
> хуже нетронутой базы. В `train/run_ppocr/big/export/finetune_meta.json` должно стоять
> `"soup_alpha": 0.4`.

Датасет на хаб выкладывается отдельно: `python tools\upload_dataset.py` (батчи по типам,
сравнение по **sha256**; `--dry-run` — план, `--verify` — проверка удалённого дерева).
Подробности — [`reports/HF_DATASET_UPLOAD.md`](../reports/HF_DATASET_UPLOAD.md),
[`tools/PUBLISH_HF.md`](../tools/PUBLISH_HF.md).

## Шаг 8. Браузерная демка

```powershell
.venv-gpu\Scripts\python.exe webapp\app.py      # затем откройте http://127.0.0.1:8765/
```

Закиньте PNG капчи (или выберите демо-картинку из списка типов) — получите предсказание, точность
по символам, золотой ответ и задержку. Сервер — только стандартная библиотека Python, офлайн.
Подробности — [`webapp/README.md`](../webapp/README.md).

## Что измерено и где это лежит

| файл | что в нём |
|---|---|
| `reports/HTML/index.html` | **единственный browsable-отчёт**: 46 типов картинками, таблицы моделей, все замеры, runbook |
| `reports/README.md` | индекс отчётов: что актуально, что устарело, что в `reports/archive/` |
| `../reports/bench_models/*.json` | единый протокол бенчмарка: 46 типов × 20 картинок, два режима подачи (полоса `roi` и целый кадр), exact match и CER. 12 чужих моделей |
| `reports/TRAINING_PPOCR_V6_BIG.md` | дообучение PP-OCRv6: 0.588 → 0.480 → **0.638** (интерполяция α = 0.4) |
| `reports/TRAINING_CRNN_BIG.md` | наш CRNN+CTC: 1.000 на обученных типах, 0.372 / 0.381 на невиданных |
| `reports/TRAINING_TROCR_BIG.md` | TrOCR-small: не лучше и в 5 раз медленнее PP-OCRv6 |

Ключевой измеренный вывод: **решает кроппер, а не модель** — 0.5517 exact match по полосе против
0.0345 по целому кадру на одних и тех же 29 типах (в 16 раз хуже).

## Если нужна машина, а не человек

`AGENTS.md` — правила работы агентов в этом репозитории (оркестратор, владение файлами, бриф).
`agents/INDEX.md` — подробная карта репозитория для машины. `llms.txt` — короткая машинная карта.
Читать их **не обязательно**, чтобы пользоваться датасетом.

## Куда смотреть дальше

| Тема | Файл |
|---|---|
| Всё измерено, в одном отчёте | [`reports/HTML/index.html`](../reports/HTML/index.html) |
| Runbook обучения и публикации | [`docs/HOW_TO_TRAIN.md`](HOW_TO_TRAIN.md) |
| Как PNG доходит до модели | [`docs/INPUT_PIPELINE.md`](INPUT_PIPELINE.md) |
| Обзор ландшафта OCR/VLM/CTC-моделей | [`docs/OCR_MODELS_101.md`](OCR_MODELS_101.md) |
| Локальный тулчейн машины | [`docs/LOCAL_ENV.md`](LOCAL_ENV.md) |
| Где лежит датасет и как его скачать | [`docs/DATASET.md`](DATASET.md) |
| Контракт `labels.jsonl`, `text` vs `answer`, правило полосы | [`docs/DATASET_FORMAT.md`](DATASET_FORMAT.md) |
| Плагины, лицензии, режимы реконструкции | [`docs/PLUGINS.md`](PLUGINS.md) · [`docs/LICENSES.md`](LICENSES.md) |
| Дефекты апстрима | [`docs/UPSTREAM_DEFECTS.md`](UPSTREAM_DEFECTS.md) |
| Словарь терминов | [`docs/GLOSSARY.md`](GLOSSARY.md) |
| Обучение CRNN (флаги) | [`train/README.md`](../train/README.md) · [`train/AGENTS.md`](../train/AGENTS.md) |
| Публикация на Hugging Face | [`tools/PUBLISH_HF.md`](../tools/PUBLISH_HF.md) |
