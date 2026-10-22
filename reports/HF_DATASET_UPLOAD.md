# HF dataset upload — CaptchaOCR dataset (500 per type)

**Дата:** 2026-10-22 · **Репозиторий:** <https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset>
· **Тип:** dataset · **Публичный:** да · **Итоговый коммит:** `6248c5b9b6ce7eb6e917efd7aa3952892beb7cea`

Задача: опубликовать перерисованный датасет (46 типов × 500 картинок = 23 000 PNG)
в **существующий** публичный репозиторий `Titlehhhh/captchaocr-dataset`, сохранив
прежнюю раскладку, чтобы `tools/fetch_dataset.py` продолжал работать без правок.

---

## 1. Что было удалено

В начале работы по исходному брифу был создан **новый** репозиторий
`Titlehhhh/captchaocr-dataset-v2`, и в него началась загрузка. По решению владельца
(«новых репозиториев не делать») репозиторий удалён:

```powershell
$env:HF_HOME="C:\Users\Title\Projects\CapthaModel\.hf-cache"
@'
from huggingface_hub import HfApi
api = HfApi()
api.delete_repo(repo_id="Titlehhhh/captchaocr-dataset-v2", repo_type="dataset")
'@ | Out-File $env:TEMP\hf_del.py -Encoding utf8
python $env:TEMP\hf_del.py
```

Вывод:

```
delete_repo: OK
VERIFIED GONE: RepositoryNotFoundError 404 Client Error. (Request ID: Root=1-6ad9dfec-...)
```

Проверка через `api.repo_info(repo_id="Titlehhhh/captchaocr-dataset-v2", repo_type="dataset")`
теперь **бросает `RepositoryNotFoundError` (404)** — репозитория нет. Запасной вариант
(сделать приватным) **не понадобился**: удаление прошло с первого раза.

В удалённый репозиторий к моменту удаления успело уехать 10 546 файлов (22 батча из 47) —
они исчезли вместе с ним. Никаких следов в существующем `Titlehhhh/captchaocr-dataset` это
не оставило: существовавший там контент не трогали до начала основной загрузки.

---

## 2. Что было загружено

### Раскладка (не изменилась)

```
data/out/<owner>/<repo>/<type>/NNN.png      + data/out/<owner>/<repo>/<type>/labels.jsonl
data/out_ru/<Plugin>/<type>/NNN.png         + data/out_ru/<Plugin>/<type>/labels.jsonl
README.md · LICENSE · dataset_inventory.json · .gitattributes
```

`data/` — тот же префикс, что и до публикации; `tools/fetch_dataset.py` ходит по этому же
пути и правок не потребовал.

### Состав

| что | сколько |
|---|---|
| типов капчи | 46 (34 в `out` + 12 в `out_ru`) |
| PNG | **23 000** (ровно 500 на тип) |
| `labels.jsonl` | **46** (по 500 строк в каждом) |
| строк в `labels.jsonl` суммарно | 23 000 |
| размер PNG | 228 769 043 Б (218.2 МБ) |
| размер всего репозитория | 235 814 831 Б (224.8 МБ) |
| `real_shots` | **не опубликованы** (0 файлов на сервере) |

Загружено **23 036** файлов за **48 коммитов**:

* 1 коммит — метаданные (`README.md`, `dataset_inventory.json`, `LICENSE`);
* 1 коммит — все 46 `labels.jsonl` (6.6 МБ, аудит-тропа — залит первым, как и требовалось);
* 46 коммитов — PNG по одному типу капчи (по 500 файлов), с ретраями (до 4 попыток,
  пауза 8/16/24/32 с).

### Что изменилось по сравнению с прежней публикацией

Прежняя версия репозитория содержала 100 картинок на тип (4 600 PNG). Датасет перерисован,
поэтому:

* файлы `001.png`–`100.png` **перезаписаны** новым рендером (сравнение идёт **по
  содержимому** — sha256 для LFS-файлов, git-sha1 для обычных, — а не по размеру,
  иначе старые картинки молча остались бы);
* файлы `101.png`–`500.png` **добавлены**;
* `labels.jsonl` перезаписаны: было 100 строк, стало 500.

Итог: репозиторий содержит полный набор 500 на тип. Старые файлы не удалялись — они
перезаписаны теми же путями.

### Чего в репозитории нет

* **`dataset/out_ru/**/real_shots/**` — 517 эталонных скриншотов чужих плагинов (523 файла
  вместе с заметками `.md`/`.txt`) — НЕ опубликованы.** Проверено на сервере: путей,
  содержащих `real_shots`, в удалённом дереве **0**. Скрипт исключает их по построению
  (тип = каталог с `labels.jsonl`, а в `real_shots` меток нет) и дополнительно
  утверждает это перед загрузкой.
* Ни картинок, ни страниц, ни ответов сторонних коммерческих сервисов.
* Ни весов модели, ни логов обучения, ни файлов измеренных результатов.

---

## 3. Карточка репозитория

`README.md` перезаписан и **проверен на сервере** (скачан обратно и прочитан).

YAML-фронтматтер:

```yaml
license: other
license_name: mixed-per-plugin-licences
tags: [captcha, ocr, minecraft, anti-bot, synthetic]
language: [en, ru]
library_name: datasets
format: imagefolder
modality: image
size_categories: 10K<n<100K
```

Что карточка говорит (дословно, фрагменты с сервера):

* «**46 captcha types × 500 images = 23000 PNG.** Every type was re-rendered on
  **2026-10-22** on the author's machine with the project's **Java 21** generators
  (`dataset/generator` and `dataset/generator_ru`), then validated and uploaded.»
* «This dataset is a **machine artefact**. The generators are **not seeded**: the fonts are
  the same, but the samples themselves are random, so a re-render of the same type produces
  a *different* set of pictures.»
* «The reference screenshots of the upstream plugins (the `real_shots/` folders of the Russian
  tree — 517 reference screenshots, 523 files in total) are **not published here**.»
* Лицензия — **та же разбивка, что и раньше**, ничего не выдумано: таблица плагинов
  (лицензия апстрима + режим faithful/clean-room/reconstructed) и сводка «лицензия → типы → PNG»
  считаются из `labels.jsonl` и проектной таблицы `PLUGIN_LICENCES` в `tools/publish_hf.py`
  в момент загрузки. Ни одна лицензия не придумана: там, где апстрим лицензии не давал,
  стоит «no licence (all rights reserved)» / «не установлена (см. source в labels.jsonl)».
* Распределение режимов (из `dataset_inventory.json` на сервере):
  **faithful 25 · clean-room 16 · reconstructed 5**; 23 апстрим-плагина, 2 дерева,
  129 символов в объединённом алфавите, 29 типов с полосой (`roi`), 9 типов, где
  `text != answer`.

`LICENSE` тоже перезаписан (та же таблица лицензий, пересчитанная под 23 000 PNG),
`dataset_inventory.json` — пересчитан и залит.

`.gitattributes` **не перезаписывался**: в репозитории уже лежит стандартный шаблон
Hugging Face (`*.png filter=lfs diff=lfs merge=lfs -text` и т.д.), и он корректен —
переписывать его значило бы сломать LFS-обработку PNG. Наличие файла проверено.

---

## 4. Проверка (что реально измерено)

### 4.1 Проверка через API — числа с сервера

```powershell
$env:HF_HOME="C:\Users\Title\Projects\CapthaModel\.hf-cache"
$env:PYTHONIOENCODING="utf-8"
python tools\upload_dataset.py --verify
```

Вывод:

```
types found:     46
png found:       23000
labels found:    46
real_shots (not published): 517 PNG in 523 files
repo:            Titlehhhh/captchaocr-dataset
last commit:     6248c5b9b6ce7eb6e917efd7aa3952892beb7cea
remote PNG:      23000
remote labels:   46
remote bytes:    235724437 (224.8 МБ)
local PNG:       23000
local labels:    46
local bytes:     235724437 (224.8 МБ)

last commits:
  6248c5b9b6ce7eb6e917efd7aa3952892beb7cea  CaptchaOCR dataset: card, inventory, license
  ee171e3fc3217378d462b9b32d5c5546beab4323  CaptchaOCR dataset: png: out_ru/LimboFilter/symbols
  537fc6520b985af2d3f34440ef7b1f72c020136d  CaptchaOCR dataset: png: out_ru/LimboFilter/map
OK
```

`remote bytes` (235 724 437) совпадает с `local bytes` **до байта** — это сумма размеров
PNG + `labels.jsonl` по дереву.

### 4.2 Независимая проверка через API (отдельный скрипт, не через `upload_dataset.py`)

```python
entries = list(api.list_repo_tree(repo_id="Titlehhhh/captchaocr-dataset",
                                  repo_type="dataset", recursive=True))
files = [e for e in entries if isinstance(e, RepoFile)]
```

Вывод:

```
repo id:    Titlehhhh/captchaocr-dataset
private:    False | gated: False
sha:        ee171e3fc3217378d462b9b32d5c5546beab4323
remote PNG:       23000
remote labels:    46
remote all files: 23050
top-level:        ['.gitattributes', 'LICENSE', 'README.md', 'data', 'dataset_inventory.json']
real_shots paths: 0
total bytes:      235814831
types on remote:  46
types != 500 PNG: none
local types/PNG/rows: 46 23000 23000
remote label rows: 23000 | !=500: none
content-checked: 23000 | mismatches: 0 []
```

Что это значит по пунктам:

* **23000 PNG** и **46 `labels.jsonl`** на сервере; в корне — только `.gitattributes`,
  `LICENSE`, `README.md`, `data`, `dataset_inventory.json`;
* **0 путей с `real_shots`**;
* **46 типов на сервере, у каждого ровно 500 PNG** (`types != 500 PNG: none`);
* **23000 строк** в удалённых `labels.jsonl`, в каждом файле ровно 500;
* **content-checked: 23000 | mismatches: 0** — для **каждого** PNG сравнён sha256 удалённого
  LFS-объекта с sha256 локального файла. То есть на сервере лежат именно те картинки,
  что в рабочем дереве, а не «похожие» (это и подтверждает, что 001–100 действительно
  перезаписаны новым рендером).

### 4.3 История коммитов не переписана

```
total commits: 79
   0edfaeb174f1  CaptchaModel dataset: 200 files      <- старые коммиты на месте
   3d4cbc5f97df  CaptchaModel dataset: 200 files
   2553440bbbd7  CaptchaModel dataset: 200 files
   340ce0db3b37  initial commit                        <- самый первый коммит
```

Всего 79 коммитов; новые 48 добавлены **поверх** старых, «initial commit» и коммиты прежней
публикации (4600 PNG) на месте. Это **добавление**, а не переписывание истории
(force-push / `reset --hard` не делались — скрипт умеет только `create_commit`).

### 4.4 Идемпотентность (повторный запуск ничего не перезаливает)

```powershell
python tools\upload_dataset.py --dry-run
```

```
remote files:    23050
unchanged (skipped): 46
batches:               0
files to upload:       0
```

Все 23 000 PNG и 46 `labels.jsonl` совпали с сервером **по содержимому** — повторный
запуск не отправляет ничего лишнего.

---

## 5. Точные команды

```powershell
# токен и кодировка — перед КАЖДЫМ вызовом HF
$env:HF_HOME="C:\Users\Title\Projects\CapthaModel\.hf-cache"
$env:PYTHONIOENCODING="utf-8"
$env:HF_HUB_DISABLE_PROGRESS_BARS="1"

hf auth whoami                                   # user: Titlehhhh

python tools\upload_dataset.py --dry-run        # план, ничего не грузится
python tools\upload_dataset.py                  # загрузка (метки -> PNG по типам)
python tools\upload_dataset.py --verify         # проверка удалённого дерева
```

Ключевые вызовы API, которыми всё делалось и проверялось:

```python
api.delete_repo(repo_id="Titlehhhh/captchaocr-dataset-v2", repo_type="dataset")
api.repo_info(repo_id="Titlehhhh/captchaocr-dataset-v2", repo_type="dataset")   # -> 404
api.create_commit(repo_id="Titlehhhh/captchaocr-dataset", operations=[...],
                  repo_type="dataset", commit_message="...")
api.list_repo_tree(repo_id="Titlehhhh/captchaocr-dataset", repo_type="dataset",
                   recursive=True)
api.list_repo_commits(repo_id="Titlehhhh/captchaocr-dataset", repo_type="dataset")
```

---

## 6. Что сломалось / что чинилось по пути

| проблема | где | как решено |
|---|---|---|
| `publish_hf.remote_file_sizes()` падал с `RepositoryNotFoundError` на несуществующем репозитории | `tools/publish_hf.py` (чужой файл, не правился) | в `tools/upload_dataset.py` написана своя `remote_file_sizes()`: в huggingface_hub 1.x `list_repo_tree` — **генератор**, и 404 прилетает уже во время итерации, поэтому try накрывает и создание списка, и проход по нему |
| сравнение файлов по размеру пропустило бы старые картинки 001–100 | `tools/upload_dataset.py` | сравнение по **содержимему**: sha256 (LFS) / git-sha1 (обычные файлы); проверено — 0 расхождений на 23 000 файлах |
| `AttributeError: 'RepoFolder' object has no attribute 'size'` в проверочном скрипте | мой одноразовый скрипт в `$env:TEMP` | фильтр `isinstance(e, RepoFile)` вместо `e.type` |
| `NameError: name 'types' is not defined` / `AttributeError: 'dict' object has no attribute 'labels_path'` в `build_card()` | `tools/upload_dataset.py` | лишняя строка внутри функции удалена, `labels_bytes` передаётся параметром |
| первый запуск в `Titlehhhh/captchaocr-dataset-v2` (создан по исходному брифу) | — | репозиторий **удалён**, существование подтверждено 404 |
| в карточке сначала стояло «523 reference screenshots» | `tools/upload_dataset.py` | разделено: **517** скриншотов (PNG) и **523** файла всего (включая 5 `.md` и 1 `.txt`); карточка перезалита |
| размер в карточке был назван «total size», хотя это только PNG | `tools/upload_dataset.py` | стало две строки: «size of the PNG files» и «size of the whole repository» |

Сеть работала стабильно: **ни один из 48 коммитов не потребовал ретрая**.

---

## 7. Что НЕ проверено

* **Не проверено, что картинки визуально корректны.** Проверка — это байтовое совпадение
  локальных и удалённых файлов; «содержимое PNG правильное» не проверялось. Локально
  датасет проходил `dev.captcha.Validate` и чекеры проекта, но это работа **другого** агента
  и её результат здесь не переигрывался.
* **Не проверена загрузка через `datasets`/`imagefolder`.** Библиотека `datasets` с этим
  репозиторием не запускалась — публикуются плоские файлы, а не скрипт загрузки; формат
  заявлен как `imagefolder`, но `load_dataset("imagefolder", ...)` не проверялся.
* **Не проверено, что `tools/fetch_dataset.py` скачивает новую версию** — скрипт не
  запускался против живого репозитория (раскладка путей сохранена, это проверено по
  `list_repo_tree`, но не скачиванием).
* **Не проверены приватность/гейтинг после всех коммитов** — `private=False`, `gated=False`
  прочитаны из `repo_info` **до** последнего коммита карточки; после него проверялось
  только дерево и история. Поскольку новый коммит не меняет настройки репозитория,
  риск нулевой, но формально это не перепроверено.
* **Не проверено, как выглядит карточка на сайте** — читался только скачанный `README.md`
  (то есть ровно то, что отдаёт CDN).
* Не измерялась скорость/трафик загрузки (46 коммитов по 500 файлов заняли ~11 минут).

---

## 8. Итог

| | |
|---|---|
| репозиторий | <https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset> (dataset, публичный) |
| repo id | `Titlehhhh/captchaocr-dataset` |
| итоговый коммит | `6248c5b9b6ce7eb6e917efd7aa3952892beb7cea` |
| PNG на сервере | **23 000** (46 типов × 500) |
| `labels.jsonl` на сервере | **46** (по 500 строк) |
| размер | 235 724 437 Б (PNG + метки), 235 814 831 Б со всеми файлами репозитория |
| `real_shots` на сервере | **0** |
| новых репозиториев | **0** (временный `captchaocr-dataset-v2` удалён) |
| коммитов добавлено | 48 (история не переписана, всего 79) |
