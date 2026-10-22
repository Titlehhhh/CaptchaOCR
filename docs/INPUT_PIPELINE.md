# INPUT PIPELINE — как капча с диска доходит до модели

**Дата:** 2026-10-22 · **Для кого:** владелец проекта и новый человек в репозитории.
**Источник истины — код.** Каждая цифра в этом документе либо процитирована как `файл:строка`,
либо получена командой, которую можно повторить (команды в §11).

> **Что это за документ.** В проекте 46 типов капч, и у каждой свой размер картинки, свой цвет,
> своё положение ответа. Модель же принимает **один строгий формат**. Этот документ объясняет
> (простыми словами, на русском) и показывает измерениями, **как именно PNG на диске превращается
> в строку**, и почему решает не модель, а **кроппер** (то, какой прямоугольник вырезать).

---

## 0. Словарик (объясняем каждый термин один раз)

| термин | что это, простыми словами |
|---|---|
| **кадр (frame)** | вся картинка капчи целиком, как её нарисовал плагин. Например, 550×356 пикселей — это окно Minecraft, а ответ занимает в нём крошечный прямоугольник |
| **полоса (band), она же `roi`** | прямоугольник `[x, y, w, h]` внутри кадра, в котором нарисован ответ. Например, в кадре 550×356 полоса может быть 104×30. «ROI» = *region of interest*, «область интереса» |
| **глиф (glyph)** | нарисованный символ (одна буква или цифра). У глифа есть **высота в пикселях** — сколько пикселей по вертикали он занимает. Это не то же самое, что высота полосы: в полосе может быть несколько строк, а глиф в каждой из них — свой |
| **масштабирование (scale)** | во сколько раз увеличили или уменьшили картинку, чтобы привести её к нужному размеру |
| **тензор (tensor)** | массив чисел, который подаётся в нейросеть. Для картинки это «числовая копия пикселей» |
| **канал (channel)** | одна цветовая плоскость картинки: R (красный), G (зелёный), B (синий) или одна плоскость серого |
| **нормализация (normalisation)** | приведение значений пикселей из 0…255 к диапазону около −1…+1, чтобы сеть считала устойчиво |
| **CTC** | способ обучения и декодирования «последователь → последовательность» без выравнивания символов по позициям. На выходе — строка |
| **exact match** | «доля картинок, на которых предсказанная строка совпала с правильной целиком» (не «сколько символов угадано», а «угадано всё») |
| **CER** | character error rate — «доля неверных символов». Мягче, чем exact match: ошибка в одном символе из шести даёт CER ≈ 0.17, а exact match — 0 |

---

## 1. Что такое PNG на диске

Капча в датасете — это **обычный PNG-файл**, один на один образец. Лежит рядом с ним
`labels.jsonl` — файл, где **одна строка JSON на одну картинку** (`train/ppocr_data.py:69-76`
читает его построчно).

### 1.1 Поля `labels.jsonl`

Строка целиком (реальная, из `dataset/out/haq/mapcha/map/labels.jsonl`, первая строка):

```json
{"file":"001.png","plugin":"haq/mapcha","captcha":"map","answer":"zPyf","text":"zPyf",
 "prompt":"Open the map to see the captcha.","roi":[23,68,82,46],"width":128,"height":128,
 "source":"dev.affan.mapcha.player.CaptchaPlayer#generateCaptcha"}
```

| поле | смысл | где читается в коде |
|---|---|---|
| `file` | имя PNG в этом каталоге | `train/ppocr_data.py:99` |
| `plugin`, `captcha` | плагин и тип капчи | `train/finetune_ppocr.py:141-161` (по типу строится разбивка) |
| `answer` | **что игрок вводит в поле ответа** | `train/ppocr_data.py:101` |
| `text` | **что нарисовано на картинке** | `train/ppocr_data.py:91` — это и есть цель распознавания |
| `roi` | полоса `[x, y, w, h]` или `null` | `train/ppocr_data.py:94-96` |
| `width`, `height` | размер кадра **в пикселях** (не размер файла!) | — |
| `source` | откуда взят тип (апстрим / clean-room) | — |

> **`text` ≠ `answer` — это разные вещи.** Пример: тип `LagBug/XProtect/equation` рисует
> `19 - 11`, а игрок вводит `8`. Тип `LagBug/XProtect/reverse` рисует строку **перевёрнутой**.
> Типы с русскими числительными словами рисуют «шестьсот девяносто», а игрок вводит `690`.
> **Модель распознаёт `text`.** Превращение `text → answer` — это отдельный шаг «solver»
> (`docs/pipeline-design.md` §2, слой 3). Измерено: `text != answer` в **9 типах из 46**
> (команда §11.2), в остальных 37 — совпадает.

### 1.2 Размеры: кадр разный, а модель — одна

Измерено по трём реальным файлам (команда §11.1):

| тип | файл на диске | размер кадра | пикселей в кадре | цвет? | полоса `roi` | пикселей в полосе |
|---|---|---|---|---|---|---|
| `out/haq/mapcha/map` | 1 913 Б | **128×128** | 16 384 | цветной (разброс каналов 255) | `[23,68,82,46]` → 82×46 | 3 772 (23 % кадра) |
| `out_ru/GalleryCaptcha/ru-symbols` | 18 458 Б | **250×150** | 37 500 | цветной (разброс 153) | `[37,36,180,88]` → 180×88 | 15 840 (42 % кадра) |
| `out/jSdCool/minecaptcha/text` | 9 483 Б | **550×356** | 195 800 | цветной (разброс 255) | `[223,129,104,30]` → 104×30 | 3 120 (**1.6 %** кадра) |

**Что это значит.** Три типа — три разных задачи для сети:

* `haq/mapcha/map` — маленький квадрат 128×128, ответ занимает примерно четверть;
* `ru-symbols` — средний кадр 250×150, ответ занимает почти половину;
* `minecaptcha/text` — **большой кадр 550×356** (окно Minecraft с рамкой и кнопками), а ответ —
  узкая строчка 104×30 в углу. **98.4 % картинки — мусор для распознавания.**

Именно поэтому «скормить модели весь кадр» — плохая идея: модель обучалась на строчке текста,
а получает окно игры.

**Все картинки в датасете — цветные (RGB)**, не серые. Это важно: для PP-OCRv6 порядок каналов
приходится менять (см. §5.1), для TrOCR — нет.

---

## 2. Весь конвейер — одной картинкой

```
                    ФАЙЛ НА ДИСКЕ  (PNG, 128×128 … 550×356, RGB)
                                 │
                                 ▼
                    [1] PIL открывает файл          ← Image.open(path) + .convert("RGB")
                                 │
                                 ▼
                    [2] КРОП ПО ПОЛОСЕ (roi)        ← img.crop((x, y, x+w, y+h))
                        · если roi есть — режем полосу
                        · если roi == null — кроп по «чернилам» (ink_bbox)
                                 │
                                 ▼
                    [3] МАСШТАБ (что именно 48/32?)
                        · PP-OCR: вся ПОЛОСА становится 48 px
                        · наш CRNN: ГЛИФ становится 32 px (высота строки измеряется)
                        · TrOCR: ничего — 384×384 всегда
                                 │
                                 ▼
                    [4] ПОРЯДОК ЦВЕТОВ
                        · PP-OCR: RGB → BGR
                        · CRNN: → серый (L), 1 канал
                        · TrOCR: RGB как есть
                                 │
                                 ▼
                    [5] НОРМАЛИЗАЦИЯ
                        · (x/255 − 0.5) / 0.5   ← «paddle», дефолт
                        · (x − mean) / std      ← «imagenet», тоже реализовано
                                 │
                                 ▼
                    [6] РАЗМЕР ТЕНЗОРА
                        · PP-OCR: (3, 48, 320) — нули справа до 320
                        · CRNN:   (1, 32, W)   — нули справа до W макс. в батче
                        · TrOCR:  (3, 384, 384)
                                 │
                                 ▼
                    [7] МОДЕЛЬ
                        · PP-OCRv6: CNN → (T, 18 710) логиты
                        · CRNN:     CNN → BiLSTM → (T, 63) логиты, T = W/4
                        · TrOCR:    ViT → декодер, генерирует токены
                                 │
                                 ▼
                    [8] ДЕКОД
                        · CTC (greedy): argmax на каждом шаге → collapse повторов → убрать blank
                        · TrOCR: autoregressive generate + batch_decode
                                 │
                                 ▼
                    [9] СТРОКА ("zPyf")  →  [10] SOLVER (text → answer)
```

---

## 3. Полоса `roi`: главный герой

### 3.1 Что это и зачем

`roi` в `labels.jsonl` — это прямоугольник, в котором плагин нарисовал ответ.
Он вырезается **до** модели, и именно это делает модель работоспособной.

Правило репозитория: **«полоса, которая не помещается в кадр, — это не полоса»** — тогда `roi`
равен `null`, и такой тип вообще не является задачей распознавания
(`train/ppocr_data.py:94-96`, `train/train.py:232-242`).

### 3.2 Измеренный эффект: 16 раз

Источник: **`reports/bench_models/ppocrv6-medium.json`**, ключ
`modes.band.full.metrics.roi_types` и `modes.frame.full.metrics.roi_types`.
Это один и тот же вес `PaddlePaddle/PP-OCRv6_medium_rec_onnx`, один и тот же протокол,
920 картинок, 46 типов, по 20 на тип; меняется **только обрезка**.

| режим входа | типов с полосой | картинок | **exact match (micro)** | CER (micro) | медиана по типам |
|---|---|---|---|---|---|
| **band** (кроп по `roi`) | 29 | 580 | **0.5517** | 0.3078 | 0.750 |
| **frame** (весь кадр) | 29 | 580 | **0.0345** | 0.9307 | 0.000 |
| разница | | | **× 15.99** | | |

> **0.552 по полосе против 0.035 по кадру.** Ровно те числа, что стоит запомнить.

**Скорость при этом одинаковая**: медианная задержка 25.9 мс в режиме `band` и 25.0 мс в режиме
`frame` (тот же JSON, ключи `latency_ms_median`). Кроп не стоит ничего по времени — он даёт
16-кратный выигрыш в точности. **Решает кроппер, а не модель.**

**Важная тонкость.** Для 17 типов **без** полосы результат в обоих режимах одинаковый —
0.1529: в **бенчмарке** кропать нечего, и «band»-режим (`bench/bench_models.py:196-202`)
просто показывает кадр целиком. Выигрыш 0.552 vs 0.035 относится **только к 29 типам с полосой**.

> А вот в **нашем** датасете для `roi is None` кадр кропается **по «чернилам»**
> (`train/ppocr_data.py:378-380`) — то есть файн-тюн PP-OCRv6 и TrOCR видят для этих 17 типов
> **не кадр, а кроп по чернилам**. Проверено на `out_ru/BotFilter/map`: кадр 128×128,
> кроп по чернилам 121×112, и тензор (3, 48, 320) строится именно из кропа.
> Поэтому цифру 0.1529 из бенчмарка **нельзя** переносить на файн-тюн — там другой вход.

### 3.3 По типам: одна и та же модель, одна и та же картинка

Из того же файла (`modes.band.full.per_type` против `modes.frame.full.per_type`, n = 20 на тип):

| тип | band | frame |
|---|---|---|
| `out/haq/mapcha/map` | **0.95** | **0.00** |
| `out/jSdCool/minecaptcha/text` | **0.75** | **0.00** |
| `out_ru/GalleryCaptcha/ru-symbols` | **0.00** | **0.00** |

* `mapcha` и `minecaptcha/text` — латиница: кроп даёт 0.95 и 0.75, кадр — ноль.
* `ru-symbols` — **ноль в обоих режимах**: в словаре PP-OCRv6 **вообще нет кириллицы**
  (`train/ppocr_data.py:184-186`: «the dictionary has no Cyrillic at all»). Эту капчу
  не спасёт никакой кроп — нужен другой алфавит.

---

## 4. Модель не берёт кадр «как есть» — у неё строгий вход

Свёрточная сеть не умеет «картинки разного размера». Фиксирована не картинка, а **высота карты
признаков**; ширина — единственное, что естественно плавает
(`reports/CAPTCHA_SYSTEM_OVERVIEW.md` §2). Дальше каждый конвейер по-своему приводит картинку
к канону.

---

## 5. Три модели: точная цепочка преобразований, как в коде

### 5.1 PP-OCRv6 — `train/ppocr_data.py` + `train/finetune_ppocr.py`

**Какая полоса.** Ровно `roi` из `labels.jsonl`:

```python
# train/ppocr_data.py:375-380
item = self.items[i]
img = self._load(item["path"], item["roi"])
if item.get("roi") is None:
    x, y, w, h = self.ink_bbox(img)          # запасной путь: кроп по «чернилам»
    img = img.crop((x, y, x + w, y + h))
```

```python
# train/ppocr_data.py:278-289  — сам кроп (прямоугольник зажимается в границы кадра)
img = Image.open(path)
if img.mode != "RGB":
    img = img.convert("RGB")
if roi:
    x, y, w, h = roi
    x = max(0, min(x, img.width - 1));  y = max(0, min(y, img.height - 1))
    w = max(1, min(w, img.width - x));  h = max(1, min(h, img.height - y))
    img = img.crop((x, y, x + w, y + h))
```

**Как масштабируется.** Два режима, оба реализованы (`train/ppocr_data.py:350-363`):

```python
def _prepare(self, img):
    if self.glyph_scale == "glyph":
        top, bottom = self._content_rows(img)      # строки полосы, где есть текст
        line = self._line_height(img)              # высота ОДНОЙ строки текста
        crop = img.crop((0, top, img.width, bottom + 1))
        scale = self.glyph_height / max(1, line)    # 48 px на ГЛИФ
    else:
        crop = img
        scale = self.glyph_height / max(1, img.height)   # 48 px на ВСЮ ПОЛОСУ
    w = int(round(crop.width * scale))
    w = max(self.min_width, min(self.max_width, w))      # min_width=16, max_width=320
    out = crop.resize((w, self.glyph_height), Image.BILINEAR)
    return out, w
```

**Дефолт — `glyph_scale="band"`** (`train/finetune_ppocr.py:257`, и в логе прогона:
`normalisation=paddle glyph_scale=band bgr=True`, `train/run_ppocr/big/log.txt`).
То есть **высота 48 — это высота всей полосы, а не глифа**. Режим `"glyph"` (48 px на глиф)
реализован, но дефолтом не является.

**Целевой тензор.** 3 × 48 × 320 (`train/ppocr_data.py:43-44`, `:388-389`):

```python
IMG_HEIGHT = 48
MAX_WIDTH = 320
...
canvas = np.zeros((3, self.glyph_height, MAX_WIDTH), dtype=np.float32)
canvas[:, :, :w] = arr          # нулями справа до 320
```

Это совпадает с `preprocessor_config.json` весов `PaddlePaddle/PP-OCRv6_medium_rec_safetensors`:
`"size": {"height": 48, "width": 320}`, `"pad_size": {"height": 48, "width": 320}`,
`"max_image_width": 3200`.

**Порядок цветов — BGR.** Не RGB: PNG открыт как RGB, потом каналы переворачиваются
(`train/ppocr_data.py:365-373`):

```python
def _normalize(self, img):
    a = np.asarray(img, dtype=np.float32) / 255.0
    if self.bgr:
        a = a[:, :, ::-1]                     # RGB → BGR
    if self.norm == "imagenet":
        a = (a - np.array(IMAGENET_MEAN, dtype=np.float32)) / np.array(IMAGENET_STD, dtype=np.float32)
    else:
        a = (a - 0.5) / 0.5
    return np.ascontiguousarray(a.transpose(2, 0, 1))
```

`bgr=True` — дефолт конструктора (`train/ppocr_data.py:236`). Это **не no-op**: картинки цветные
(разброс каналов до 255), как и сказано в докстринге модуля (`train/ppocr_data.py:21-22`).
Бенчмарк делает ровно то же самое: `arr = arr[:, :, ::-1]` при `img_mode == "BGR"`
(`bench/bench_models.py:339-340`), а `img_mode` и `image_shape` берутся из
`inference.yml` самого веса (`bench/bench_models.py:325-327`).

**Нормализация — два режима, оба реализованы** (`train/ppocr_data.py:38-41`, `:369-372`):

| режим | формула | кто где |
|---|---|---|
| **`paddle`** ← **дефолт** | `(x/255 − 0.5) / 0.5` | `train/finetune_ppocr.py:256` (`--norm`, default `"paddle"`) |
| `imagenet` | `(x/255 − mean) / std`, mean = (0.485, 0.456, 0.406), std = (0.229, 0.224, 0.225) | `train/ppocr_data.py:40-41` |

Дефолт `paddle` подтверждён логом прогона (`train/run_ppocr/big/log.txt`):
`processor: size={'height': 48, 'width': 320} pad_size={'height': 48, 'width': 320}
max_image_width=3200 normalisation=paddle glyph_scale=band bgr=True`.
Слово `imagenet` — это про `PPOCRV6SmallRecImageProcessor` из HF; чья из двух нормализаций
нужна весам, проверялось **измерением**, а не догадкой (см. докстринг `train/ppocr_data.py:34-37`).

**Декод — CTC.** `train/finetune_ppocr.py:112-125`: по каждому временному шагу берётся
`argmax`, подряд идущие одинаковые индексы схлопываются, индекс 0 (blank) выбрасывается.
Словарь — **18 710 классов**, blank = 0, пробел = 18 709
(`train/run_ppocr/big/log.txt`: `dictionary: 18710 classes, blank index=0, space index=18709`).
Лосс при обучении — `torch.nn.CTCLoss(blank=vocab.blank, zero_infinity=True)`
(`train/finetune_ppocr.py:391`), logits берутся в обход публичного `forward`, который
возвращает softmax (`train/finetune_ppocr.py:101-109`).

---

### 5.2 TrOCR — `train/finetune_trocr.py` (появился в дереве 22.10.2026 в 15:15:56)

> **Хронология.** Когда я начал читать дерево (~15:08), файла `train/finetune_trocr.py`
> **не было** (`git log --all -- train/finetune_trocr.py` — пусто, в `train/run/trocr_big/`
> лежало только колесо `sentencepiece`). Он появился в 15:15:56 — его писал **другой агент
> параллельно**. Ниже — уже по **настоящему коду**, прочитанному после его появления,
> и по **измеренному** smoke-прогону (`train/run/trocr_big/smoke/`).

**Модель.** `microsoft/trocr-small-printed` — `VisionEncoderDecoderModel`: кодировщик
DeiT-small ViT (12 слоёв, hidden 384, **image_size 384**), декодер — трансформер на 6 слоёв,
d_model 256, **61 596 672 параметра** (`train/run/trocr_big/log.txt`:
`params: 61596672  encoder=deit hidden=384 layers=12 image_size=384  decoder d_model=256
layers=6 vocab=64044`).

**Какая полоса — та же самая, что у PP-OCRv6.** Код не переписывает кроп, а **переиспользует**
`train/ppocr_data.py` (`train/finetune_trocr.py:264-271`):

```python
img = PPOCRDataset._load(item["path"], item["roi"])
if item.get("roi") is None:
    x, y, w, h = PPOCRDataset.ink_bbox(img)
    img = img.crop((x, y, x + w, y + h))
if self.augment:
    img = self.helpers._augment(img)
```

Докстринг модуля формулирует это прямо: «Preprocessing is deliberately identical to the
PP-OCRv6 run … crop by `roi`, and for the types without a band crop to the ink bounding box;
… Only the pixel geometry differs (384x384 instead of 48x320)» (`train/finetune_trocr.py:29-33`).

**Масштабирование и нормализация — целиком в процессоре модели** (`train/finetune_trocr.py:273`):

```python
pv = self.processor.image_processor(images=img, return_tensors="pt")["pixel_values"][0]
```

`TrOCRProcessor.from_pretrained(args.model)` (`train/finetune_trocr.py:555`), и по логу:

```
processor: DeiTImageProcessor size=SizeDict(height=384, width=384, ...) mean=(0.5, 0.5, 0.5) std=(0.5, 0.5, 0.5)
tokenizer: XLMRobertaTokenizer vocab=64002 pad=1 bos=0 eos=2 decoder_start=2
```

То есть **384×384, RGB, mean = std = 0.5** — ровно то, что мы измерили в §11.1 на реальной
полосе: `pixel_values (1, 3, 384, 384)`, значения −1…+1.

**Декод — НЕ CTC, а генерация токенов** (`train/finetune_trocr.py:326-352`):

```python
g = model.generate(pixel_values=chunk, max_new_tokens=max_new_tokens,
                   do_sample=False, num_beams=1)
...
texts.extend(tokenizer.batch_decode(g, skip_special_tokens=True))
```

Лосс при обучении — **кросс-энтропия декодера**, метки сдвинуты вправо
(`shift_tokens_right`, `train/finetune_trocr.py:313-321`), padding маскируется `-100`
(`train/finetune_trocr.py:286-300`). Докстринг: «This is NOT CTC - there is no blank and no
alignment» (`train/finetune_trocr.py:27`).

**Что «значит 384».** Ничего похожего на «глиф». Картинка **всегда** втискивается в квадрат
384×384, сохраняя пропорции и дополняя пустотой. Для капчи это дорого: полоса `minecaptcha`
104×30 растягивается в 384×384 — **×12.8 по высоте**, а полезные пиксели (буквы) занимают
**1.41 %** холста. Подробности — §6, пример C.

**Что измерено на TrOCR** (`train/run/trocr_big/smoke/`, 1 эпоха, batch 4, по 4 картинки на тип):

| что | значение | источник |
|---|---|---|
| скорость обучения | **7.3 img/s**, шаг 544 мс, эпоха 33.2 с | `train/run/trocr_big/smoke/log.txt`: `epoch 0: loss=8.3721  33.2s  7.3 img/s  step=544ms` |
| нулевой шаг (до обучения) | held-out медиана exact **0.0**, micro 0.0357, CER 1.0 | `train/run/trocr_big/smoke/result.json` → `zero_step` |
| алфавит | 56 076 символов меток, **0 вне латиницы**, round-trip токенизатора — 0 ошибок | `train/run/trocr_big/log.txt`: `charset: 56076 label characters, 0 outside the Latin alphabet (100.00% Latin)` |
| объём | train 6 499 / eval 3 500 / held-out 3 500 | `train/run/trocr_big/log.txt` |

Сравните скорости: **PP-OCRv6 ≈ 96 img/s, наш CRNN ≈ 133 img/s, TrOCR-small ≈ 7.3 img/s** —
TrOCR примерно в **13–18 раз** медленнее на той же карте. Причина — 384×384 против 48×320
(в **9.6 раза** больше значений) **плюс** генерация токенов вместо одного жадного прохода CTC.

> **Важная деталь про алфавит.** TrOCR-скрипт умеет кириллицу (токенизатор
> `XLMRobertaTokenizer`, vocab 64 002), но по умолчанию `--allow_cyrillic` выключен, и
> кириллические типы отбрасываются с причиной «label outside the ASCII alphabet»
> (`train/run/trocr_big/log.txt`, список `DROPPED types`). Плюс сам токенизатор **не умеет**
> то, что умеет CTC: длина строки — это длина последовательности токенов, а не символов,
> поэтому `exact match` здесь считается по декодированной строке, а не по токенам
> (`train/finetune_trocr.py:356-380` — тот же `norm()`, что и у PP-OCRv6).

---

### 5.3 Наш CRNN + CTC — `train/captcha_crnn.py` + `train/train.py`

**Полоса.** Та же `roi`, но **с серым каналом**:

```python
# train/captcha_crnn.py:158-169
img = Image.open(path)
if img.mode != "L":
    img = img.convert("L")                 # ВСЕГДА один серый канал
if roi:
    x, y, w, h = roi
    ... img = img.crop((x, y, x + w, y + h))
return img
```

> **Внимание, тут отличие от PP-OCR:** в `train/captcha_crnn.py` **нет** запасного кропа по
> «чернилам». Если `roi` пуст, `_load` отдаёт **весь кадр**. Типы без полосы поэтому
> исключаются из обучения по умолчанию (`train/train.py:232-242`), а флаг `--allow-no-roi`
> (`train/train.py:110-114`) — это ровно та некорректная постановка, о которой предупреждает
> `train/AGENTS.md` §2.

**`--glyph-height 32` — это 32 px ГЛИФА, а не кадра и не полосы.** Это главная тонкость.

```python
# train/captcha_crnn.py:246-258
# Scale so the GLYPH is `glyph_height` tall, not so the band is. A band can be
# several lines of text (the number family), and the glyph is then only a
# fraction of it. Then widen until the time steps satisfy the CTC constraint
# T >= 2L + 1.
line = self._line_height(img)              # измеряем высоту ОДНОЙ строки текста
scale = self.glyph_height / max(1, line)
w = int(round(img.width * scale))
w = max(self.min_width, w)                 # min_width = 64
needed = 4 * (2 * n_label + 1)              # T = W/4, значит нужно W >= 4*(2L+1)
w = max(w, needed)
w = min(self.max_width, w)                 # max_width = 400
img = img.resize((w, self.glyph_height), Image.BILINEAR)
```

`_line_height` (`train/captcha_crnn.py:171-204`) измеряет **одну строку текста**, а не всю полосу:
строка текста «пестрая» по горизонтали, пустые строки между строками — нет; берётся медиана
длины «занятых» отрезков. Это спасает русские числительные, где полоса — блок из 2–3 строк,
а глиф — пятая часть полосы (`train/captcha_crnn.py:174-186`).

**Формат — 1 × 32 × W, серый, (x/255 − 0.5)/0.5:**

```python
# train/captcha_crnn.py:261-263
a = np.asarray(img, dtype=np.float32) / 255.0
a = (a - 0.5) / 0.5
tensor = torch.from_numpy(a).unsqueeze(0)          # (1, 32, W)
```

Дефолты — `glyph_height=32`, `min_width=64`, `max_width=400`
(`train/captcha_crnn.py:116-117`), флаг `--glyph-height` по умолчанию 32
(`train/train.py:83`).

**Ширина в батче.** `collate` дополняет картинки нулями **до самой широкой в батче**, а не до
фиксированного числа (`train/captcha_crnn.py:274-291`). То есть фиксированной ширины у нашей
модели нет вообще — фиксирована только высота 32.

**Временные шаги.** Пулинги `(2,2), (2,2), (2,1)` дают `H/8` строк признаков и `T = W/4`
(`train/captcha_crnn.py:340-373`, комментарий на `:364` и `:370`):

```python
f = self.cnn(x)                     # (B, 256, H/8, W/4)
f = f.permute(0, 3, 1, 2).reshape(b, w, h * c)   # (B, T=W/4, H/8*256)
```

Отсюда и правило `T ≥ 2L+1`, и `needed = 4*(2L+1)` выше: CTC нужно место на L символов и хотя бы
по одному blank'у между соседними одинаковыми символами.

**Декод — жадный CTC** (`train/captcha_crnn.py:378-404`): argmax на каждом шаге, повторы
схлопываются, blank (индекс 0) выбрасывается; дополнительно считается **уверенность** —
геометрическое среднее постоверior'ов тех кадров, из которых получились символы.
Алфавит — **63 класса** (62 латинских символа + blank, `train/captcha_crnn.py:36`).
Лосс — `torch.nn.CTCLoss(blank=BLANK, zero_infinity=True)` (`train/train.py:313`).

---

## 6. Три разобранных примера — реальные числа из файлов

Все три примера — **первая строка** соответствующего `labels.jsonl`, файл `001.png` существует
на диске. Все числа получены прогоном кода из `train/` (команда §11.1).

### Пример A — `out/haq/mapcha/map` (маленький квадрат)

```
файл      : dataset/out/haq/mapcha/map/001.png   (1 913 Б)
кадр      : 128×128 = 16 384 px, RGB, цветной (разброс каналов 255)
labels    : width=128 height=128 roi=[23,68,82,46] text="zPyf" answer="zPyf"
```

| шаг | результат |
|---|---|
| кроп по `roi` | прямоугольник (23, 68) размером **82×46** = 3 772 px |
| PP-OCR (`band`, дефолт) | scale = 48/46 = 1.043 → ширина **86** → resize (86, 48) → **(3, 48, 320)**, осмысленные пиксели в колонках 0…85, остальные 234 колонки — нули |
| PP-OCR (`glyph`) | строки полосы 0…45, высота строки 46 → тот же результат: **86 px** (полоса одноцветная строка, отличать нечего) |
| наш CRNN | полоса в сером 82×46, высота глифа **46 px** → scale = 32/46 = 0.696 → ширина 57 → **поднята до `min_width`=64** → **(1, 32, 64)**; T = 64/4 = **16** шагов, метка «zPyf» = 4 символа, нужно T ≥ 9 ✓ |
| TrOCR | (1, 3, **384, 384**), полоса растянута ×8.35 по высоте; глиф 46 px → 384 px в холсте, но сама полоса занимает только 215 из 384 строк |
| замер бенчмарка | **band 0.95** / **frame 0.00** (n = 20) |

### Пример B — `out_ru/GalleryCaptcha/ru-symbols` (средний кадр, кириллица)

```
файл      : dataset/out_ru/GalleryCaptcha/ru-symbols/001.png   (18 458 Б)
кадр      : 250×150 = 37 500 px, RGB, цветной (разброс каналов 153)
labels    : width=250 height=150 roi=[37,36,180,88] text="5МП" answer="5МП"
```

| шаг | результат |
|---|---|
| кроп по `roi` | прямоугольник (37, 36) размером **180×88** = 15 840 px (42 % кадра) |
| PP-OCR (`band`) | scale = 48/88 = 0.545 → ширина **98** → resize (98, 48) → **(3, 48, 320)** |
| PP-OCR (`glyph`) | строки 0…87, высота строки 88 → тот же результат: **98 px** |
| наш CRNN | полоса 180×88, высота глифа **88 px** → scale = 32/88 = 0.364 → ширина 65 → **(1, 32, 65)**; T = 16 шагов. **Метка ужалась до 1 символа:** `Charset.encode` молча выбрасывает символы вне алфавита (`train/captcha_crnn.py:60-61`), а кириллицы в латинском наборе 63 нет — из «5МП» осталось «5» |
| TrOCR | (1, 3, **384, 384**), растяжка ×4.36 по высоте |
| замер бенчмарка | **band 0.00** / **frame 0.00** — в словаре PP-OCRv6 **нет кириллицы** (`train/ppocr_data.py:184-186`) |

> Это пример-предупреждение: **кроп не спасёт капчу, написанную не тем алфавитом.**
> Для кириллицы нужен либо отдельный charset (у нас `CYRILLIC = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"`,
> `train/captcha_crnn.py:39` — 33 буквы, **без цифр**), либо другая модель.

### Пример C — `out/jSdCool/minecaptcha/text` (большой кадр, ответ в углу)

```
файл      : dataset/out/jSdCool/minecaptcha/text/001.png   (9 483 Б)
кадр      : 550×356 = 195 800 px, RGB, цветной (разброс каналов 255)
labels    : width=550 height=356 roi=[223,129,104,30] text="BhagzUQJ" answer="BhagzUQJ"
```

| шаг | результат |
|---|---|
| кроп по `roi` | прямоугольник (223, 129) размером **104×30** = 3 120 px — **1.6 % кадра** |
| PP-OCR (`band`, дефолт) | scale = 48/30 = 1.6 → ширина **166** → **(3, 48, 320)** |
| PP-OCR (`glyph`) | строки с текстом 9…28 (глиф 20 px), высота строки **19 px** → scale = 48/19 = 2.526 → ширина **263** → **(3, 48, 320)** — глиф в 1.6 раза крупнее, чем в режиме `band` |
| наш CRNN | полоса 104×30, высота глифа **19 px** → scale = 32/19 = 1.684 → ширина **175** → **(1, 32, 175)**; T = 175/4 = **43** шага, метка «BhagzUQJ» = 8 символов, нужно T ≥ 17 ✓ |
| TrOCR | (1, 3, **384, 384**): полоса растянута ×12.8 по высоте; глиф 20 px → 256 px из 384; **полезные пиксели — 2 080 из 147 456, то есть 1.41 % холста** |
| замер бенчмарка | **band 0.75** / **frame 0.00** (n = 20) |

**Что здесь видно.** «32» в `--glyph-height 32` — это **19 пикселей глифа**, растянутых до 32.
Если бы мы отмасштабировали **полосу** (30 px) до 32, глиф получился бы 20 px — почти вдвое
мельче, чем модель видела при обучении.

А если бы в модель пошёл **весь кадр** 550×356, то при приведении к высоте 48 px масштаб был бы
48/356 = 0.135, и глиф в **19 px превратился бы в 2.6 px**. Читать 2.6 px невозможно — отсюда
0.00 в режиме `frame` (§3.3).

---

## 7. Таблица сравнения трёх моделей

| | **PP-OCRv6** (наш файл-тюн) | **TrOCR-small** (`microsoft/trocr-small-printed`) | **Наш CRNN + CTC** |
|---|---|---|---|
| код | `train/ppocr_data.py`, `train/finetune_ppocr.py` | `train/finetune_trocr.py` (появился 22.10.2026 15:15:56) | `train/captcha_crnn.py`, `train/train.py` |
| модель | `PPOCRV6SmallRecForTextRecognition`, 19 134 326 параметров | `VisionEncoderDecoderModel`, **61 596 672** параметра | `CRNN`, **4 623 615** параметров |
| **ожидаемый вход** | **3 × 48 × 320**, float32 | **3 × 384 × 384**, float32 | **1 × 32 × W**, float32 (W плавает) |
| каналы | 3, **BGR** (`ppocr_data.py:368`) | 3, **RGB** (процессор модели, `DeiTImageProcessor`) | **1, серый** (`captcha_crnn.py:160-161`) |
| **нормализация** | `(x/255 − 0.5)/0.5` — режим **`paddle`**, дефолт; `imagenet` = (0.485,0.456,0.406)/(0.229,0.224,0.225) тоже есть | `(x/255 − 0.5)/0.5` (mean 0.5, std 0.5 из `preprocessor_config.json`) | `(x/255 − 0.5)/0.5` (`captcha_crnn.py:262`) |
| **что значит «32/48/384»** | вся **полоса** становится 48 px (дефолт `glyph_scale="band"`); режим `"glyph"` — 48 px на глиф | ничего: всегда 384×384, пропорции сохраняются, остальное — пустота | **глиф** становится 32 px; высота строки текста измеряется по картинке |
| предел ширины | 320 (плюс `min_width`=16) | 384 | `max_width`=400, `min_width`=64; батч дополняется до самой широкой |
| какой ROI | `roi` из `labels.jsonl`, запасной кроп по чернилам | **тот же самый** (`PPOCRDataset._load`, `finetune_trocr.py:266-269`) | `roi` из `labels.jsonl`; запасного кропа **нет** |
| размер словаря | 18 710 (blank=0, пробел=18 709) | декодер 64 044, токенизатор 64 002 (`XLMRobertaTokenizer`) | 63 (62 латинских + blank) |
| **декод** | **CTC**, жадный (`finetune_ppocr.py:112-125`) | **генерация** токенов, `max_new_tokens=24`, `num_beams=1` (`finetune_trocr.py:341-342`) | **CTC**, жадный + уверенность (`captcha_crnn.py:378-404`) |
| лосс | `CTCLoss(blank=0, zero_infinity=True)` (`finetune_ppocr.py:391`) | кросс-энтропия декодера, метки сдвинуты вправо, padding = −100 (`finetune_trocr.py:286-321`) | `CTCLoss(blank=0, zero_infinity=True)` (`train.py:313`) |
| правило `T ≥ 2L+1` | применяется внутри CTC-потери | **не применяется** (шагов CTC нет) | применяется: `needed = 4*(2L+1)`, `T = W/4` |
| **скорость (измерено)** | обучение **96.2 img/s** (медиана), макс 100.3 — `train/run_ppocr/big/log.txt`; ранний прогон: медиана 115.7, макс 119.2 — `train/run_ppocr/final/log.txt` | обучение **7.3 img/s**, шаг 544 мс — `train/run/trocr_big/smoke/log.txt` | обучение **132.9 img/s** (медиана), макс 256.6 — `train/run/crnn_big/train.log`; другие прогоны: `foldA` 14.6 медиана, `main` 25.7 медиана |
| инференс (измерено) | **25.9 мс** медиана на картинку (CPU, onnxruntime) — `reports/bench_models/ppocrv6-medium.json` | не измерено отдельно | **не измерено** отдельным замером |
| нулевой шаг (до обучения) | held-out медиана exact **0.588** — `train/run_ppocr/big/log.txt` | held-out медиана exact **0.0**, micro 0.0357 — `train/run/trocr_big/smoke/result.json` | — |

*Замеры скорости — на GTX 1080 Ti, batch 32, обучение. Это **не** инференс; инференс PP-OCRv6
посчитан отдельно бенчмарком (25.9 мс/картинку на CPU).*

> **Расхождение с `HANDOVER.md`.** Там написано «CRNN даёт 920 img/s» (строки 79, 218, 331).
> Логи в репозитории дают **133–257 img/s**, и сам `reports/TRAINING_MINIMAL_LATIN.md:144-145`
> это уже признаёт: «The **920 img/s** of `HANDOVER.md` §1.0 is not what this run measures.
> The honest figure … is **~140–280 img/s** end to end (302 img/s for the GPU step alone)».
> Ориентироваться надо на 140–280.

---

## 8. Скорость: где узкое место

| что | измерено | источник |
|---|---|---|
| обучение PP-OCRv6 (3×48×320, batch 32, GPU) | медиана 96.2 img/s, макс 100.3 | `train/run_ppocr/big/log.txt` (строки `epoch N: … img/s`) |
| обучение PP-OCRv6, более ранний прогон | медиана 115.7 img/s, макс 119.2 | `train/run_ppocr/final/log.txt` |
| обучение нашего CRNN (1×32×W, batch 32, GPU) | медиана 132.9 img/s, макс 256.6 | `train/run/crnn_big/train.log` |
| обучение TrOCR-small (3×384×384, batch 4, GPU) | **7.3 img/s**, шаг 544 мс | `train/run/trocr_big/smoke/log.txt` |
| разбор картинок (даталоадер) | 3 475 img/s (6 воркеров), 7 308 img/s (12 воркеров) | `reports/TRAINING_MINIMAL_LATIN.md:137-138` |
| GPU-шаг CRNN, batch 32 | 302 img/s — «the GPU is the limit, not the loader» | `reports/TRAINING_MINIMAL_LATIN.md:139` |
| инференс PP-OCRv6 ONNX (CPU) | 25.9 мс медиана / 26.6 мс среднее | `reports/bench_models/ppocrv6-medium.json` |

Ширина входа влияет на скорость: у PP-OCR ширина **всегда** 320, у нашего CRNN — плавает
(64…400) и в батче дополняется до максимума, поэтому «ширина самого широкого образца в батче
решает» (`reports/TRAINING_MINIMAL_LATIN.md:140`).

**Сводка по скорости (все три — обучение, GPU 1080 Ti):**

| модель | img/s | во сколько раз медленнее PP-OCRv6 |
|---|---|---|
| PP-OCRv6 (3×48×320, batch 32) | **96.2** (медиана) | ×1 |
| наш CRNN (1×32×W, batch 32) | **132.9** (медиана) | быстрее в 1.4 раза |
| TrOCR-small (3×384×384, batch 4) | **7.3** | **×13.2** |

---

## 9. Как это выглядит для владельца (веб-демо `webapp/`)

Запуск: `.venv-gpu\Scripts\python.exe webapp\app.py` → <http://127.0.0.1:8765/>

**Что происходит, когда владелец роняет PNG в окно браузера:**

1. **Картинка из датасета** (то есть её путь известен) — приложение **само находит строку
   `labels.jsonl`** и берёт из неё `roi` (`webapp/app.py:798-806`):
   ```python
   row, abs_path = app.dataset.resolve(path)
   ...
   if row is not None:
       roi = row.get("roi")
   ```
   Дальше кадр кропается по полосе, и в ответе честно стоит `"used_band": true`
   (`webapp/app.py:850`).
2. **Произвольная загруженная картинка** (не из датасета) — `roi` неизвестен, поэтому
   приложение кропает **по «чернилам»**: находит самый частый цвет фона и берёт
   прямоугольник, где фон отличается (`webapp/app.py:217-241`, `:280-284`).
   Это примерный кроппер — он срабатывает не на всех типах.
3. **Предобработка в приложении — копия кода из `train/`**, и для PP-OCRv6 это **проверяется
   при старте**: приложение сравнивает свой тензор с тензором, собранным
   `train/ppocr_data.py`, и печатает вердикт (`webapp/app.py:534-570`):
   `match (the local copy equals train/ppocr_data.py)`.

**Что владельцу стоит заметить:**

* **Демо-подборщик показывает только «честные» типы** — с полосой, не из группы C и с
  **чисто ASCII**-метками (`webapp/app.py:156-173`). Причина — в словаре PP-OCRv6 нет
  кириллицы, поэтому кириллический тип в демо был бы гарантированным провалом.
* **Цифра «0.95» в демо — это заслуга кропа, а не модели.** Та же самая PP-OCRv6 на том же
  `haq/mapcha/map/001.png` даёт **0.95 с полосой и 0.00 без** (§3.3). Если владелец скормит
  модели **скриншот окна Minecraft** целиком (а не картинку из датасета), число резко
  упадёт — и это ожидаемо, а не поломка.
* **Разные типы требуют разных кропперов.** 29 типов решаются одной полосой из `labels.jsonl`.
  Остальные 17 — это отдельная задача: у части весь кадр и есть ответ, у части ответ — не
  текст вовсе (см. разбор в `docs/pipeline-design.md` §8, там это честно названо гипотезой).
  Универсальный кроппер «по чернилам» (`ink_bbox`) — рабочая замена для случая «текст занимает
  весь кадр», но не для сцен с текстом.
* **Что именно показывает демо** — предсказанная строка, уверенность по каждому символу,
  правильный ответ, совпало ли, и **использовалась ли полоса**. Эти четыре поля
  (`text`, `per_char`, `ground_truth`, `used_band`) и есть весь диагноз.

---

## 10. Грабли (gotchas)

1. **Правило полосы.** `roi = null` означает «это не полоса», а не «полоса неизвестна».
   Тип без полосы исключается из обучения по умолчанию (`train/train.py:232-242`).
   Флага `--require-roi` **не существует**; есть `--allow-no-roi` (`train/train.py:110-114`),
   и он **включает** неправильную постановку задачи — учить модель искать строку в картинке.
   **Неверная полоса хуже, чем её отсутствие** (`train/AGENTS.md` §3, правило 2).
2. **`text` ≠ `answer`.** Модель читает **нарисованное**. Измерено: различаются в **9 типах
   из 46** (3 арифметических, 3 русских числительных, 2 «слова в рамках», `LagBug/XProtect/reverse`).
   Для 37 типов `text == answer`. Метрика распознавания считается по `text`
   (`bench/bench_models.py:218-225` — отдельно считается и по `answer`).
3. **Алфавит на тип.** У каждого типа свой: `CaptchaVerifyZ/map` — `0-9A-Z`,
   `haq/mapcha/map` — `0-9A-Za-z`, `ru-symbols` — `0-9` + кириллица, `LagBug/XProtect/slot` —
   `1-8`. Модель PP-OCRv6 вообще **не умеет кириллицу** (`train/ppocr_data.py:184-186`).
   Наш латинский charset — 63 класса, кириллический — **33 буквы без цифр**
   (`train/captcha_crnn.py:39`), поэтому цифры в метках `LimboFilter/symbols` и
   `ru-symbols` **молча выпадают** (`Charset.encode` не предупреждает,
   `train/captcha_crnn.py:60-61`) — это измерено в примере B выше.
4. **Почему 384×384 для TrOCR — расточительство.** Для `minecaptcha/text` глиф в исходной
   полосе — **19–20 px** (измерено: строки с чернилами 9…28, высота строки 19 px). В холсте
   TrOCR он растягивается до 256 px из 384, а **полезные пиксели занимают 1.41 % площади**.
   Площадь входа TrOCR — 3·384·384 = **442 368** значений против 3·48·320 = **46 080** у
   PP-OCRv6 — **в 9.6 раза больше**, при том, что информации в них меньше.
   Плюс TrOCR декодит **генерацией**, а не CTC: это медленнее и не даёт гарантии `T ≥ 2L+1`.
5. **`--glyph-height 32` — это глиф, а не кадр.** Если масштабировать **полосу** до 32,
   глиф в многострочных типах (русские числительные: полоса из 2–3 строк) получится 7 px —
   неразличимы `0/O`, `1/l`, `5/S`, `8/B` (`train/captcha_crnn.py:174-186`).
6. **Цвет ≠ серый.** PNG в датасете цветной. Для PP-OCRv6 нужен **BGR**, для нашего CRNN —
   принудительный серый (`captcha_crnn.py:160-161`), для TrOCR — RGB как есть.
   Смена порядка каналов «молча» портит модель, не вызывая ошибок.
7. **Две нормализации PP-OCRv6.** `paddle` (дефолт) и `imagenet` — обе реализованы
   (`ppocr_data.py:369-372`). Смешивать их нельзя: модель училась с одной.
8. **PP-OCRv6 — словарь на 18 710 классов с индексом 0 = blank.** Пробел — 18 709
   (`train/run_ppocr/big/log.txt`). Наш CRNN — 63 класса, blank = 0
   (`train/captcha_crnn.py:41`). Путать эти два словаря — источник «пустых» предсказаний.
9. **Бенчмарк HF/TrOCR измерялся по кадру, а не по полосе** (`bench/bench_hf.py::predict_trocr`
   вызывает `load_image(p)` без `roi` — см. расхождение № 11 в `agents/INDEX.md`).
   В `bench/bench_models.py` режимы `band` и `frame` честно разделены, поэтому
   цифры §3.2 сравнимы между собой.

---

## 11. Как это проверялось (команды)

### 11.1 Формы, размеры, цвета, алгоритмы — прогон кода из `train/`

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv-gpu\Scripts\python.exe -c "import sys; sys.path.insert(0,'train'); import ppocr_data as d; print([n for n in dir(d) if not n.startswith('_')][:40])"
```

> Вывод (фрагмент): `['IMAGENET_MEAN', 'IMAGENET_STD', 'IMG_HEIGHT', 'Image', 'ImageEnhance',
> 'MAX_WIDTH', 'NORM_MODES', 'PPOCRDataset', 'Vocab', 'build_eval_items', 'build_items', 'cer',
> 'collate', 'find_types', 'io', 'json', 'levenshtein', 'np', 'os', 'random', 'read_labels',
> 'torch', 'type_stats']` — то есть модуль импортируется и содержит те самые константы:
>
> ```
> IMG_HEIGHT 48  MAX_WIDTH 320  NORM_MODES ('paddle', 'imagenet')
> IMAGENET_MEAN (0.485, 0.456, 0.406)   IMAGENET_STD (0.229, 0.224, 0.225)
> ```
>
> А для нашего CRNN:
>
> ```
> CaptchaDataset.__init__(self, items, encode, glyph_height=32, min_width=64, max_width=400, ...)
> CHARSET len 62   CYRILLIC len 33
> ```

Дальше — один скрипт на stdin (ничего не пишет на диск), который для трёх реальных файлов
печатает: размер на диске, `PIL mode`, размер, число пикселей, разброс каналов, строку
`labels.jsonl`, результат `_load` → `_prepare` → `_normalize` → `canvas` для **обоих** режимов
`glyph_scale`, и `CaptchaDataset[0]` для CRNN. Ключевые строки вывода:

```
### out/haq/mapcha/map
  file on disk : dataset/out/haq/mapcha/map/001.png  (1913 bytes)
  PIL mode=RGB size=(128, 128)  pixels=16384
  label row    : width=128 height=128 roi=[23, 68, 82, 46] text='zPyf' answer='zPyf'
  max channel spread (colour?) = 255  -> COLOUR
  band crop rect (x,y,w,h) = (82, 46)  (roi=[23, 68, 82, 46])
   PPOCR glyph_scale=band : resize->(86, 48)  tensor (3, 48, 320)  content width 86 px
   PPOCR glyph_scale=glyph: resize->(86, 48)  tensor (3, 48, 320)  content width 86 px
   CRNN: band grey (82, 46), line_height(glyph)=46px  -> tensor (1, 32, 64)  width=64
   CRNN: T = W/4 = 16 time steps, label len = 4

### out_ru/GalleryCaptcha/ru-symbols
  file on disk : dataset/out_ru/GalleryCaptcha/ru-symbols/001.png  (18458 bytes)
  PIL mode=RGB size=(250, 150)  pixels=37500
  label row    : width=250 height=150 roi=[37, 36, 180, 88] text='5МП' answer='5МП'
  max channel spread (colour?) = 153  -> COLOUR
  band crop rect (x,y,w,h) = (180, 88)
   PPOCR glyph_scale=band : resize->(98, 48)  tensor (3, 48, 320)  content width 98 px
   CRNN: band grey (180, 88), line_height(glyph)=88px  -> tensor (1, 32, 65)  width=65
   CRNN: T = W/4 = 16 time steps, label len = 1        <-- кириллица выпала из метки

### out/jSdCool/minecaptcha/text
  file on disk : dataset/out/jSdCool/minecaptcha/text/001.png  (9483 bytes)
  PIL mode=RGB size=(550, 356)  pixels=195800
  label row    : width=550 height=356 roi=[223, 129, 104, 30] text='BhagzUQJ' answer='BhagzUQJ'
  max channel spread (colour?) = 255  -> COLOUR
  band crop rect (x,y,w,h) = (104, 30)
   PPOCR glyph_scale=band : resize->(166, 48)  tensor (3, 48, 320)  content width 166 px
   PPOCR glyph_scale=glyph: resize->(263, 48)  tensor (3, 48, 320)  content width 263 px
   CRNN: band grey (104, 30), line_height(glyph)=19px  -> tensor (1, 32, 175)  width=175
   CRNN: T = W/4 = 43 time steps, label len = 8
```

Отдельно — процессоры TrOCR (из локального кэша `.hf-cache`, без сети):

```
trocr-base-printed  image processor: ViTImageProcessor size=384×384 mean=(0.5,0.5,0.5) std=(0.5,0.5,0.5) resample=2
trocr-small-printed image processor: DeiTImageProcessor size=384×384 mean=(0.5,0.5,0.5) std=(0.5,0.5,0.5) resample=3
TrOCR base  pixel_values (1, 3, 384, 384)  dtype=torch.float32  min=-1.0000 max=1.0000      (mapcha; у ru-symbols max=0.7255)
-> minecaptcha: полоса 104×30 растянута в 384×384 (×3.69 по ширине, ×12.80 по высоте)
-> глиф 20 px -> 256 px из 384; полезные пиксели 2080 из 147456 = 1.41 %
```

(Оба варианта TrOCR дают одинаковую геометрию 384×384 и одинаковые mean/std 0.5.
Файн-тюн в проекте использует **`trocr-small-printed`** — `DeiTImageProcessor`, вторая строка;
`trocr-base-printed` — `ViTImageProcessor`, первая строка. Разница только в ресемплинге:
BILINEAR против BICUBIC.)

### 11.2 Числа из бенчмарка и из датасета

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv-gpu\Scripts\python.exe -c "import json; d=json.load(open('reports/bench_models/ppocrv6-medium.json',encoding='utf-8')); \
  [print(m, s, k, d['modes'][m][s]['metrics'][k]) for m in ('band','frame') for s in ('full',) \
   for k in ('roi_types','no_roi_types','all_types')]"
```

Вывод (сокращённо):

```
band  full  roi_types     types=29 items= 580 acc_micro=0.5517 cer=0.3078 acc_median=0.7500
band  full  no_roi_types  types=17 items= 340 acc_micro=0.1529 cer=1.0070 acc_median=0.0000
frame full  roi_types     types=29 items= 580 acc_micro=0.0345 cer=0.9307 acc_median=0.0000
frame full  no_roi_types  types=17 items= 340 acc_micro=0.1529 cer=1.0070 acc_median=0.0000
band  full  latency_ms_median = 25.9   frame full latency_ms_median = 25.0
```

Алфавиты и `text != answer` — прогоном `ppocr_data.type_stats` + построчного чтения
`labels.jsonl` по всем 46 типам (команда в §11.1-скрипте):

```
types where text != answer (rows differ):
  out/FeelingAlive0/AdvancedCaptcha/math             500 rows
  out/LagBug/XProtect/equation                       500 rows
  out/LagBug/XProtect/reverse                        500 rows
  out/Mrbysco/Captcha/math                           500 rows
  out_ru/GalleryCaptcha/ru-numberword                500 rows
  out_ru/GalleryCaptcha/ru-numberword-caption        500 rows
  out_ru/LimboFilter/framed2x2                       500 rows
  out_ru/LimboFilter/framed3x3                       500 rows
  out_ru/LimboFilter/map                             500 rows
total types: 46   types with band: 29
```

### 11.3 TrOCR: числа из smoke-прогона и проверка флага `--no-roi-mode`

```powershell
$env:PYTHONIOENCODING="utf-8"
Select-String -Path train\run\trocr_big\smoke\log.txt -Pattern "img/s|epoch |processor:|tokenizer:|charset:"
```

Вывод (ключевые строки):

```
processor: DeiTImageProcessor size=SizeDict(height=384, width=384, ...) mean=(0.5, 0.5, 0.5) std=(0.5, 0.5, 0.5)
tokenizer: XLMRobertaTokenizer vocab=64002 pad=1 bos=0 eos=2 decoder_start=2
charset: 56076 label characters, 0 outside the Latin alphabet (100.00% Latin); tokenizer round-trip failures: 0
epoch 0: loss=8.3721  33.2s  7.3 img/s  step=544ms
epoch 0: held-out median exact=0.0 cer=1.0  micro exact=0.0
done in 1.32 min -> train\run\trocr_big\smoke/result.json
```

А нулевой шаг (до обучения) — из `train/run/trocr_big/smoke/result.json`:
`zero_step.held_out = {types: 7, items: 28, exact_match_median: 0.0, cer_median: 1.0,
exact_match_micro: 0.0357}`.

Проверка, что `--no-roi-mode` **не** переключает кроп (расхождение № 5 в §12.2):

```python
a = P.build_eval_items([("out_ru/BotFilter/map", "dataset/out_ru/BotFilter/map")], no_roi_mode="frame")
b = P.build_eval_items([("out_ru/BotFilter/map", "dataset/out_ru/BotFilter/map")], no_roi_mode="content")
print(a == b)                       # -> True
```

Вывод: `frame items: 500 None`, `content items: 500 None`, `skip items: 0`, `frame == content ? True`.
Плюс тензор: `whole frame: (128, 128)  ink bbox: (4, 3, 121, 112)` →
`tensor (3, 48, 320) built from the INK CROP (121, 112)`.

### 11.4 Проверка самого документа

```powershell
(Get-Item docs\INPUT_PIPELINE.md).Length
```

Вывод: `67048` (байт; ~900 строк).

---

## 12. Что НЕ проверено и известные расхождения

### 12.1 Не проверено

1. **Инференс TrOCR отдельно не замерен** — в логах только скорость обучения (7.3 img/s).
   Бенчмарк TrOCR-бэкенд из `bench/bench_models.py` **падал**
   (`reports/bench_models/trocr-base-printed.json`: `ValueError: You need to specify
   either 'text' or 'text_target'.` — в transformers 5.x процессор TrOCR требует `text`).
2. **Инференс нашего CRNN отдельно не замерен** (в логах — только скорость обучения).
3. **Файл `train/finetune_trocr.py` появился в дереве в 15:15:56 22.10.2026 — во время этой
   сессии, его писал другой агент параллельно.** §5.2 написан по коду, который появился
   **после** начала моей работы; большой прогон `train/run/trocr_big` (`--epochs 4
   --batch-size 8 --max-minutes 18`) в момент написания ещё шёл, поэтому приведены числа
   **smoke-прогона** (1 эпоха, 4 картинки на тип), а не большого.
4. **Полосы не нарисованы глазами** для трёх примеров — числа `roi` взяты из `labels.jsonl`
   и применены кодом, но визуальная проверка (`tools/check_band_vs_answer.py`) не делалась.
5. **Скорость 302 img/s для GPU-шага CRNN** взята из `reports/TRAINING_MINIMAL_LATIN.md:139`,
   а не переизмерена здесь; переизмерены только цифры из логов (`train/run/crnn_big/train.log`
   и др.).
6. **Реальный запуск веб-демо не производился** — код `webapp/app.py` прочитан, но запросы
   к `http://127.0.0.1:8765/` не отправлялись.
7. **Модель TrOCR, обученная на наших типах, ещё не дала приемлемого числа** — smoke-прогон
   дал held-out 0.0 после 1 эпохи на 28 картинках; большой прогон не завершён.

### 12.2 Расхождения, найденные при чтении кода

| # | где | расхождение |
|---|---|---|
| 1 | `docs/GLOSSARY.md` (`text`/`answer`) и `docs/pipeline-design.md` §5 | пишут **8** типов, где `text != answer`; измерено **9** — забыт `LagBug/XProtect/reverse`. Корневой `AGENTS.md` §3 говорит правильно («9 типов из 46») |
| 2 | `train/captcha_crnn.py:158-169` vs `webapp/app.py:297-321` | в трейнере для картинки **без** `roi` подаётся **весь кадр**; в веб-приложении — кроп **по чернинам**. Значит, «приложение — копия препроцессинга» верно **только** для пути PP-OCRv6 (там есть проверка паритета, `webapp/app.py:534-570`); для CRNN такой проверки нет и поведение реально различается |
| 3 | `train/ppocr_data.py:236,361` vs `bench/bench_models.py:337` | у нас есть `min_width=16` (узкая полоса → минимум 16 px), в бенчмарке нижней границы нет (`max(1, …)`). На очень узких полосах входы будут различаться (до 15 px по ширине) |
| 4 | `HANDOVER.md:79,218,331` vs логи | «920 img/s» для CRNN — логи дают 133–257 img/s; расхождение уже отмечено в `reports/TRAINING_MINIMAL_LATIN.md:144-145` |
| 5 | `train/ppocr_data.py:107-145,378-380` | докстринг `build_eval_items` обещает, что `no_roi_mode="frame"` — «the whole frame, downscaled to 48 px tall», а `"content"` — кроп по чернилам. **По коду это не так:** и `"frame"`, и `"content"` дают **одинаковый** список элементов (проверено: `build_eval_items(..., "frame") == build_eval_items(..., "content")` → `True`), и `__getitem__` **всегда** кропает по чернилам при `roi is None`. Флаг различает только `skip` (не оценивать тип) и «не skip». Флаг `--no-roi-mode` в `train/finetune_ppocr.py:254` по умолчанию `frame`, и его название вводит в заблуждение |
| 6 | `train/ppocr_data.py:16-19` (докстринг) | говорит «resize to 48 px tall keeping the aspect ratio, cap the width at 320» — это описание режима `glyph_scale="band"`. Режим `"glyph"` (48 px на глиф) в докстринге не отражён, хотя реализован |
| 7 | `train/ppocr_data.py:22` | «The dataset PNGs are RGB (max channel spread 255)» — для `ru-symbols` измеренный разброс 153, то есть не 255. Формулировка верна по сути, но «255» — это не про все файлы |
| 8 | `train/finetune_trocr.py:497` vs `train/finetune_ppocr.py:254` | у TrOCR-скрипта `--no-roi-mode` принимает только `frame` и `skip`, у PP-OCRv6 — ещё и `content`. Но, как показано в строке 5, само значение `frame` ни на что не влияет — оба скрипта кропают по чернилам. Разница только в том, **какие типы вообще попадают в оценку** |
| 9 | `train/finetune_trocr.py` vs `bench/bench_models.py:409-468` | два разных TrOCR-пути: файн-тюн использует `TrOCRProcessor` (384×384, mean/std 0.5) и декодит `generate(max_new_tokens=24)`, а бенчмарк — `proc(images=…)` и `generate(max_new_tokens=100)`; у бенчмарка на transformers 5.x процессор вообще падал. Числа из двух мест **нельзя смешивать** |

---

*Документ написан 2026-10-22. Все числа получены из файлов репозитория и из прогонов кода,
перечисленных в §11; ни один измеренный результат в `reports/` при написании не редактировался.*
