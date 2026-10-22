# ONBOARDING — что делать, если вы открыли этот репозиторий

Маршрут для человека. Четыре типичные цели — найдите свою и идите по ней; всё остальное можно
дочитать потом.

| Я хочу | Что делать | Подробности |
|---|---|---|
| **Посмотреть капчи** | открыть витрину в браузере | [`dataset/samples/index.html`](../dataset/samples/index.html) — по 5 картинок на каждый из 46 типов, с золотыми ответами и поиском. Ничего устанавливать не надо |
| **Скачать датасет** | одна команда | `python tools\fetch_dataset.py` — 4600 PNG (43.6 МБ) в `dataset/full/`. Флаги: `--dry-run`, `--types`, `--cache-dir`. Подробности — [`DATASET.md`](DATASET.md) |
| **Обучить модель** | тренажёр + отдельная среда | `train/README.md` — окружение, флаги, как читать кривую потерь. Коротко: `python -m venv .venv-gpu`, затем `pip install -r requirements.txt`, затем `train\train.py --trees both --epochs 80` |
| **Добавить свой тип капчи** | один Java-файл | `dataset/generator/dev/captcha/gens/<Имя>.java` — класс с публичным конструктором без аргументов, реализующий `dev.captcha.Cg`. Реестр править не надо: `dev.captcha.Gen` находит классы рефлексией. House rules — [`../dataset/generator/AGENTS.md`](../dataset/generator/AGENTS.md) |
| **Проверить метки и полосы** | два чекера | `python tools\check_labels_and_roi.py dataset\out_ru` и `python tools\check_band_vs_answer.py dataset\out_ru`. Правило полосы — в [`DATASET_FORMAT.md`](DATASET_FORMAT.md) |

## Что здесь вообще есть

| | |
|---|---|
| `dataset/generator/`, `dataset/generator_ru/` | генераторы на Java 21: 46 типов капчи от 23 плагинов |
| `dataset/out/`, `dataset/out_ru/` | сгенерированный датасет: 46 типов × 100 PNG + `labels.jsonl` |
| `dataset/samples/` | витрина: 230 PNG + `index.html` |
| `train/` | своя модель CRNN+CTC, тренажёр, измерители |
| `bench/` | харнессы для чужих OCR-моделей, единый протокол `bench_models.py` |
| `tools/` | чекеры меток и полос, скрипт скачивания датасета, публикация на HF |
| `reports/` | измеренные результаты (JSON и их разбор) |
| `docs/` | эта документация |

## Если нужна машина, а не человек

`AGENTS.md` — правила работы агентов в этом репозитории (оркестратор, владение файлами,
бриф). `agents/INDEX.md` — подробная карта репозитория для машины. `llms.txt` — короткая
машинная карта. Читать их **не обязательно**, чтобы пользоваться датасетом.

## Окружение

| что | где |
|---|---|
| Java 21 | JDK 21 в `PATH` (`java -version` → 21) или переменная `JAVA_HOME` |
| Python | 3.11+; зависимости — `requirements.txt` |
| GPU | нужен только для обучения; системный Python для тренажёра не годится |

Сборка генераторов (нужна, только если вы хотите **пересобрать** датасет):

```powershell
$javac = "$env:JAVA_HOME\bin\javac.exe"
$java  = "$env:JAVA_HOME\bin\java.exe"
$core = Get-ChildItem -File dataset\generator\dev\captcha\*.java | % FullName
& $javac -encoding UTF-8 -d build\classes    -sourcepath dataset\generator    $core (Get-ChildItem -Recurse -Filter *.java dataset\generator    | % FullName)
& $javac -encoding UTF-8 -d build\classes_ru -sourcepath dataset\generator_ru $core (Get-ChildItem -Recurse -Filter *.java dataset\generator_ru | % FullName)
& $java "-Djava.awt.headless=true" -cp build\classes    dev.captcha.Validate dataset\out
& $java "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Validate dataset\out_ru
```

> **Не пересобирайте датасет, если не хотите его переписать.** Генераторы **не засеяны**: при
> пересборке картинки будут другими (шрифты AWT те же, случайные значения — новые), а
> `labels.jsonl` и `index.html` в git изменятся. Датасет — артефакт, а не функция.

Полная пересборка (с генерацией и валидацией) — в `AGENTS.md` §4.

## Что измерено и где это лежит

* `reports/bench_models/*.json` — единый протокол бенчмарка: 46 типов × 20 картинок, две режима
  подачи (полоса `roi` и целый кадр), exact match и CER.
* `reports/TRAINING_MINIMAL_LATIN.md` — минимальная модель, обученная с нуля: 1.000 на знакомых
  типах и 0.000 на невиданных (то есть запоминает, а не обобщает).
* `reports/TRAINING_PPOCR_V6.md` — дообучение PP-OCRv6 на 7 удержанных типах.

Если документация расходится с измерениями — **правы измерения**.

## Куда смотреть дальше

| Тема | Файл |
|---|---|
| Где лежит датасет и как его скачать | [`DATASET.md`](DATASET.md) |
| Контракт `labels.jsonl`, `text` vs `answer`, правило полосы | [`DATASET_FORMAT.md`](DATASET_FORMAT.md) |
| Плагины, лицензии, режимы реконструкции | [`PLUGINS.md`](PLUGINS.md) · [`LICENSES.md`](LICENSES.md) |
| Дефекты апстрима | [`UPSTREAM_DEFECTS.md`](UPSTREAM_DEFECTS.md) |
| Словарь терминов | [`GLOSSARY.md`](GLOSSARY.md) |
| Обучение | [`../train/README.md`](../train/README.md) |
| Публикация на Hugging Face | [`../tools/PUBLISH_HF.md`](../tools/PUBLISH_HF.md) |
