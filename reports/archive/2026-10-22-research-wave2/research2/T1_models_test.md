# T1 — Тест готовых моделей на нашем датасете

**Волна 2, тест T1. Дата прогона:** 2026-10-22.
**Задача:** скачать готовые модели, запустить их на нашем датасете по **единому протоколу** (полоса `roi`,
exact match + CER, пер-тип + медиана), сравнить с нашими 0.000 и с опубликованной базой Graf-J 0.156,
сохранить JSON-результаты и контакт-листы ошибок.

**Главный ответ сразу: да, готовая модель лучше наших 0.000 — и намного.**
`PaddlePaddle/PP-OCRv6_medium_rec` (ONNX, Apache-2.0, 19.2 M параметров, **ни одного шага дообучения на наших
данных**) даёт на 29 типах с полосой **acc 0.5517 / CER 0.3078** (медиана по типам 0.75), тогда как наша собственная
CRNN+CTC на невиданных типах — 0.000. Второе по силе — `PaddlePaddle/PP-OCRv5_mobile_rec` и
`PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec` (0.4621 / 0.4621). «Капча-специфичные» модели из волны 1
(Graf-J ×3, jtrecenti/txtcaptcha-crnn) на полном наборе наши нули почти не превосходят — Graf-J даёт
0.0672 на типах с полосой, txtcaptcha 0.0034.

---

## 0. Что было сделано и что не было (честно, до таблиц)

**Сделано (измерено на этой машине, все числа ниже — из `reports/bench_models/*.json`):**

* новый харнесс `bench/bench_models.py` (старые харнессы не тронуты);
* один item set на всех: **46 типов × 20 сэмплов = 920 items**, детерминированная развёртка индексов;
* два дополнительных item set'а для сверки с опубликованными базами: `legacy104` (13 типов × 8 = 104 items, как в
  старом `bench/bench_hf.py`) и `legacy64` (8 типов с полосой × 8 = 64 items, тот набор, на котором в
  `reports/TRAINING_MINIMAL_LATIN.md` пересчитывались базовые 0.156 / 0.125 / 0.047);
* два режима входа, **никогда не смешанные**: `band` (кроп по `roi` из `labels.jsonl`) и `frame` (целый PNG);
* 10 моделей прогнаны полностью (все режимы и все наборы), 1 модель — частично, 1 — упала;
* 4 контакт-листа ошибок (PNG).

**Не сделано (и почему):**

| Что | Статус | Причина |
|---|---|---|
| `microsoft/trocr-base-printed` | **не измерена** | первый прогон упал: `ValueError: You need to specify either 'text' or 'text_target'` (в `transformers 5.19.0` процессор TrOCR требует `text`). Харнесс починен (fallback на `TrOCRImageProcessor`), но повторный прогон был остановлен владельцем (жалоба на 100 % CPU) до записи результата. В JSON лежит **падение**, а не измерение. |
| `PP-OCRv5_server_rec`, `PP-OCRv6_small_rec`, `PP-OCRv6_tiny_rec`, `latin_PP-OCRv5_mobile_rec` (все ONNX) | **не измерены** | прогон запущен и остановлен до конца (см. выше). Ключи в `bench/bench_models.py` есть, веса частично скачаны в `build/hf_cache`. |
| `stepfun-ai/GOT-OCR2_0` | **не измерена** | вес 1.43 ГБ + кастомный код `modeling_GOT.py`; не успел начать до остановки прогонов. Не утверждаю ни загрузку, ни качество. |
| `Gavin-chen/captcha_i2t` | **не измерена** | в репозитории нет `auto_map`/кода модели (`config.json` + `vocab.json` + `.safetensors` + три `.py` с китайскими именами, не зарегистрированные в HF) → `transformers` не может построить архитектуру. Не пробовал. |
| `EasyOCR/en` — режим `frame` | **не измерено** | тот же прогон был убит на середине (JSON сохраняется в конце `run_model`, поэтому в файле остался только `band/legacy64`) | 
| `DunnBC22/trocr-base-printed_captcha_ocr` | не измерена | в репозитории только `pytorch_model.bin` (1.33 ГБ); риск отказа `torch.load` в `transformers 5.x` + время. Не начал. |

---

## 1. Протокол

### 1.1 Item sets

| Набор | Состав | Items | Назначение |
|---|---|---|---|
| `full` | **все 46 типов** × 20 сэмплов (индексы 0, 5, 10, … 95 — равномерная развёртка по `labels.jsonl`) | **920** | основной набор |
| `legacy104` | 13 типов старого бенча × первые 8 | 104 | сверка с `reports/bench_results*.json` |
| `legacy64` | 8 типов старого бенча, у которых есть полоса × первые 8 | 64 | сверка с 0.156 / 0.125 / 0.047 |

46 типов = 34 из `dataset/out` + 12 из `dataset/out_ru`. Из них **29 с полосой** (`roi != null`) и **17 без полосы**.

### 1.2 Вход

* `band` — кроп по `roi` (`x, y, w, h` из `labels.jsonl`, с обрезкой по границам кадра). Для 17 типов без полосы
  на вход идёт целый кадр; такие items помечены `has_roi: false` и вынесены в отдельную группу метрик.
* `frame` — целый PNG, всегда.

### 1.3 Метрики

* **exact match** — нормализованная строка предсказания == нормализованная строка эталона;
* **CER** — Levenshtein / len(эталон);
* нормализация: оставляем **буквы и цифры любого алфавита** (`str.isalnum()`, поэтому кириллица не выкидывается) и
  операторы `+ - * / =`; пробелы и прочее отбрасываем. Старый харнесс использовал `[^A-Za-z0-9+\-*]`, из-за чего
  кириллические сэмплы в старых замерах просто исчезали из подсчёта;
* **эталон**: основной — `text` (строка, которая **нарисована**); вторым числом считается `answer` (ответ игрока).
  Они расходятся ровно в 8 типах из 46 (три `math`/`equation` — в кадре «19 - 11», а ответ «8»; четыре
  русских числительных — в кадре словами). Для OCR-распознавателя честный эталон — `text`, поэтому в таблицах
  ниже он и стоит; в JSON есть и `cer_answer` / `acc_answer`;
* агрегация: **micro** (по items) + **медиана по пер-типу** (не среднее) — отдельно для 29 типов с полосой,
  17 типов без полосы и всех 46.

### 1.4 Среда и воспроизведение

```
python 3.14.5 | torch 2.14.1+cu126 (CUDA, GTX 1080 Ti) | transformers 5.19.0
onnxruntime 1.30.0 (только CPUExecutionProvider — CUDA-EP в этой сборке нет) | numpy 2.5.4 | Pillow 13.0.0
huggingface_hub 1.33.0 | txtcaptcha 0.1.0 (pip) | easyocr 1.7.2 (системный python, CPU)
```

```powershell
# всё, кроме EasyOCR:
.venv-gpu\Scripts\python.exe bench\bench_models.py --models ppocrv6-medium,ppocrv5-mobile,ppocrv5-cyrillic,`
    grafj-crnn,grafj-crnn-base,grafj-convtr,txtcaptcha-crnn,doctr-crnn-ru,anuashok-v3,emelnov-mailru
# EasyOCR — только системным python (там установлен easyocr):
python bench\bench_models.py --models easyocr
# контакт-лист ошибок из уже сохранённого JSON (без повторного инференса):
.venv-gpu\Scripts\python.exe bench\bench_models.py --contact-sheet reports\bench_models\grafj-crnn.json
```

Веса: для каждой модели в JSON записан **commit sha репозитория** (`meta.<mode>/<set>.weights.revision`) и путь к
файлу весов. Кэш HF лежит в `build/hf_cache` (системный `%USERPROFILE%\.cache` для python-процессов доступен
только на чтение).

---

## 2. Главная таблица — вход `band` (полоса), набор `full` (920 items)

| Модель | Репо / ревизия | Лицензия | **acc (29 типов с полосой)** | **CER (29)** | медиана acc по типам | acc (46 типов) | CER (46) | медиана CER | ср. latency, CPU/GPU |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| **PP-OCRv6_medium_rec** (ONNX) | `PaddlePaddle/PP-OCRv6_medium_rec_onnx` @ `50c7eac` | Apache-2.0 | **0.5517** | **0.3078** | **0.7500** | 0.4043 | 0.5662 | 0.2771 | 25.9 мс (CPU) |
| PP-OCRv5_mobile_rec (ONNX) | `PaddlePaddle/PP-OCRv5_mobile_rec_onnx` @ `ed152b8` | Apache-2.0 | 0.4621 | 0.3456 | 0.5500 | 0.3152 | 0.5298 | 0.5479 | 11.1 мс (CPU) |
| cyrillic_PP-OCRv5_mobile_rec (ONNX) | `PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec_onnx` @ `2cef881` | Apache-2.0 | 0.4621 | 0.3522 | 0.6000 | 0.3217 | 0.5275 | 0.5172 | 10.5 мс (CPU) |
| anuashok/ocr-captcha-v3 (TrOCR) | `anuashok/ocr-captcha-v3` @ `51581b6` | Apache-2.0 | 0.2966 | 0.4702 | 0.0000 | 0.2098 | 0.7558 | 0.6832 | 110.9 мс (GPU) |
| docTR-CRNN ru+en (ONNX) | `graycat660/doctr-crnn-vgg16-bn-russian-onnx` @ `a1a5f68` | Apache-2.0 | 0.2776 | 0.5065 | 0.0500 | 0.1804 | 0.8692 | 0.8542 | 6.0 мс (CPU) |
| Graf-J captcha-crnn-base | `Graf-J/captcha-crnn-base` @ `23704b4` | MIT | 0.0828 | 0.6778 | 0.0000 | 0.0533 | 0.8102 | 0.8920 | 3.9 мс (GPU) |
| Graf-J captcha-crnn-finetuned | `Graf-J/captcha-crnn-finetuned` @ `8ca7bfa` | MIT | 0.0672 | 0.6612 | 0.0000 | 0.0446 | 0.8582 | 0.8896 | 3.7 мс (GPU) |
| Graf-J captcha-conv-transformer-finetuned | `Graf-J/captcha-conv-transformer-finetuned` @ `4bc31fa` | MIT | 0.0638 | 0.7013 | 0.0000 | 0.0402 | 0.8315 | 0.9293 | 3.8 мс (GPU) |
| emelnov/ocr-captcha-v4-mailru (TrOCR) | `emelnov/ocr-captcha-v4-mailru` @ `e04c216` | тег не выставлен (база TrOCR — MIT) | 0.0431 | 0.8131 | 0.0000 | 0.0304 | 0.9462 | 0.8688 | 101.2 мс (GPU) |
| jtrecenti/txtcaptcha-crnn | `jtrecenti/txtcaptcha-crnn` @ `cbdc1b9` | MIT | 0.0034 | 0.9054 | 0.0000 | 0.0022 | 1.0455 | 0.9917 | 1.5 мс (GPU) |
| EasyOCR/en | easyocr 1.7.2 + `en` weights | Apache-2.0 | **не измерено** (прогон остановлен; в консоли было `band/full` acc 0.190 / CER 0.641 по 29 типам с полосой) | | | | | | ~90 мс (CPU) |

Для сравнения — **наша собственная модель** на type-held-out: **0.000** (CER 0.95–1.06, `reports/TRAINING_MINIMAL_LATIN.md`),
и 1.000 на тех типах, на которых училась (то есть запоминание, а не обобщение).

### 2.1 То же самое, но вход `frame` (целый кадр) — тот же набор `full`

| Модель | acc (29 типов с полосой) | CER (29) | acc (46) | CER (46) | **во сколько раз упало acc (29)** |
|---|---:|---:|---:|---:|---:|
| PP-OCRv6_medium_rec | 0.0345 | 0.9307 | 0.0783 | 0.9589 | **16×** |
| PP-OCRv5_mobile_rec | 0.0069 | 0.9438 | 0.0283 | 0.9069 | **67×** |
| cyrillic_PP-OCRv5_mobile_rec | 0.0155 | 0.9597 | 0.0402 | 0.9106 | **30×** |
| anuashok/ocr-captcha-v3 | 0.0155 | 1.9867 | 0.0326 | 1.7119 | **19×** |
| docTR-CRNN ru+en | 0.0052 | 1.2619 | 0.0087 | 1.3454 | **53×** |
| Graf-J captcha-crnn-finetuned | 0.0000 | 1.0860 | 0.0022 | 1.1260 | ∞ (было 0.0672) |
| Graf-J captcha-conv-transformer-finetuned | 0.0034 | 1.0200 | 0.0022 | 1.0324 | **19×** |
| emelnov/ocr-captcha-v4-mailru | 0.0000 | 1.2180 | 0.0033 | 1.2015 | ∞ (было 0.0431) |
| jtrecenti/txtcaptcha-crnn | 0.0000 | 0.9855 | 0.0000 | 1.0965 | ∞ (было 0.0034) |

**Это главный структурный вывод теста T1: кроппер важнее модели.** Ни одна из 9 моделей не потеряла при переходе
«полоса → кадр» меньше чем в 16 раз; лучшая модель (PP-OCRv6, 0.5517) на целом кадре — 0.0345, то есть на уровне
шума. Это же объясняет, почему старая цифра `anuashok/ocr-captcha-v3 = 0.077` была получена на кадре: на **собственных
замерах этого отчёта** та же модель на тех же 104 items даёт 0.2788 по полосе против 0.0577 по кадру (в 4.8 раза
больше), а на 64 items — **0.3594 по полосе против 0.0000 по кадру**. То есть «честное сравнение по полосе»,
которого у проекта не было, меняет ануашок с 0.077 на 0.36.

---

## 3. Сверка с опубликованными базами (старые item set'ы)

| Модель | вход | `legacy104` (104) acc / CER | `legacy64` (64) acc / CER | опубликовано ранее | сходится? |
|---|---|---|---|---|---|
| Graf-J captcha-crnn-finetuned | band | 0.0962 / 0.7279 | **0.1562 / 0.5628** | 0.096 (104) и **0.156 / 0.559** (64) | **да**, exact match совпал до предсказания; CER 0.563 против 0.559 (разница CPU/GPU-численности) |
| Graf-J captcha-conv-transformer-finetuned | band | 0.0865 / 0.6880 | 0.1406 / 0.5250 | 0.077 (104) и 0.125 / 0.535 (64) | близко, но не точь-в-точь |
| Graf-J captcha-crnn-base | band | 0.0865 / 0.6808 | 0.1406 / 0.5116 | не измерялся | — |
| anuashok/ocr-captcha-v3 | **frame** | 0.0577 / 0.8154 | 0.0000 / 0.9315 | **0.0769 / 0.7853** (104, кадр) | порядок тот же, 2 items из 104 расходятся (старый харнесс считал на CPU, здесь GPU) |
| anuashok/ocr-captcha-v3 | **band** | 0.2788 / 0.4265 | **0.3594 / 0.2996** | такого замера **не было** | новое: честное сравнение «по полосе», которого у проекта не было |
| EasyOCR/en | band | 0.3281 / 0.3826 | **0.3281 / 0.3826** | 0.1154 (104) и **0.047 / 2.564** (64) | **не сходится** — см. §3.1 |
| PP-OCRv6_medium_rec | band | 0.4423 / 0.3398 | **0.5625 / 0.1978** | не измерялся | — |
| PP-OCRv5_mobile_rec | band | 0.2885 / 0.4546 | 0.4219 / 0.2766 | не измерялся | — |
| cyrillic_PP-OCRv5_mobile_rec | band | 0.3173 / 0.4405 | 0.4688 / 0.2501 | не измерялся | — |
| docTR-CRNN ru+en | band | 0.2404 / 0.6244 | 0.3750 / 0.4294 | не измерялся | — |
| jtrecenti/txtcaptcha-crnn | band | 0.0096 / 0.8830 | 0.0156 / 0.8349 | не измерялся | — |

### 3.1 Почему EasyOCR 0.047 не воспроизводится (0.328 на тех же 64 items)

Сохранённые в `reports/bench_results_others.json` предсказания старого прогона EasyOCR **читают не полосу**:
например, для типа `JSH32/Minecaptcha/map` (у него полоса есть) старое предсказание — `"Type this in chat Tries
Left:"`, тогда как наш прогон по полосе даёт `"PTAY"` — точный ответ. То есть старый прогон кормил EasyOCR **целый
кадр** (значение `roi` появилось в `labels.jsonl` позже — во втором коммите той старой, переписанной истории,
«Regenerate the dataset with the fixed rendering»), а пересчёт в `reports/TRAINING_MINIMAL_LATIN.md` пересчитал именно эти сохранённые
предсказания. **Вывод: цифра 0.047 / CER 2.564 относится к целым кадрам, а не к полосам; сегодня по полосе EasyOCR
даёт 0.328 / 0.383.** Менял я в этом ничего не могу — старый JSON не переписывал.

---

## 4. Пер-тип: где именно выигрывает PP-OCRv6_medium (`band/full`)

Полная таблица по 46 типам лежит в `reports/bench_models/ppocrv6-medium.json` (`modes.band.full.per_type`).
Здесь — группировка.

**acc = 1.000 (8 типов):** `LagBug/XProtect/drop`, `/equation`, `/jump`, `/slot`, `/sneak`, `Z4OLLIEZ4/reCaptcha/captchasx`,
`n1zamu/NCaptcha/anvil`, `CaptchaVerifyZ/map`.

**acc ≥ 0.7:** `haq/mapcha/map` 0.95, `JSH32/Minecaptcha/map` 0.90, `FeelingAlive0/AdvancedCaptcha/math` 0.85,
`irootdev/AnBot/captcha` 0.85, `ringoame196…/ReproductionCAPTCHA/map` 0.85, `LagBug/XProtect/gui` 0.80,
`GalleryCaptcha/ru-web` 0.80, `jSdCool/minecaptcha/text` 0.75, `Yukun99/Captchas/itemslot` 0.70.

**acc = 0.000 (10 типов с полосой):** `Archy-X/Krypton/map`, `FeelingAlive0/AdvancedCaptcha/button`,
`LagBug/XProtect/reverse`, `jSdCool/minecaptcha/image`, `laforetbrut/are-you-sure/code`,
`GalleryCaptcha/ru-numberword`, `GalleryCaptcha/ru-numberword-caption`, `GalleryCaptcha/ru-symbols`, `LimboFilter/map`,
`LimboFilter/symbols`.

### 4.1 Разбор провалов

1. **`Archy-X/Krypton/map` — acc 0.000 при CER 0.250.** Это **ошибка датасета, а не модели**: полоса «на 4 px уже»
   и обрезает пятый символ (это зафиксировано в `reports/TRAINING_MINIMAL_LATIN.md` §7.1). Модель читает
   `6aFi` вместо `6aFij` — то есть **4 из 5 символов верны**, но exact match = 0. Любая модель с exact-match
   метрикой на этом типе получит 0.000; по CER модель там лучшая из всех.
2. **Русские числительные (`ru-numberword`, `ru-numberword-caption`, `LimboFilter/map`) — acc 0.000 у всех моделей,
   включая `cyrillic_PP-OCRv5_mobile_rec` (CER 0.902).** Причина структурная: полоса этих типов — **блок из
   двух-трёх строк** («число прописью, по одному слову в строке»), а любая line-распознаватель читает одну строку.
   Это ровно то, о чём писал отчёт волны 1 C (§1.2: «полоса — не обязательно одна строка»). Вывод: для этой группы
   типов нужен либо тайлинг полосы на строки, либо своя архитектура — **готовой line-модели тут не помчь**.
3. **`ru-symbols` / `LimboFilter/symbols` — acc 0.000, CER 0.87–0.98** у всех: символы не алфавит, модель читает
   мусор (см. контакт-лист: `errors_ppocrv6-medium.png`, последняя строка).
4. **`LagBug/XProtect/reverse` — acc 0.000, CER 0.933.** Известный дефект: в `text` лежит **перевёрнутая** строка
   (отмечено в `reports/TRAINING_MINIMAL_LATIN.md`); сверять с ней бессмысленно.
5. **`jSdCool/minecaptcha/image` — acc 0.000, CER 0.743.** Ответ — 63–70 символов, полоса длинная; PP-OCR
   ресайзит по высоте 48 px и обрезает по ширине 320 px → длинные строки физически не помещаются. Это ограничение
   препроцессинга модели, а не домена.
6. **17 типов без полосы** (`roi = null`) — это сцены (чат, инвентарь, наковальня); acc там 0.0–0.65, а медиана 0.000.
   Ни одна из линейных моделей не умеет сама найти строку ответа — детектора у них нет.

---

## 5. Что это значит для проекта (честно, без приукрашивания)

1. **Готовая модель, лучшая на невиданных типах, есть.** `PP-OCRv6_medium_rec` — Apache-2.0, 19.2 M параметров,
   ONNX, **25.9 мс на картинку на CPU**, и на типах, на которых наша модель даёт 0.000, она даёт **0.5517**
   (медиана по типам 0.75, 8 типов из 29 — 1.000). Никакого дообучения. Это ответ на главный вопрос T1.
2. **«Капча-специфичные» модели HF (Graf-J, txtcaptcha) на нашем домене хуже универсальных.** Все три Graf-J варианта
   дают 0.04–0.08 на типах с полосой (и медиану 0.000 по типам), txtcaptcha — 0.0034. Их собственные карточки
   обещают 96.8 % / 92.98 % seq-acc: это **переобучение под свой синтетический корпус**, ровно тот диагноз, который
   волна 1 уже сформулировала для нашей модели (Graf-J: 96.81 % на одном корпусе и 9.65 % на другом).
3. **Кроппер важнее модели** — в 16–67 раз (§2.1). Значит, первоочередная работа — не «найти ещё одну сеть», а
   довести `roi` (и полосы для 17 типов без них), иначе любой рантайм выдаёт ~0.
4. **Что осталось за рамками готовых line-моделей** — ровно то, что волна 1 уже назвала дефицитом данных:
   многострочные полосы (русские числительные), неалфавитные символы, сцены без детектора, длинные строки,
   обрезанная полоса `Archy-X`. Это четыре конкретных типа-бенефицита, а не «46 типов подряд».
5. **Про собственную модель.** Наша CRNN+CTC (4.62 M, 63 класса) проигрывает готовой PP-OCRv6_medium и по
   type-held-out (0.000 против 0.5517), и по пер-типу. Но из этого **не** следует, что PP-OCR — это и есть наш
   продукт: PP-OCR не решает 4 из 5 сцен (многострочные/символьные полосы, сцены без детектора) и требует
   внешнего детектора для 17 типов. Реалистичная стратегия — **PP-OCR как учитель/база + наш доменный fine-tune
   на разнообразии** (ровно рецепт из `reports/research2/E_training_methods.md` §4), а не «своя сеть с нуля,
   чтобы обойти чужую».
6. **Рантайм.** ONNX-модели PP-OCR идут в ORT без Python — ровно тот путь, который волна 1 описала в
   `F_runtime_llamacpp.md` (§6 «вариант A»). Собственный рантайм ради точности не нужен: точность даёт модель и
   кроп, а не рантайм.

---

## 6. Контакт-листы ошибок

`reports/bench_models/errors_*.png` — сетка 4×N: кроп полосы, золотой `text`, предсказание модели; сортировка
по убыванию CER (худшие сверху).

| Файл | Модель | Что видно |
|---|---|---|
| `errors_txtcaptcha-crnn.png` | jtrecenti/txtcaptcha-crnn (0.0022) | модель выдаёт случайные латинские строки; на кириллице — пусто |
| `errors_grafj-convtr.png` | Graf-J conv-transformer (0.0402) | читает первые символы и обрывается; на сценах — мусор |
| `errors_grafj-crnn.png` | Graf-J CRNN-finetuned (0.0446) | то же; полосы с 1–3 px глифом нечитаемы |
| `errors_ppocrv6-medium.png` | PP-OCRv6_medium (0.4043) | её настоящие ошибки: GUI-сцена `CaptchaGUI/clickblock` (модель читает «XXXXXXXX» вместо цифры), кириллические символы `ru-symbols` / `LimboFilter/symbols`, чат-сцена `LagBug/XProtect/color` (читает инструкцию вместо кода) |

Пересобрать любой лист без повторного инференса:

```powershell
.venv-gpu\Scripts\python.exe bench\bench_models.py --contact-sheet reports\bench_models\ppocrv6-medium.json `
    --contact-mode band --contact-set full
```

---

## 7. Файлы

Создано (мои):

| Файл | Что это |
|---|---|
| `bench/bench_models.py` | новый харнесс: 6 бэкендов (PP-OCR ONNX, Graf-J custom code, TrOCR, txtcaptcha, docTR ONNX, EasyOCR), 3 item set'а, 2 режима входа, агрегация, контакт-листы |
| `reports/research2/T1_models_test.md` | этот отчёт |
| `reports/bench_models/grafj-crnn.json`, `grafj-crnn-base.json`, `grafj-convtr.json`, `ppocrv5-mobile.json`, `ppocrv6-medium.json`, `ppocrv5-cyrillic.json`, `doctr-crnn-ru.json`, `txtcaptcha-crnn.json`, `anuashok-v3.json`, `emelnov-mailru.json`, `trocr-base-printed.json`, `easyocr.json` | результаты: ревизия весов, препроцессинг, окружение, метрики per-type и overall, **все предсказания** |
| `reports/bench_models/errors_txtcaptcha-crnn.png`, `errors_grafj-convtr.png`, `errors_grafj-crnn.png`, `errors_ppocrv6-medium.png` | контакт-листы ошибок |
| `build/hf_cache/` | кэш весов HF (4.07 ГБ; каталог `build/` в `.gitignore`, в коммит не попадает) — потому что `%USERPROFILE%\.cache` для python-процессов доступен только на чтение |

**Не трогал:** `reports/bench_results*.json` (измеренные результаты прошлого раза), `dataset/**`, `train/**`,
`agents/**`, `AGENTS.md`, `HANDOVER.md`, чужие отчёты в `reports/research2/`, чужие файлы в

Побочный эффект: в `.venv-gpu` доустановлен пакет `txtcaptcha 0.1.0` (+ `torchvision 0.29.1+cpu`, `matplotlib`,
`pandas` — его зависимости) ради модели `jtrecenti/txtcaptcha-crnn`.

---

## 8. Что осталось недомерённым (сводка)

1. `microsoft/trocr-base-printed` — первый прогон упал на процессоре (`You need to specify either 'text' or
   'text_target'`), харнесс починен, но повторный прогон остановлен владельцем до записи JSON. В файле — падение.
2. `PP-OCRv5_server_rec`, `PP-OCRv6_small_rec`, `PP-OCRv6_tiny_rec`, `latin_PP-OCRv5_mobile_rec` (ONNX) — прогон
   запущен и остановлен; ключи в харнессе есть, воспроизводится одной командой.
3. `stepfun-ai/GOT-OCR2_0` — не начат (1.43 ГБ + кастомный код).
4. `Gavin-chen/captcha_i2t` — не начат; по составу репозитория загрузить его `transformers` не сможет (нет кода модели).
5. `DunnBC22/trocr-base-printed_captcha_ocr` — не начат (только `pytorch_model.bin`).
6. `EasyOCR/en` в режиме `frame` — прогон остановлен; в JSON остался только `band/legacy64` (плюс напечатанный в
   консоль `band/full`: acc 0.190 / CER 0.641 по 29 типам с полосой).
7. `04RR/Florence-base-Captcha` — не пробовал: в прошлом замере он уже падал
   (`'Florence2LanguageConfig' object has no attribute 'forced_bos_token_id'`), а времени на переустановку не было.

**Что можно добавить следующим шагом (по цене минут, а не часов):** долить четыре PP-OCR-варианта из п. 1–2 и
перезапустить `trocr-base-printed` — всё это ONNX/GPU-истинги, минут 10–15 суммарно.
