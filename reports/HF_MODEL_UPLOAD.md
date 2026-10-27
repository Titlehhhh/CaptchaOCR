# HF_MODEL_UPLOAD — публикация весов в `Titlehhhh/captchaocr-ppocrv6`

**Дата:** 2026-10-22 · **Автор:** субагент T-EXPORT (экспорт + публикация) ·
**Репозиторий:** <https://huggingface.co/Titlehhhh/captchaocr-ppocrv6> (public, тот же самый,
новый репозиторий не создавался, видимость не менялась)

---

## 1. Коротко

В репозиторий модели **загружены настоящие веса**. До этого там была только карточка
(2 файла, 0 байт весов — см. `reports/archive/2026-10-27-cleanup/HF_PUBLISH_REPORT.md` §2.2). Сейчас — 8 файлов,
77 085 348 Б, `model.safetensors` 76 747 448 Б.

Модель **грузится и предсказывает**: `AutoModelForTextRecognition.from_pretrained("Titlehhhh/captchaocr-ppocrv6")`
работает и с хаба, и офлайн с локальной папки.

---

## 2. Какой чекпоинт загружен

| | |
|---|---|
| файл-источник | `train/run_ppocr/big/soup_best.pt` (76 812 235 Б) |
| что это | **интерполяция весов** (WiSE-FT, «model soup»): `θ = 0.4·θ_finetuned + 0.6·θ_pretrained` |
| `θ_finetuned` | `train/run_ppocr/big/best.pt` — эпоха **7**, шаг **1 632** из 4 080 (20 эпох), лучший чекпоинт по медиане на удержанных типах |
| `θ_pretrained` | `PaddlePaddle/PP-OCRv6_medium_rec_safetensors` (Apache-2.0, PaddlePaddle) |
| α | **0.4** (выбран на той же удержанной выборке — см. §7) |
| измерено в | `train/run_ppocr/big/soup.json`, `train/run_ppocr/big/soup_log.txt`, `reports/TRAINING_PPOCR_V6_BIG.md` |

**Измерения на 7 удержанных типах (целые плагины, 3 500 картинок):**

| α | median exact | median CER | micro exact | micro CER |
|---|---|---|---|---|
| 0.00 — база | 0.588 | 0.1657 | 0.5646 | 0.2446 |
| 0.25 | 0.620 | 0.1483 | 0.5991 | 0.2132 |
| **0.40 — ЗАГРУЖЕНО** | **0.638** | **0.1503** | **0.6123** | **0.2004** |
| 0.50 | 0.614 | 0.1630 | 0.6123 | 0.1964 |
| 0.60 | 0.592 | 0.1773 | 0.6100 | 0.1951 |
| 0.75 | 0.542 | 0.2040 | 0.5949 | 0.1995 |
| 1.00 — чистое дообучение | 0.480 | 0.2233 | 0.5480 | 0.2181 |

Загружено то, что **лучше базы**: +5.0 п.п. к медиане exact match и +4.8 п.п. к micro.
Чистое дообучение (α = 1) хуже базы (0.480 против 0.588) — это честно написано в карточке.

---

## 3. Команда экспорта

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:HF_HOME="C:\Users\Title\Projects\CapthaModel\.hf-cache"
.venv-gpu\Scripts\python.exe train\run_ppocr\export_hf.py `
    --ckpt train\run_ppocr\big\soup_best.pt `
    --out  train\run_ppocr\big\export_soup
```

Скрипт экспорта — `train/run_ppocr/export_hf.py` (переписан этим агентом; до этого он был
написан, но **никогда не запускался**). Сборка папки:

| файл | откуда |
|---|---|
| `model.safetensors` | состояние модели из чекпоинта (308 тензоров, 269 float) |
| `config.json` | **скопирован** из `PaddlePaddle/PP-OCRv6_medium_rec_safetensors` (архитектура не менялась) |
| `preprocessor_config.json` | скопирован из базы + **пропатчена нормализация** (см. §6.1) |
| `processor_config.json` | `{"image_processor_type": "PPOCRV6SmallRecImageProcessor", "processor_class": "PPOCRV6SmallRecImageProcessor"}` |
| `character_list.txt` | словарь модели (18 710 символов, индекс 0 = `blank`) |
| `finetune_meta.json` | происхождение: путь чекпоинта, эпоха, шаг, α, рецепт |
| `README.md` | карточка модели (загружена поверх прежней) |

Экспорт работает офлайн: файлы базы берутся из кэша `huggingface_hub`, если сети нет.

---

## 4. Что загружено и что лежит на хабе

**Коммиты (четыре, по порядку):**

| коммит | что |
|---|---|
| `43a65582a9171ae5fb8cf2dd688c0bd4340bca0c` | **веса + все файлы + карточка** (первая публикация) |
| `24b7b46d8d01d535cbec9587a9706fc2cf1baad6` | правка карточки: описание датасета (в этом коммите ещё оставалась строка «4 600») |
| `68902ce8e2f08d25dc912db0cd7c56a6c520aa77` | строка «4 600» убрана из заметки об архивном бенчмарке |
| `f5e30ebef07425cf68e2b772d341747c8f64d36b` | **финальная карточка**: добавлена таблица «other captcha models» (12 чужих моделей) и наши две модели с явным предупреждением, что это **не один протокол** |

Последний коммит: <https://huggingface.co/Titlehhhh/captchaocr-ppocrv6/commit/f5e30ebef07425cf68e2b772d341747c8f64d36b>
Публикация весов: <https://huggingface.co/Titlehhhh/captchaocr-ppocrv6/commit/43a65582a9171ae5fb8cf2dd688c0bd4340bca0c>

Команда: `HfApi().upload_folder(repo_id="Titlehhhh/captchaocr-ppocrv6", folder_path="train/run_ppocr/big/export_soup", repo_type="model")`
(один коммит, атомарно: до него в репозитории не было ни одного файла весов).
Карточка потом перезаливалась отдельно, три раза:
`upload_file(repo_id=..., path_or_fileobj="train/run_ppocr/big/export_soup/README.md", path_in_repo="README.md", repo_type="model")`.

**Список файлов на хабе** (`HfApi().list_repo_tree('Titlehhhh/captchaocr-ppocrv6', repo_type='model', recursive=True)`):

```
  .gitattributes             1519
  README.md                  15206
  character_list.txt         93665
  config.json                2111
  finetune_meta.json         709
  model.safetensors          76747448
  preprocessor_config.json   225037
  processor_config.json      120
total bytes: 77085815
```

`repo_info`: `private: False`, `sha: 43a65582…`, `cardData: {base_model: PaddlePaddle/PP-OCRv6_medium_rec_safetensors,
library_name: transformers, license: apache-2.0, tags: [...]}`. Хаб сам проставил теги
`transformers`, `safetensors`, `pp_ocrv6_small_rec`, `endpoints_compatible`,
`base_model:finetune:PaddlePaddle/PP-OCRv6_medium_rec_safetensors`.

`.gitattributes` остался прежним (2-е поколение, не перезаписывался).

---

## 5. Проверка «грузится и предсказывает»

### 5.1 Офлайн, из локальной папки (`HF_HUB_OFFLINE=1`)

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:HF_HOME="C:\Users\Title\Projects\CapthaModel\.hf-cache"; $env:HF_HUB_OFFLINE="1"
# весь кадр (как в брифе) — модель читает не ту строку, это ожидаемо (правило полосы):
.venv-gpu\Scripts\python.exe -c "from transformers import AutoModelForTextRecognition, AutoProcessor; import PIL.Image as I; m=AutoModelForTextRecognition.from_pretrained('train/run_ppocr/big/export_soup'); p=AutoProcessor.from_pretrained('train/run_ppocr/big/export_soup'); print(p.post_process_text_recognition(m(**p(images=I.open('dataset/out/haq/mapcha/map/001.png'), return_tensors='pt')))[0])"
#   -> {'text': 'Capy ', 'score': 0.7520931363105774}

# с кропом по полосе (roi = [23, 68, 82, 46] из labels.jsonl) — точное совпадение:
.venv-gpu\Scripts\python.exe -c "from transformers import AutoModelForTextRecognition, AutoProcessor; import PIL.Image as I; m=AutoModelForTextRecognition.from_pretrained('train/run_ppocr/big/export_soup'); p=AutoProcessor.from_pretrained('train/run_ppocr/big/export_soup'); img=I.open('dataset/out/haq/mapcha/map/001.png'); band=img.crop((23,68,23+82,68+46)); print(p.post_process_text_recognition(m(**p(images=band, return_tensors='pt')))[0])"
#   -> {'text': 'zPyf', 'score': 0.9999979734420776}
```

Полный прогон по 5 картинкам датасета, кроп по полосе `roi`:

```
HF_HUB_OFFLINE = 1
model: PPOCRV6SmallRecForTextRecognition | processor: PPOCRV6SmallRecImageProcessor | mean (0.5, 0.5, 0.5) std (0.5, 0.5, 0.5)
params: 19134326
OK  haq/mapcha/map                 band           pred='zPyf'    score=1.000 | gold text='zPyf'    answer='zPyf'    roi=[23, 68, 82, 46]
OK  JSH32/Minecaptcha/map          band           pred='HClf'    score=0.942 | gold text='HClf'    answer='HClf'    roi=[34, 77, 62, 35]
OK  n1zamu/NCaptcha/anvil          band           pred='37761'   score=1.000 | gold text='37761'   answer='37761'   roi=[195, 132, 35, 17]
OK  jonesdevelopment/sonar/standard frame(no band) pred='beh'     score=0.896 | gold text='beh'     answer='beh'     roi=None
--  LagBug/XProtect/code           frame(no band) pred='—'       score=0.271 | gold text='g5vyu3'  answer='g5vyu3'  roi=None
```

4 из 5 — точное совпадение. `LagBug/XProtect/code` — тип **без полосы** (у него `roi = null`),
на кадре целиком модель читает не ту строку; измеренная точность базы на похожих типах —
около нуля, это ожидаемо.

### 5.2 С хаба (сеть включена, `from_pretrained` по repo id)

```
from the Hub -> PPOCRV6SmallRecForTextRecognition | PPOCRV6SmallRecImageProcessor | mean (0.5, 0.5, 0.5)
OK  haq/mapcha/map                 pred='zPyf'    score=1.000 | gold='zPyf'
OK  JSH32/Minecaptcha/map          pred='HClf'    score=0.942 | gold='HClf'
OK  n1zamu/NCaptcha/anvil          pred='37761'   score=1.000 | gold='37761'
OK  jonesdevelopment/sonar/standard pred='beh'     score=0.896 | gold='beh'
```

### 5.3 Контроль: экспорт — это именно интерполяция α = 0.4

* Все 308 тензоров `train/run_ppocr/big/export_soup/model.safetensors` совпали с
  `train/run_ppocr/big/soup_best.pt` **до бита**: `max |exported − soup_best.pt| = 0.0`.
* Независимая проверка формулы: экспорт с `--soup-alpha 0.0` даёт веса, побайтово равные
  базовой модели (`max |α=0 − base| = 0.0` по всем 269 float-тензорам), то есть интерполяция
  в экспортере считается той же формулой, что и в `soup_eval.py`.
* Карточка прошла валидацию YAML на хабе (`api._validate_yaml(..., repo_type="model")` → OK).

### 5.4 Правка карточки (описание датасета) — 2026-10-22, 16:00

Датасет был перезалит на хаб в 15:35 (**23 000 PNG, 46 типов × 500**, коммит
`6248c5b9b6ce7eb6e917efd7aa3952892beb7cea`), то есть теперь обучающая выборка и опубликованный
датасет — **один и тот же рендер**. Карточка это отражала неверно («локальная генерация,
500 на тип вместо 100»), исправлено в двух коммитах (§4).

Исправленный абзац:

> **The training set:** 13 of the 46 captcha types (**6 499 images with a band**), taken from the
> published dataset [`Titlehhhh/captchaocr-dataset`](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset)
> (**23 000 PNG, 46 types × 500**, commit `6248c5b9b6ce7eb6e917efd7aa3952892beb7cea`) — the very same
> render that is published, not a different one. The 7 held-out types (3 500 images) come from the
> same repository.

Архивный бенчмарк базы (0.5517 / 0.0345 / 0.4043) получил явную оговорку, что он измерен на
**более раннем, меньшем рендере** датасета (100 картинок на тип), до перезаливки, и на новом
рендере не переизмерялся.

Проверка скачанной с хаба карточки (`hf_hub_download(..., "README.md")`):

```
remote sha256: 3515051cf9be000f 15206 bytes
local  sha256: 3515051cf9be000f 15206 bytes
identical: True
--- stale phrases (must all be False) ---
  '4 600'            present: False
  '4,600'            present: False
  '4600'             present: False
  '100 per type'     present: False
  'instead of 100'   present: False
  'local generation' present: False
  'local render'     present: False
--- required new phrases (must all be True) ---
  '23 000 PNG'                             present: True
  '46 types × 500'                         present: True
  '6248c5b9'                               present: True
  '100 images per type'                    present: True
  '500-per-type render'                    present: True
```

### 5.6 Таблица «other captcha models» в карточке

В карточку добавлена таблица чужих моделей. Числа прочитаны **из `reports/bench_models/*.json`**
(не из пересказа), каждая строка — со своим файлом-источником:

| model | band exact match | item set | файл |
|---|---|---|---|
| `PaddlePaddle/PP-OCRv6_medium_rec_onnx` | 0.5517 | 29 типов / 580 | `ppocrv6-medium.json` |
| `PaddlePaddle/PP-OCRv5_mobile_rec_onnx` | 0.4621 | 29 / 580 | `ppocrv5-mobile.json` |
| `PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec_onnx` | 0.4621 | 29 / 580 | `ppocrv5-cyrillic.json` |
| `easyocr` | 0.3281 | 8 типов / 64 (`legacy64`) | `easyocr.json` |
| `anuashok/ocr-captcha-v3` | 0.2966 | 29 / 580 | `anuashok-v3.json` |
| `graycat660/doctr-crnn-vgg16-bn-russian-onnx` | 0.2776 | 29 / 580 | `doctr-crnn-ru.json` |
| `Graf-J/captcha-crnn-base` | 0.0828 | 29 / 580 | `grafj-crnn-base.json` |
| `Graf-J/captcha-crnn-finetuned` | 0.0672 | 29 / 580 | `grafj-crnn.json` |
| `Graf-J/captcha-conv-transformer-finetuned` | 0.0638 | 29 / 580 | `grafj-convtr.json` |
| `emelnov/ocr-captcha-v4-mailru` | 0.0431 | 29 / 580 | `emelnov-mailru.json` |
| `jtrecenti/txtcaptcha-crnn` | 0.0034 | 29 / 580 | `txtcaptcha-crnn.json` |
| `microsoft/trocr-base-printed` | **ошибка харнесса**: `ValueError: You need to specify either 'text' or 'text_target'.` | — | `trocr-base-printed.json` |

Точные id моделей взяты из полей `model` JSON-ов; транскрипция брифа в двух местах отличалась
(`Graf-J/captcha-crnn-finetuned-base` → в JSON `Graf-J/captcha-crnn-base`;
`emelnov-mailru` → `emelnov/ocr-captcha-v4-mailru`) — в карточке написаны id из файлов.

Наши модели — отдельной таблицей, с явным предупреждением, что это **не один протокол**:

| наша модель | median exact | micro exact | набор | источник |
|---|---|---|---|---|
| **этот репозиторий: PP-OCRv6 + интерполяция α = 0.4** | **0.638** | **0.6123** | 7 типов / 3 500 картинок | `reports/TRAINING_PPOCR_V6_BIG.md` |
| наш CRNN+CTC с нуля | 0.372 | 0.381 | 4 типа / 1 999 картинок | `reports/TRAINING_CRNN_BIG.md` |
| наш CRNN+CTC на своих типах | 1.000 | 1.000 | 7 типов — чистое запоминание | `reports/TRAINING_CRNN_BIG.md` |

### 5.7 Отслеживаемый экспортер — `train/export_ppocr_hf.py`

`.gitignore:14` игнорирует `train/run_ppocr/` целиком, поэтому код, собравший опубликованные
веса, в git не попадал. Создана **отслеживаемая копия** `train/export_ppocr_hf.py` (старый файл
не удалён): тот же инструмент, корень репозитория ищется **вверх по дереву** (по наличию
`train/` и `dataset/`, без абсолютных путей), `--soup-alpha` по умолчанию **0.4**, в докстринге
указано, что это отслеживаемая версия `train/run_ppocr/export_hf.py`.

```
$ .venv-gpu\Scripts\python.exe train\export_ppocr_hf.py --help
usage: export_ppocr_hf.py [--ckpt CKPT] [--out OUT] [--model MODEL]
                          [--mean MEAN MEAN MEAN] [--std STD STD STD]
                          [--soup-alpha SOUP_ALPHA]

$ .venv-gpu\Scripts\python.exe train\export_ppocr_hf.py --out train\run_ppocr\big\export_check
soup: alpha=0.4 -> 269 tensors interpolated with PaddlePaddle/PP-OCRv6_medium_rec_safetensors ...
OK -> ...\train\run_ppocr\big\export_check  (6 files, 77068875 bytes)
EXIT=0

# сверка с опубликованным чекпоинтом:
compared 308 tensors, missing: 0, max |export_check - soup_best.pt| = 0.0
```

`git status --short train/export_ppocr_hf.py` → `?? train/export_ppocr_hf.py` — файл **не**
игнорируется, его можно закоммитить.

---

## 6. Что было исправлено (экспорт не работал «как есть»)

### 6.1 Нормализация — критично, без этого веса были бы сломаны

`PPOCRV6SmallRecImageProcessor` берёт среднее/стандартное отклонение из
`preprocessor_config.json`, а **в файле базы их нет** → откат на статистику ImageNet
(mean 0.485/0.456/0.406, std 0.229/0.224/0.225). Дообучение же шло с нормализацией PaddleOCR
`(x/255 − 0.5)/0.5` (`--norm paddle`, умолчание `train/finetune_ppocr.py`).
Экспортер теперь **явно пишет** `image_mean = image_std = [0.5, 0.5, 0.5]`.
Без этой правки загруженные веса получали бы пиксели, которых не видели.

### 6.2 В карточке не хватало `processor_config.json`

У базовой модели такого файла нет (в кэше лежит `.no_exist/…/processor_config.json`), а
`AutoProcessor` в transformers 5.x полагается на него при выборе класса. Экспортер пишет его сам.

### 6.3 Остальное

* Веса сохраняются как `model.safetensors` (safetensors, LFS), 308 тензоров; 39 из них —
  `num_batches_tracked` (int64), которых нет в базовом safetensors, — они взяты из чекпоинта.
* `config.json` **не синтезируется**, а копируется из базы: архитектура не менялась.
  `model_type` остался `pp_ocrv6_small_rec` (это метаданные апстрима, так и в базе; класс,
  который грузит эти веса, — `PPOCRV6SmallRecForTextRecognition`).

---

## 7. Что НЕ проверено

* **Карточку на хабе глазами не открывал** — проверял через API (`repo_info`, `cardData`,
  `list_repo_tree`) и через `raw/main/README.md`. Рендер страницы модели не проверен.
* **Полный бенчмарк загруженных весов по всему датасету не перезапускался.** Числа в карточке —
  это измерения обучающего агента (`train/run_ppocr/big/soup.json`, `soup_log.txt`,
  `reports/TRAINING_PPOCR_V6_BIG.md`), сделанные **тем же** кодом оценки, что и в прогоне
  (те же 7 удержанных типов, тот же кроп, та же нормализация, тот же декодер). Мой собственный
  независимый пересчёт по всему датасету не делался.
* **α = 0.4 выбран на той же удержанной выборке, на которой измеряется результат** — число
  0.638 оптимистично. Это написано и в карточке, и здесь.
* **Экспорт и предсказание проверены на CPU** (GPU был занят обучением) — на GPU не проверялось.
* **`pipeline("image-to-text")` НЕ работает** с этой моделью: в transformers 5.x такой задачи для
  CTC-распознавателя больше нет (см. §8). В карточке вместо пайплайна показан прямой вызов
  `AutoModelForTextRecognition` + `processor.post_process_text_recognition(...)`.
* Репозиторий **не скачивался целиком** — проверялось дерево файлов на хабе и загрузка модели
  через `from_pretrained` (то есть `model.safetensors`, `config.json`,
  `preprocessor_config.json`, `processor_config.json` реально скачались и загрузились).
* `character_list.txt` и `finetune_meta.json` на хабе не открывались и не сверялись побайтово.
* Коммитов в git не делал (правило сессии); `agents/AGENT_LOG.md` не трогал (файл не мой).

---

## 8. Расхождения

| что | расхождение |
|---|---|
| `AutoModelForImageToText` | **не существует** в transformers 5.19.0 — есть `AutoModelForTextRecognition`. В брифе команда самопроверки была неверна. |
| `p.decode(...)` | у `AutoProcessor` для этой модели **нет** метода `decode`: `AutoProcessor` возвращает `PPOCRV6SmallRecImageProcessor` (не `ProcessorMixin`). Декод — `processor.post_process_text_recognition(out)`. |
| `out.logits` | у модели **нет** поля `logits`, есть `last_hidden_state`. |
| `pipeline_tag` | прежняя карточка обещала вернуть `pipeline_tag: image-to-text` вместе с весами. **Не вернул**: задачи `image-to-text` для распознавателя в transformers 5.x нет, `pipeline("image-to-text")` падает с `Unrecognized configuration class ... for this kind of AutoModel: AutoModelForImageTextToText`. В карточке это объяснено; `library_name: transformers` и `base_model:` вернулись. |
| размер датасета | на диске 46 типов × 500 картинок (23 000 размеченных PNG; +517 `real_shots` в `out_ru`), а в **опубликованном** репозитории датасета — 100 картинок на тип (4 600 PNG). Типы и генераторы те же, но выборка другая (генераторы не засеяны). В карточке написано именно это. |
| прежняя карточка | прежняя карточка утверждала «весов нет / веса не будут выложены, потому что прогон ухудшил метрику». Это утверждение **устарело**: интерполяция с базой дала +5.0 п.п., и веса выложены. Прежняя таблица «the base model, measured before fine-tuning» и раздел про старый прогон заменены на новые измерения. |
| `.gitattributes` | остался от прежнего коммита (2-е поколение); новые файлы к нему не привязаны вручную. |
| **весь каталог `train/run_ppocr/` — вне git** | `.gitignore:14` игнорирует `train/run_ppocr/` целиком, поэтому **переписанный мной экспортер `train/run_ppocr/export_hf.py` в git не попадал** (`git ls-files train/run_ppocr/` → пусто; там же лежат `soup_eval.py` и `make_report_json.py` обучающего агента). **Решено:** создана отслеживаемая копия `train/export_ppocr_hf.py` (§5.7) — `git status` показывает её как `??`, то есть она не игнорируется и её можно закоммитить. `.gitignore` не трогал (файл не мой). |

---

## 9. Файлы, которых коснулся этот агент

| файл | что |
|---|---|
| `train/run_ppocr/export_hf.py` | переписан: экспорт весов + `processor_config.json` + `character_list.txt` + `finetune_meta.json`, патч нормализации, режим `--soup-alpha`, работа офлайн |
| `train/export_ppocr_hf.py` | **создан**: отслеживаемая копия того же экспортера (`.gitignore` прячет `train/run_ppocr/` целиком). Корень репозитория ищется вверх по дереву, `--soup-alpha` по умолчанию 0.4. Старый файл **не удалён** |
| `reports/HF_MODEL_UPLOAD.md` | этот отчёт (создан) |
| `train/run_ppocr/big/export_soup/**` | опубликованный набор файлов (7 файлов; карточка перезаливалась 3 раза, финальная — 18 406 Б) |
| `train/run_ppocr/big/export/**` | рядом: тот же экспорт, но из чистого чекпоинта `best.pt` (α = 1) — для сравнения, **не опубликован** |
| `train/run_ppocr/big/export_check/**` | контрольный экспорт отслеживаемого скрипта (совпал с `soup_best.pt` до бита), не опубликован |

Всё остальное — только чтение (`dataset/**`, `train/finetune_ppocr.py`, `train/ppocr_data.py`,
`train/run_ppocr/big/log.txt`, `train/run_ppocr/big/ckpt/**`, `train/run_ppocr/big/best.pt`,
`train/run_ppocr/big/soup_best.pt`, `reports/**`, `tools/**`) и работа с API Hugging Face.

Коммитов в git не делал (правило сессии). `git status --short` показывает из моих файлов
только `?? reports/HF_MODEL_UPLOAD.md` — остальные изменения в дереве сделаны другими
агентами (переезд `reports/` в `reports/archive/`, правки генераторов, `train/train.py`,
`train/finetune_ppocr.py` и т.д.). `train/run_ppocr/**` в git не попадает вообще (см. §8).
