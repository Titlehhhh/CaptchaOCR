# Направление C — как внутри устроено распознавание

**Задача направления:** объяснить по шагам, как из картинки произвольного размера получается строка,
и почему каждый шаг именно такой. Образовательный раздел.

**Дата:** 2026-10-22. **Автор:** research-агент (направление C).

**Оговорка о брифе.** Файл `build/scratch/briefs2/C_how_it_works.md` в репозитории отсутствует
(проверено: `glob **/briefs2/**` — пусто), каталог `reports/research2/` до начала работы тоже не
существовал и создан этим отчётом. Работа велась по тексту задания из брифа сессии.

**Метод.** Поиск — через `ddgs` (skill `web-search`), чтение страниц — через `web_fetch`.
Каждое утверждение ниже либо процитировано дословно из источника, либо помечено как вывод
из источника, либо ссылается на файл самого репозитория. Файлы репозитория не менялись,
обучение не запускалось, датасет не трогался; единственное чтение датасета — подсчёт длин
ответов в `labels.jsonl` (раздел 7.3), он воспроизводим и приведён вместе с командой.

---

## Выводы

1. **Конвейер «детектор → кроп → нормализация → распознаватель → декод → пост-обработка» — это не
   один блок, а минимум четыре независимо обучаемые части.** У CaptchaOCR детектор заменён
   заранее известным `roi` из `labels.jsonl`: 29 из 46 типов несут полосу с ответом, а у 17 типов
   `roi` равен `null` и кадр целиком является текстом ([AGENTS.md §3](../AGENTS.md)).
   Для 17 «сценных» типов без детектора задача неразрешима в принципе: модель не может знать,
   какую строку читать.
2. **Сеть почти всегда имеет фиксированную высоту входа и переменную ширину — и это не компромисс,
   а архитектурная необходимость.** CRNN: «Before being fed into the network, all the images need to
   be scaled to the same height» и вход описывается как «W×32 gray-scale image»
   ([CRNN, arXiv:1507.05717](https://arxiv.org/abs/1507.05717)). У CaptchaOCR ровно то же: глиф
   приводится к 32 px, ширина плавает, а `T = W/4` ([`train/captcha_crnn.py:343-356`](../../train/captcha_crnn.py)).
3. **Число шагов CTC — это функция ширины картинки, а не длины ответа.** При пулингах `(2,2),(2,2),(2,1)`
   получается `T = W/4`, и чтобы строка длины `L` вообще была выразима, нужно `T ≥ 2L+1`, то есть
   `W ≥ 4*(2L+1)`. Отсюда рост `min_width` в датасете проекта
   ([`train/captcha_crnn.py:254`](../../train/captcha_crnn.py)).
4. **Главный враг — не модель, а разрешение.** Глиф 8 px физически не разделяет `0/O`, `8/B`,
   `1/l`: это прямо зафиксировано в коде проекта («a 7 px glyph, which is below what a recogniser
   can separate» — [`train/captcha_crnn.py:171-204`](../../train/captcha_crnn.py)). Масштабирование
   вверх без сглаживания (`BILINEAR`) штрихи не восстанавливает, а размывает —
   Pillow оценивает `BILINEAR` в одну звезду за качество даунскейла и `LANCZOS` в четыре
   ([Pillow Concepts](https://pillow.readthedocs.io/en/stable/handbook/concepts.html)).
5. **Для captcha-домены CTC сильнее attention-подходов практически, а не только теоретически:**
   GTC прямо фиксирует, что «CTC decoder has a much shorter inference time, yet a lower accuracy»
   и что модель даёт «6 times shorter inference time than attention-based methods»
   ([GTC, arXiv:2002.01276](https://arxiv.org/abs/2002.01276)); SVTRv2 (ICCV 2025) идёт дальше и
   заявляет, что «CTC Beats Encoder-Decoder Models» по точности и скорости
   ([arXiv:2411.15858](https://arxiv.org/abs/2411.15858)). Для коротких строк (а у 83 % сэмплов
   длина ответа 1–6 символов) этого достаточно.
6. **int8-квантизация CRNN технически проста, но на этой машине бесполезна на GPU.** ONNX Runtime
   прямо предупреждает: для int8 на GPU «You need a device that supports Tensor Core int8
   computation, like T4 or A100. Older hardware will not benefit from quantization»
   ([ORT quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)).
   GTX 1080 Ti — это Pascal (sm_61), Tensor Cores появились только в Volta (sm_70). Значит int8
   имеет смысл только для CPU-инференса.
7. **Метрика «accuracy = exact match» для капчи жёстче, чем кажется, и падает экспоненциально с
   длиной.** CER определён как `(S+D+I)/N` ([metric card evaluate-metric/cer](https://huggingface.co/spaces/evaluate-metric/cer)),
   и вероятность полного совпадения при длине `L` ведёт себя как `(1-CER)^L`. Для типа
   `jSdCool/minecaptcha/image` (ответ 63–70 символов) это означает: нужна per-character точность
   лучше ~99 %, иначе exact match равен нулю при идеальном CER.
8. **Число в `./reports/bench_results*` и `AGENTS.md` — про распознавание, а не про runtime.**
   Направление C показывает, где в конвейере теряются ошибки, и подсказывает, что прежде чем
   строить «свой runtime», надо сначала довести сам датасет и нормализацию: без разнообразия
   стилей (46 стилей × 100 сэмплов) никакая архитектура и никакое квантирование не дадут
   обобщения на невиданные типы.

---

## 0. Карта всего конвейера

Ниже — полный путь от файла PNG до строки ответа. Каждый блок разобран в отдельном разделе,
у каждого — источник.

```
файл PNG (любой размер, любой стиль)
   │
   ├─(1) ДЕТЕКТОР ТЕКСТА  ─────────────────────────── §1.1
   │      DBNet / EAST / CRAFT  →  координаты строки(и)
   │      (у CaptchaOCR: заменён на roi из labels.jsonl — §1.1.4)
   │
   ├─(2) КРОП СТРОКИ  ────────────────────────────── §1.2
   │      вырезать прямоугольник, убрать рамку/фон
   │
   ├─(3) НОРМАЛИЗАЦИЯ  ───────────────────────────── §1.3, §4
   │      grayscale → высота глифа = 32 px → ширина по аспекту
   │      → (x/255 − 0.5)/0.5
   │
   ├─(4) МОДЕЛЬ  ─────────────────────────────────── §1.4, §5
   │      CNN → (B, C, H/8, W/4) → BiLSTM → линейный слой
   │      на выходе (B, T, num_classes),  T = W/4
   │
   ├─(5) ДЕКОД  ──────────────────────────────────── §3
   │      argmax по каждому шагу → склейка повторов → удаление blank
   │      (CTC-декодирование, без выравнивания)
   │
   └─(6) ПОСТ-ОБРАБОТКА  ────────────────────────── §1.6, §7.3
          маска по алфавиту типа, маска по длине типа,
          разворот строки, число-словом → цифры, арифметика
```

---

## 1. От картинки произвольного размера до строки

### 1.1 Детектор текста

Задача детектора — по произвольной картинке дать координаты текстовых областей. В классической
постановке это отдельная нейросеть, обучаемая отдельно от распознавателя.

**EAST** ([arXiv:1704.03155](https://arxiv.org/abs/1704.03155), CVPR 2017) — «прямо предсказывает
слова или текстовые строки произвольной ориентации и четырёхугольной формы на полных
изображениях, устраняя ненужные промежуточные шаги (например, агрегацию кандидатов и
разбиение на слова), одной нейросетью». Заявленная точность: «On the ICDAR 2015 dataset, the
proposed algorithm achieves an F-score of 0.7820 at 13.2fps at 720p resolution».

**DBNet** ([arXiv:1911.08947](https://arxiv.org/abs/1911.08947), AAAI 2020) — сегментационный
детектор, у которого бинаризация встроена в сеть («Differentiable Binarization»):
`B̂ᵢⱼ = 1 / (1 + e^(−k(Pᵢⱼ − Tᵢⱼ)))`, где `P` — карта вероятностей, `T` — предсказанная карта
порогов, `k = 50`. Плюс — «DB works quite well when using a light-weight backbone»: с ResNet-18
на MSRA-TD500 получается **F-measure 82.8 при 62 FPS**. Постпроцессинг при этом — «about 30 % of
the inference time».

Важная для нас деталь — как из карты получаются боксы. Из полного текста DBNet
([ar5iv, 1911.08947](https://ar5iv.labs.arxiv.org/html/1911.08947)): на инференсе
«(1) the probability map/the approximate binary map is firstly binarized with a constant threshold
(0.2), to get the binary map; (2) the connected regions (shrunk text regions) are obtained from
the binary map; (3) the shrunk regions are dilated with an offset D′ (Vatti clipping algorithm)»,
где `D′ = A′ × r′ / L′` и `r′ = 1.5`. То есть на выходе детектора — **прямоугольники/полигоны**,
пригодные для кропа.

**CRAFT** ([arXiv:1904.01941](https://arxiv.org/abs/1904.01941), CVPR 2019) идёт от другой идеи:
детектор ищет не «текст», а «область символа + область сродства между символами»
(character region + affinity), и «The bounding box of texts are obtained by simply finding
minimum bounding rectangles on binary map after thresholding character region and affinity scores»
([репозиторий clovaai/CRAFT-pytorch](https://github.com/clovaai/CRAFT-pytorch)). Для капчи это
интересно тем, что даёт посимвольные координаты — но это уже избыточно, если у вас уже есть
`roi` полосы.

**Современная индустриальная пара** — детектор + распознаватель как два отдельных блока.
PP-OCRv2 формулирует это прямо: «we propose a bag of tricks to train a better text detector and
a better text recognizer» ([arXiv:2109.03144](https://arxiv.org/abs/2109.03144)); тот же двухэтапный
конвейер в PaddleOCR ([README](https://github.com/PaddlePaddle/PaddleOCR), ссылающийся на
PaddleOCR 3.0 Technical Report, arXiv:2507.05595).

#### 1.1.4 Что это значит для CaptchaOCR: детектор заменён на `roi`

В проекте детектора нет вообще. Вместо него используется поле `roi` в `labels.jsonl` —
«the bounding box `[x,y,w,h]` of the text band that carries the answer, or `null` when the whole
frame is the text» ([AGENTS.md §3](../AGENTS.md)). Проверено по данным: у 29 из 46 типов `roi`
заполнен, у 17 — `null`.

Это сильная сторона проекта (детектор не нужно обучать) и одновременно ограничение:
- для 29 типов модель получает ровно ту строку, которую надо прочитать;
- для 17 типов «весь кадр — это текст», и задача «прочитать ответ» **не имеет решения** без
  внешнего детектора или без ручного знания, где строка.

Это ровно то, что описано в [train/README.md](../train/README.md), пункт 2: модель, показанная
целый кадр с заголовком, счётчиками и кодом, «read the wrong line» — и held-out тип получает
accuracy 0.000 при полностью рабочей модели.

### 1.2 Кроп строки

Дальше — операция тривиальная, но именно на ней теряется больше всего. Из полного кадра вырезается
прямоугольник строки. Для CaptchaOCR это буквально `img.crop((x, y, x+w, y+h))` с защитой от
выхода за границы
([`train/captcha_crnn.py:158-169`](../../train/captcha_crnn.py)).

Важный нюанс: полоса `roi` — это **не обязательно одна строка**. Для русского числового семейства
полоса — это блок из двух-трёх строк («The Russian number family spells a whole number out, one
word per row, so its band is a two or three line block whose glyph is only a fifth of the band» —
[`train/captcha_crnn.py:171-186`](../../train/captcha_crnn.py)). Отсюда растёт требование
измерять высоту глифа, а не высоту полосы (§4).

### 1.3 Нормализация

Нормализация состоит минимум из трёх независимых вещей:

1. **Приведение к grayscale.** В проекте — `img.convert("L")`
   ([`train/captcha_crnn.py:158-161`](../../train/captcha_crnn.py)).
2. **Масштабирование по высоте глифа с сохранением аспекта.** Обоснование — в §2.1.
3. **Нормализация значений.** В проекте — `(x/255 − 0.5)/0.5`
   ([`train/captcha_crnn.py:261-263`](../../train/captcha_crnn.py), [train/README.md](../train/README.md)).

Отдельно: выбор фильтра ресайза — это не вкусовое предпочтение, а вопрос сохранения штрихов
(§4.2).

### 1.4 Модель

Модель CaptchaOCR: 4 свёрточных слоя с пулингами `(2,2), (2,2), (2,1)`, затем
`BiLSTM(hidden=256, num_layers=2, bidirectional=True)`, затем линейный слой в 63 класса
(62 символа + blank), итого **4 623 615 параметров**
([`train/captcha_crnn.py:327-373`](../../train/captcha_crnn.py), [train/README.md](../train/README.md)).

Ключевое: три пулинга дают `(B, 256, H/8, W/4)`. Высота 32 → 4 строки признаков; ширина
делится на 4 → **`T = W/4` временных шагов**. Отсюда и формула ограничения (§3).

Архитектурная родня — CRNN Ши, Бая и Яо
([arXiv:1507.05717](https://arxiv.org/abs/1507.05717), TPAMI 2017). Их конфигурация
(таблица 1 статьи) — те же идеи: вход «W×32 gray-scale image», пулинги `1×2, 1×2, 2×2`,
бидирекционный LSTM на 256, CTC-транскрипция. Их ключевое проектное решение — «the 3rd and the
4th max-pooling layers, we adopt 1×2 sized rectangular pooling windows instead of the conventional
squared ones. This tweak yields feature maps with larger width, hence longer feature sequence».
Ровно это делает пулинг `(2,1)` в CaptchaOCR: он не уменьшает ширину, сохраняя число шагов.

### 1.5 Декод

Разбор в §3.

### 1.6 Пост-обработка

Пост-обработка в captcha-домене — не косметика, а носитель половины задачи. В проекте она
перечислена в [train/README.md](../train/README.md) и состоит из:

- **маски по алфавиту типа** (например, `BotFilter` — только цифры, `CaptchaVerifyZ` — `0-9A-Z`);
- **маски по длине** (`CaptchaVerifyZ` — ровно 5, `ru-web` — ровно 5, `BotFilter` — 4 или 5);
- **специфичных преобразований**: разворот строки, превращение русских числительных в цифры,
  вычисление арифметического выражения.

Всё это выводится из `labels.jsonl` — то есть **приор известен заранее и не требует обучения**.
Это аналог того, что в CRNN называется lexicon-based transcription: «each test sample is
associated with a lexicon 𝒟 […] the label sequence is recognized by choosing the sequence in
the lexicon that has highest conditional probability» ([CRNN §2.3.3](https://arxiv.org/abs/1507.05717)).
CRNN решал эту задачу через BK-дерево с ограничением расстояния редактирования δ = 3 и 50-словным
словарём Hunspell: поиск в BK-дереве — `O(log|𝒟|)`.

Разница в подходе: у CRNN лексикон — это словарь естественного языка, у CaptchaOCR — это
перечень разрешённых строк конкретного плагина, то есть лексикон **точнее** и **бесплатен**.

---

## 2. Почему у сети фиксированный вход, а картинки разные

### 2.1 Resize с сохранением аспекта: фиксированная высота + переменная ширина

Это не «компромисс», а прямое следствие того, что CNN требует фиксированного входа.
CRNN формулирует это в двух местах:

> «Since CNN requires the input images to be scaled to a fixed size in order to satisfy with its
> fixed input dimension, it is not appropriate for sequence-like objects due to their large length
> variation. In CRNN, we convey deep features into sequential representations in order to be
> invariant to the length variation of sequence-like objects.»

> «Before being fed into the network, all the images need to be scaled to the same height.»

и в списке преимуществ — «It is **unconstrained to the lengths of sequence-like objects**,
requiring **only height normalization** in both training and testing phases».

Практические числа из статьи: при обучении «all images are scaled to 100×32 in order to accelerate
the training process», при тестировании «Testing images are scaled to have height 32. Widths are
proportionally scaled with heights, but at least 100 pixels».

**В CaptchaOCR ровно та же схема**, но с важным уточнением: масштабируется не полоса, а **глиф**
(§4). Ширина = `round(img.width * scale)`, где `scale = 32 / line_height`
([`train/captcha_crnn.py:250-258`](../../train/captcha_crnn.py)).

### 2.2 Padding (дополнение до кратности)

Чтобы собрать батч, картинки разной ширины надо дополнить. В проекте — дополнение нулями
до максимальной ширины батча:

```python
max_w = max(widths)
images = torch.zeros(len(batch), 1, h, max_w)
for i, b in enumerate(batch):
    images[i, 0, :, : b["width"]] = b["image"]
```
([`train/captcha_crnn.py:274-291`](../../train/captcha_crnn.py)).

Важно: реальная ширина каждого сэмпла передаётся отдельно (`widths`), и именно она, а не
`max_w`, используется при декодировании. Иначе CTC начал бы «читать» и паддинг.

Побочный эффект, о котором стоит знать: padding — это вычисления впустую. Для батча, где один
сэмпл в 10 раз шире остальных, ~90 % вычислений тратятся впустую. Это и мотивирует bucketing (§2.4).

### 2.3 Тайлинг / скользящее окно

Применяется, когда детектора нет и надо прочитать целую страницу/кадр. Опубликованный пример —
TrOCR, дообученный на кусках: «We finetune the pretrained instance-level model TrOCR with randomly
cropped image chunks, and gradually increase the image chunk size […] The best model, which splits
the full image into **15 equally sized chunks**, gives 87.8 F1-score and 4.98 % CER»
([arXiv:2212.05525](https://arxiv.org/abs/2212.05525)). Там же сформулирована сама боль
двухэтапного конвейера: «Most existing OCR models only focus on the cropped text instance images,
which require the bounding box information provided by a text region detection model. Introducing
an additional detector to identify the text instance images in advance adds complexity,
however instance-level OCR models have very low accuracy when processing the whole image».

**Для CaptchaOCR тайлинг — естественный обходной путь для 17 типов без `roi`**: разбить кадр
на полосы, прочитать каждую, выбрать нужную по длине/алфавиту. Именно так устроены
`LimboFilter/framed2x2` и `framed3x3` (кадр 256×256 / 384×384 разрезан на карты 128×128) —
это готовый эталон тайлинга в самом датасете.

### 2.4 Bucketing (группировка по длине)

Идея: не смешивать в батче короткие и длинные сэмплы, а формировать батчи из похожих по ширине.
Документация NVIDIA NeMo формулирует это буквально:

> «You can also use bucketing to ensure similar utterance lengths within batches.»

с параметрами конфигурации `bucketing_strategy: "synced_randomized"` и `bucketing_batch_size`
([NeMo, `docs/source/asr/ssl/configs.rst`](https://raw.githubusercontent.com/NVIDIA/NeMo/main/docs/source/asr/ssl/configs.rst)).
Там же названа и настоящая цель: «we want to avoid the durations varying too significantly within
a single batch».

Для CaptchaOCR bucketing особенно уместен, потому что ширина сэмпла **неоднородна по типам**:
у `jSdCool/minecaptcha/image` ответ из 63–70 символов (и полоса — многострочный блок), а у
`LagBug/XProtect/slot` ответ из одного символа. В одном батче разница ширин — десятки раз.

### 2.5 Динамические батчи и динамические формы

Два разных механизма, их не надо путать:

- **Динамический батч** — размер батча определяется runtime'ом по доступной памяти/времени.
- **Динамическая форма (dynamic shape)** — вход имеет переменный размер, и рантайм заранее
  не знает размеров тензоров.

Второе требует shape inference. ONNX Runtime формулирует это так: «Our quantization tool works
best when the tensor's shape is known. Both symbolic shape inference and ONNX shape inference help
figure out tensor shapes» ([ORT quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)).
Родственная оптимизация — слияние свёртки и BatchNorm в один узел, что заметно упрощает
квантизацию: «a Convolution operator followed by BatchNormalization can be fused into one during
the optimization, which can be quantized very efficiently».

В проекте переменная ширина уже реализована (свой collate + отдельный `widths`), но
**экспортированный чекпойнт как ONNX с динамической осью ширины** — это отдельная задача
(`train/export_hf.py` существует, но, по [AGENTS.md §6](../AGENTS.md), «никогда не выполнялся»).

---

## 3. Длина строки → число шагов CTC

### 3.1 Что такое CTC и временной шаг

CTC (Connectionist Temporal Classification) — функция потерь и представление выхода, предложенные
Грейвсом в 2006 г. ([Wikipedia: Connectionist temporal classification](https://en.wikipedia.org/wiki/Connectionist_temporal_classification),
ссылка на Graves, Fernández, Gomez, Schmidhuber, ICML 2006). Суть: вход — последовательность
наблюдений `X = [x₁, …, x_T]`, выход — последовательность меток `Y = [y₁, …, y_U]`, причём
**выравнивание между ними неизвестно**. CTC «маргинализует» по всем допустимым выравниваниям:

> «The CTC conditional probability **marginalizes** over the set of valid alignments»

([Distill: Sequence Modeling with CTC](https://distill.pub/2017/ctc/); архивная копия —
[web.archive.org/web/20171127180056](https://web.archive.org/web/20171127180056/https://distill.pub/2017/ctc/)).

Чтобы из выходов собрать строку, CTC вводит **blank** (ε) и правило «схлопывания»:

1. выкинуть все blank'ы;
2. склеить одинаковые символы, идущие подряд.

Отсюда же — свойство монотонности: «the allowed alignments between X and Y are **monotonic**»,
выравнивание «many-to-one», и, как следствие, «**the length of Y cannot be greater than the length
of X**» ([Distill](https://distill.pub/2017/ctc/)). Именно blank позволяет выразить два
одинаковых символа подряд: «If Y has two of the same character in a row, a valid alignment must
have a ε between them».

### 3.2 Откуда берётся T

`T` — число временных шагов, то есть число кадров, на которые сеть «нарезает» картинку. У CTC
это длина выравнивания, и она равна длине входа.

В CaptchaOCR `T = W/4` — ширина, делённая на 4 из-за пулингов `(2,2), (2,2), (2,1)`.
Это зафиксировано в докстринге модели: «The pooling is `(2,2), (2,2), (2,1)` […] That gives four
feature rows at a 32-pixel input height and **T = W/4** time steps»
([`train/captcha_crnn.py:329-338`](../../train/captcha_crnn.py)).

### 3.3 Почему нужно T ≥ 2L+1

Выводится из правил выравнивания:

- строка длины `L` требует как минимум `L` шагов (по шагу на символ);
- если два соседних символа в строке одинаковы, между ними обязан быть blank
  (иначе схлопывание склеит их в один) → ещё один шаг;
- худший случай — строка из `L` одинаковых символов: нужно `L` символов + `(L−1)` blank'ов =
  **`2L − 1` шагов**;
- на практике берут `2L + 1`, с одним шагом запаса — так путь CTC не вырождается и у CTC-декодера
  остаётся пространство для пустых шагов по краям.

Это и есть то, что зашито в коде проекта:

```python
needed = 4 * (2 * n_label + 1)
w = max(w, needed)
```
([`train/captcha_crnn.py:253-256`](../../train/captcha_crnn.py)) — `4·` из-за `T = W/4`.

**Честная оговорка.** Канонической фразы «T ≥ 2L+1» в первоисточниках CTC (Graves 2006,
Distill 2017) я **не нашёл** в такой формулировке — там формулируется свойство «длина Y не может
превышать длину X» и требование blank'а между одинаковыми символами. Правило `2L+1` —
это вывод из этих двух свойств плюс практическая конвенция (запас в один шаг), зафиксированная
в коде CaptchaOCR и в [train/README.md](../train/README.md) («The `T >= 2L + 1` constraint has to
be enforced per sample»).

### 3.4 Как из шагов собирается строка

Жадный CTC-декод:

1. `argmax` по классам на каждом шаге → последовательность меток длины `T`;
2. убрать подряд идущие дубликаты;
3. убрать blank.

Именно это делает `greedy_decode` в проекте
([`train/captcha_crnn.py:378-404`](../../train/captcha_crnn.py)) — с одной полезной деталью:
одновременно считается **постериорная вероятность** выбранного класса на каждом шаге, а
уверенность строки — геометрическое среднее этих вероятностей. Это даёт порог, ниже которого
решение считается ненадёжным (в solver'е это основа для retry/фоллбэка).

Жадный декод формально обоснован у CRNN: «Since there exists no tractable algorithm to precisely
find the solution, we use the strategy adopted in [Graves et al.] […] taking the most probable
label πt at each time stamp t, and map the resulted sequence onto l*»
([CRNN §2.3.2](https://arxiv.org/abs/1507.05717)). Там же — цена лексиконного варианта:
«The average testing time is 0.16 s/sample […] The approximate lexicon search is applied to the
50k lexicon of IC03, with the parameter δ set to 3. Testing each sample takes 0.53 s on average»
— то есть лексиконный декод **в 3.3 раза дороже** жадного.

Более дорогие альтернативы: beam search с префиксным CTC-скорингом — именно так работает
joint CTC/attention архитектура, где «During the beam search process, we combine the CTC
predictions, the attention-based decoder predictions and a separately trained LSTM language model»
([Hori et al., arXiv:1706.02737](https://arxiv.org/abs/1706.02737)).

---

## 4. Почему маленький глиф (8–40 px) — это проблема

### 4.1 Что происходит при маленьком глифе

Глиф высотой 8 px — это 8 строк пикселей. Различия между `0` и `O`, `8` и `B`, `1` и `l` — это
единицы пикселей. Проект фиксирует это прямым текстом:

> «A band is not always one line. The Russian number family spells a whole number out, one word per
> row, so its band is a two or three line block whose glyph is only a fifth of the band - scaling
> the band to 32 px would leave a 7 px glyph, which is **below what a recogniser can separate**
> (0 from O, 1 from l, 5 from S, 8 from B).»

([`train/captcha_crnn.py:171-186`](../../train/captcha_crnn.py)).

Конкретика по нашему датасету ([AGENTS.md §6](../AGENTS.md)): у русского числового семейства
x-height **14–15 map px**, у символьного семейства LimboFilter cap height **~55 map px**. То есть
разброс высоты глифа в датасете — примерно 14–55 px, и до нормализации до 32 px часть типов
реально уезжает вниз.

Самое длинное и самое мелкое семейство — `jSdCool/minecaptcha/image`: ответ из 63–70 символов
(это число, записанное русскими словами) — при 100 сэмплах на тип, измеренно по `labels.jsonl`.

### 4.2 Что с этим делают

**(а) Масштабировать глиф, а не кадр.** Отдельно измерять высоту глифа внутри полосы. Метод в
проекте: по строкам картинки считается стандартное отклонение (`a.std(axis=1) > 6.0`), «занятые»
строки группируются в runs, и берётся медиана длины run'а — это и есть высота строки текста.
Метод работает и для тёмного по светлому, и наоборот, «because it looks at the variation and
not at the brightness» ([`train/captcha_crnn.py:171-204`](../../train/captcha_crnn.py)).

**(б) Правильный фильтр ресайза.** Это не вкусовое: при даунскейле (а потом апскейле) нужен
фильтр, усредняющий несколько исходных пикселей, иначе штрих теряется или появляются лесенки.
Pillow публикует таблицу качества ([Pillow Concepts](https://pillow.readthedocs.io/en/stable/handbook/concepts.html)):

| Фильтр | Качество даунскейла | Качество апскейла |
|---|---|---|
| `NEAREST` | — | 5 звёзд |
| `BOX` | 1 звезда | — |
| `BILINEAR` | 1 звезда | 2 звезды |
| `BICUBIC` | 3 звезды | 3 звезды |
| `LANCZOS` | 4 звезды | 4 звезды |

`LANCZOS` описан как «a high-quality Lanczos filter (a truncated sinc) on all pixels that may
contribute to the output value» — то есть именно сглаживание. В проекте для основного ресайза
используется `Image.BILINEAR` ([`train/captcha_crnn.py:258`](../../train/captcha_crnn.py)) —
по таблице это худший по качеству даунскейл из разумных вариантов; `LANCZOS` в проекте не
используется. Это **гипотеза для проверки**, а не установленный факт (см. §«Что это значит»).

**(в) Аугментация под реальные артефакты, а не под искажения.** JPEG (q15–95), WebP (q45–90),
яркость, контраст — «applied to the finished raster, because the generator already distorts the
glyphs» ([`train/README.md](../train/README.md), [`train/captcha_crnn.py:131-156`](../../train/captcha_crnn.py)).
Логика: JPEG-сжатие на низком качестве — это и есть дополнительная потеря разрешения, и модель
должна быть к ней устойчива.

**(г) Геометрический джиттер вместо запоминания пикселей.** Небольшой поворот ±7°, масштаб
0.90–1.10, сдвиг — «the same glyph appears in a slightly different place every epoch, so the only
way to fit the training set is to use the shape of the character»
([`train/captcha_crnn.py:213-235`](../../train/captcha_crnn.py)). Важно: «The canvas keeps its size,
so the CTC width constraint (T >= 2L + 1) is unaffected».

**(д) Исправление геометрии как отдельный модуль.** Для наклонного/перспективного текста —
ESIR, «an end-to-end trainable scene text recognition system that iteratively removes perspective
distortion and text line curvature as driven by better scene text recognition performance»
([arXiv:1812.05824](https://arxiv.org/abs/1812.05824), CVPR 2019).

**(е) TTA (test-time augmentation).** Опубликованный прецедент именно в распознавании текста —
стратегия multi-size resizing в SVTRv2: «a multi-size resizing strategy is proposed to resize text
instances to appropriate predefined sizes, effectively avoiding severe text distortion»
([arXiv:2411.15858](https://arxiv.org/abs/2411.15858)). Логика для капчи: прогнать одну и ту же
полосу в нескольких масштабах (и/или с разными фильтрами ресайза) и проголосовать.

---

## 5. Зачем CTC, attention, гибрид GTC и что такое SVTR

### 5.1 CTC

**Плюсы:** нет выравнивания в разметке (достаточно пары «картинка → строка»), быстрый декод,
стабильное обучение, одна голова.

**Минусы:** CTC «limited to monotonic alignment» ([Wikipedia](https://en.wikipedia.org/wiki/Connectionist_temporal_classification)) —
он не может «заглянуть» направо и не умеет моделировать язык сам по себе. Прямая цитата о
разнице качества: «Compared with attention-based methods, **CTC decoder has a much shorter
inference time, yet a lower accuracy**» ([GTC, arXiv:2002.01276](https://arxiv.org/abs/2002.01276)).

### 5.2 Attention (encoder–decoder)

Attention-модель явно строит распределение внимания по позициям и умеет учитывать контекст на
всю строку сразу. MASTER — характерный представитель: «Attention-based scene text recognizers
have gained huge success, which leverages a more compact intermediate representation to learn 1d-
or 2d-attention by a RNN-based encoder-decoder architecture»
([arXiv:1910.02562](https://arxiv.org/abs/1910.02562), Pattern Recognition 2021). Цена —
итеративный декод (autoregressive), то есть последовательный по времени.

**Для капчи это плохо совпадает с задачей:** у 83 % сэмплов ответ — 1–6 символов, а время
инференса у attention-модели растёт с длиной ответа.

### 5.3 Гибрид CTC/attention

Классический гибрид — joint CTC/attention: CTC-голова даёт быстрый декод, attention-голова — качество,
и они объединяются на beam search ([Hori et al., arXiv:1706.02737](https://arxiv.org/abs/1706.02737),
INTERSPEECH 2017). Для OCR этот класс тоже применяют.

### 5.4 GTC — Guided Training of CTC

Это **не** гибрид CTC/attention: attention-модель используется только на этапе **обучения** как
«учитель», а на инференции остаётся чистый CTC.

> «we propose the guided training of CTC (GTC), where CTC model learns a better alignment and
> feature representations from a more powerful attentional guidance. With the benefit of guided
> training, CTC model achieves robust and accurate prediction for both regular and irregular scene
> text while **maintaining a fast inference speed**. […] our end-to-end model achieves a new
> state-of-the-art for regular and irregular scene text recognition and needs **6 times shorter
> inference time than attention-based methods**.»

([GTC, arXiv:2002.01276](https://arxiv.org/abs/2002.01276), AAAI 2020). Плюс GCN-модуль для
локальных связей между признаками.

Для CaptchaOCR это прямо применимо: у нас уже есть per-type приор (алфавит, длина), но нет
«учителя» — потому что нет второй, более сильной модели. Вариант: взять готовую сильную модель
(например, PP-OCRv5 / SVTRv2) как attention-учитель для нашего CTC — но только если в домене
есть размеченные данные, на которых учитель лучше нашего ученика. На текущих 4600 сэмплах это
маловероятно.

### 5.5 SVTR

SVTR — «Single Visual model for Scene Text recognition»: **полностью отказ от последовательной
модели**. Вместо CNN→RNN→CTC — одна визуальная сеть с иерархическими стадиями, которые
перемешивают, сливают и объединяют «компоненты символов» (patch-wise image tokenization):

> «The method, termed SVTR, firstly decomposes an image text into small patches named character
> components. Afterward, hierarchical stages are recurrently carried out by component-level mixing,
> merging and/or combining. Global and local mixing blocks are devised to perceive the
> inter-character and intra-character patterns […] Thus, characters are recognized by a **simple
> linear prediction**.»

([arXiv:2205.00159](https://arxiv.org/abs/2205.00159), IJCAI 2022). Есть варианты SVTR-L (large) и
SVTR-T (tiny).

Практический смысл: **CTC остаётся**, исчезает рекуррентная часть. Это даёт ускорение без
потери «CTC-совместимости» (тот же логits → CTC-декод).

**SVTRv2** ([arXiv:2411.15858](https://arxiv.org/abs/2411.15858), ICCV 2025) идёт дальше и
формулирует конкуренцию CTC и encoder-decoder открыто — в самом заголовке: «**CTC Beats
Encoder-Decoder Models in Scene Text Recognition**». Там же — feature rearrangement module
«to ensure that visual features accommodate the requirement of CTC, thus alleviating the alignment
puzzle» и семантическое руководство, «can be omitted at the inference stage».

---

## 6. Квантизация int8

### 6.1 Как это делается: PTQ и QAT

**PTQ (post-training quantization)** — квантизация готовой модели. Нужны калибровочные данные:
модель прогоняется на них, собираются статистики активаций, и по ним вычисляются scale и
zero_point. ONNX Runtime: «Static quantization method first runs the model using a set of inputs
called calibration data. During these runs, we compute the quantization parameters for each
activations. These quantization parameters are written as constants to the quantized model and used
for all inputs» ([ORT quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)).
Методы калибровки: MinMax, Entropy, Percentile.

**Динамическая квантизация** — scale/zero_point считаются на лету, для каждого прохода:
«Dynamic quantization calculates the quantization parameters (scale and zero point) for activations
dynamically. These calculations increase the cost of inference, while usually achieve higher
accuracy comparing to static ones».

**QAT (quantization-aware training)** — модель обучается с эмуляцией квантизации. PyTorch
описывает наблюдатели как «observers which are used to collect statistics about the values
observed during calibration (PTQ) or training (QAT)»
([`torch/ao/quantization/observer.py`](https://github.com/pytorch/pytorch/blob/main/torch/ao/quantization/observer.py)).

**Выбор метода.** ONNX Runtime даёт прямое предписание: «In general, it is recommended to use
**dynamic quantization for RNNs** and transformer-based models, and **static quantization for CNN**
models». Если ни один PTQ-метод не даёт нужной точности — «you can try using quantization-aware
training (QAT) to retrain the model» ([ORT quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)).

Для CaptchaOCR (CNN + BiLSTM) это прямо транслируется в план: **статическая (PTQ) квантизация
свёрточной части + динамическая квантизация LSTM**.

### 6.2 Формула и per-channel против per-tensor

Аффинное квантование: `val_fp32 = scale * (val_quantized − zero_point)`.

- **Асимметричное** (zero_point ≠ 0): `scale = (data_range_max − data_range_min) / (quantization_range_max − quantization_range_min)`.
- **Симметричное**: `scale = max(|data_range_max|, |data_range_min|) · 2 / (quantization_range_max − quantization_range_min)`.

`zero_point` важен, потому что «It is important that the floating point zero value be exactly
representable in quantization space. This is because zero padding is used in many CNNs. If it is
not possible to represent 0 uniquely after quantization, it will result in accuracy errors»
([ORT quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)) —
это прямая ссылка на padding из §2.2.

**Per-tensor** — один scale/zero_point на весь тензор. **Per-channel** — свои параметры на каждый
канал. PyTorch описывает это через granularity:

> `PerTensor`: «This granularity type calculates the quantization parameters based off the
> **entire tensor**.»
> `PerAxis`: «calculates **different quantization parameters along a specified axis** of the tensor.
> For example if the input tensor has shape [8, 16] and axis=0, then the quantization parameters are
> calculated for each row of the tensor. Giving a total of 8 quantization parameters.»

([`torch/ao/quantization/observer.py`](https://github.com/pytorch/pytorch/blob/main/torch/ao/quantization/observer.py)).

Практическое правило от ONNX Runtime: «**Per-channel quantization can improve the accuracy for
models whose weight ranges are large.** Try it if the accuracy loss is large. On AVX2 and AVX512
machines, you will generally need to enable reduce_range as well if per-channel is enabled».
И отдельно — про переполнение: «This instruction might suffer from saturation issues: it can
happen that the output does not fit into a 16-bit integer and has to be clamped (saturated) to
fit».

PyTorch даёт ту же логику в коде: `default_per_channel_weight_observer` — «Default per-channel
weight observer, usually used on backends where per-channel weight quantization is supported, such
as `fbgemm`».

**Форматы данных.** U8U8, U8S8, S8U8, S8S8. «S8S8 with QDQ is the default setting and balances
performance and accuracy. It should be the first choice. Only in cases that the accuracy drops
a lot, you can try U8U8». И: «ONNX Runtime quantization on GPU only supports S8S8».

### 6.3 Почему CRNN квантуется хорошо (аргумент, а не измерение)

Структурные причины:

1. **Активации после ReLU неотрицательны и ограничены** — то есть хорошо ложатся в
   асимметричный uint8 диапазон [0, 255], и нет проблемы «длинных хвостов» в обе стороны.
   В PyTorch есть даже готовый «дефолтный» наблюдатель, ограниченный диапазоном:
   `default_observer = MinMaxObserver.with_args(quant_min=0, quant_max=127)`.
2. **Нет attention и softmax** — а именно attention-подобные слои (LayerNorm, softmax) дают
   outlier-каналы, которые ломают per-tensor квантизацию.
3. **Основная работа — свёртки и матричные умножения**, а это ровно те операции, для которых int8
   даёт основной выигрыш.
4. **Мало слоёв** — 4.6 M параметров: квантизованная модель почти не изменится по размеру, выигрыш
   будет в скорости, а не в памяти.

Оговорка: **публикационного head-to-head сравнения «int8 для CRNN vs int8 для трансформерного
OCR-распознавателя» я не нашёл.** Это конструктивный аргумент, а не измеренный результат.

### 6.4 Главное ограничение для этой машины

> «Quantization on GPU — Hardware support is required to achieve better performance with
> quantization on GPUs. **You need a device that supports Tensor Core int8 computation, like T4 or
> A100. Older hardware will not benefit from quantization.**»

([ORT quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)).

GTX 1080 Ti — это Pascal, sm_61; Tensor Cores появились в Volta (sm_70). То есть **int8 на этой
GPU не даст ускорения**. Плюс: «The performance improvement depends on your model and hardware […]
And quantization has overhead (from quantizing and dequantizing), so it is not rare to get worse
performance on old devices». Вывод: int8 для CaptchaOCR — это инструмент для **CPU-рантайма**
(и для публикации на HF в виде int8-чекпойнта), а не для тренировки и не для GPU-инференса.

Ещё одно предупреждение, важное именно для нашего пайплайна: «Quantization is **not a loss-less
transformation**. It may negatively affect a model's accuracy» — и ORT даёт инструменты
квантизационного дебага (сопоставление весов и активаций float32 и int8 моделей).

---

## 7. Как измеряют точность

### 7.1 Exact match

«Accuracy» в распознавании строк = доля сэмплов, где предсказанная строка **в точности** совпала
с истиной. Это либо «sequence accuracy», либо «exact match». Здесь важно не путать её с
per-character accuracy: строка из 5 символов, где 4 верны, даёт exact match = 0.

### 7.2 CER

Character Error Rate — стандарт для OCR/ASR. Определение из metric card:

```
CER = (S + D + I) / N = (S + D + I) / (S + D + C)
```

где `S` — замены, `D` — удаления, `I` — вставки, `C` — верные символы, `N = S + D + C` — длина
эталона ([HuggingFace evaluate-metric/cer](https://huggingface.co/spaces/evaluate-metric/cer)).

Два предупреждения из того же источника, критичные для отчётов проекта:

- «**CER's output is not always a number between 0 and 1**, in particular when there is a high
  number of insertions» — при обильных вставках CER > 1 (пример из metric card: 1.2);
- «CER provides **no details on the nature of translation errors**» — поэтому CER надо
  дополнять разбором по типам, а не только сводным числом.

В проекте `cer()` считается именно так — Levenshtein, делённый на длину эталона
([`train/captcha_crnn.py:407-426`](../../train/captcha_crnn.py)). Соответствует определению выше.

### 7.3 Почему для капч важна длина ответа

**Механика.** Если per-character точка равна `p`, то вероятность полного совпадения для строки
длины `L` — примерно `p^L` (при независимых ошибках). Отсюда:

- `L = 4`, `p = 0.99` → `p^L ≈ 0.96`;
- `L = 4`, `p = 0.95` → `p^L ≈ 0.81`;
- `L = 63`, `p = 0.99` → `p^L ≈ 0.53`;
- `L = 63`, `p = 0.95` → `p^L ≈ 0.04`.

То есть **длинный ответ требует на порядки более высокой per-character точности**, а exact match
на длинных ответах остаётся почти нулевым даже при отличном CER. Это прямое следствие
определения CER (ошибки нормируются на длину эталона) и формулы exact match.

**Данные проекта** (подсчитано по `dataset/out/**/labels.jsonl` и `dataset/out_ru/**/labels.jsonl`,
4600 строк, 46 типов; команда приведена в разделе «Воспроизведение»):

Гистограмма длин ответа:

| длина | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15–28 | 63–70 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| сэмплов | 266 | 167 | 1089 | 783 | 837 | 657 | 65 | 119 | 144 | 54 | 35 | 30 | 117 | 20 | 117 | 100 |

Контроль суммы: 3799 (длины 1–6) + 65 + 119 + 144 + 54 + 35 + 30 + 117 + 20 + 117 + 100 = **4600**.

**83 % ответов (3799 из 4600) имеют длину 1–6 символов.** Длинный хвост — два семейства:

| тип | длина ответа | с `roi` |
|---|---|---|
| `jSdCool/minecaptcha/image` | 63–70 | 100/100 |
| `FeelingAlive0/AdvancedCaptcha/button` | 19–28 | 100/100 |

**Практический вывод из этого:**

1. **Метрику надо выбирать под тип, а не одну на все 46.** Для 40+ типов с ответом 3–6 символов
   exact match и CER ведут себя почти одинаково, и достаточно exact match. Для
   `jSdCool/minecaptcha/image` (63–70) exact match будет ~0 при любом разумном CER — там нужна
   **per-character** метрика и, скорее всего, разбиение на слова/числа.
2. **Для длинных типов нужен другой декод, а не только лучшая модель.** Разделитель «шестьсот
   девяносто» — это словарь, и он известен ([train/README.md](../train/README.md) — приор по
   алфавиту/длине выводится из `labels.jsonl`). Словарное ограничение превращает задачу с 63
   свободных позиций на 3–4 словарных позиции.
3. **Тип `FeelingAlive0/AdvancedCaptcha/button` (19–28) — это, судя по имени и длине, не одна
   строка**, а составной ответ; проверять, что именно нарисовано, надо по `text`, а не по `answer`
   ([AGENTS.md §3](../AGENTS.md) — `text` и `answer` расходятся в 8 из 46 типов).

---

## Что это значит для CaptchaOCR

1. **Сначала закрыть `roi` для 17 типов, а не улучшать модель.** Из 46 типов у 17 `roi` равен
   `null` ([AGENTS.md §3](../AGENTS.md)); для них модель физически не может выбрать нужную строку,
   и measured accuracy 0.000 на held-out типах объясняется этим, а не архитектурой. Готовый
   эталон тайлинга в датасете — `LimboFilter/framed2x2` и `framed3x3` (кадр, разрезанный на карты
   128×128). Плюс DBNet/CRAFT дают готовый путь «детектор → кроп».
2. **Пересмотреть фильтр ресайза: `BILINEAR` → `LANCZOS`.** По таблице Pillow это разница между
   одной звездой и четырьмя за качество даунскейла, а именно даунскейл-апскейл и убивает мелкие
   глифы (14–15 px у русского числового семейства). Это однострочное изменение в
   [`train/captcha_crnn.py:258`](../../train/captcha_crnn.py) с измеримым эффектом на
   `ru-numberword`/`jSdCool/minecaptcha/image`. Проверяемо: переобучить и сравнить CER по типам.
3. **Группировать батчи по ширине (bucketing).** Ширина сэмплов в датасете различается на порядки
   (ответ 1 символ против 70 символов), а `collate` сейчас паддит всё до максимума
   ([`train/captcha_crnn.py:274-291`](../../train/captcha_crnn.py)). NeMo показывает готовый рецепт
   (`bucketing_strategy`, `bucketing_batch_size`). Это чистая экономия GPU-часов, а на 1080 Ti
   с 11.8 ГБ VRAM — заметная.
4. **int8 — только для CPU, и только после того, как закрыт held-out.** ONNX Runtime прямо
   говорит, что на GPU без Tensor Cores int8 не ускоряет; на 1080 Ti (sm_61) это ровно наш
   случай. Практический порядок: сначала добиться обобщения на невиданные типы (это вопрос
   разнообразия данных, §4 и §7.3), потом — экспорт и int8-чекпойнт для публикации на HF и для
   CPU-рантайма. При этом для CRNN (CNN + BiLSTM) схема PTQ-статик для свёрток + динамическая
   для LSTM прямо рекомендована ONNX Runtime.
5. **Разделить метрики по типам.** Для 40+ типов (ответ 3–6) exact match достаточен; для
   `jSdCool/minecaptcha/image` (63–70) и `FeelingAlive0/AdvancedCaptcha/button` (19–28) exact match
   будет ~0 при приемлемом CER — там надо публиковать per-character метрику и/или перейти к
   словарному декоду. Иначе сводное число по 46 типам будет нечитаемым.
6. **Архитектуру не менять.** По опубликованным данным для этого класса задач CTC-декод
   проигрывает attention-подходам по точности, но выигрывает по скорости в 6 раз
   ([GTC](https://arxiv.org/abs/2002.01276)); SVTRv2 показывает, что и точность можно подтянуть,
   оставив CTC ([arXiv:2411.15858](https://arxiv.org/abs/2411.15858)). При 4.6 M параметров и
   коротких ответах менять голову не нужно; узкое место — данные и нормализация, а не
   архитектура.

---

## Чего не нашёл / не проверил

1. **Бриф `build/scratch/briefs2/C_how_it_works.md` отсутствует** в репозитории. Работал по
   тексту задания. Если бриф содержал дополнительные требования, они могли быть пропущены.
2. **Не нашёл первоисточника, который формулирует правило именно как «T ≥ 2L+1».** В [Graves et
   al., ICML 2006](https://en.wikipedia.org/wiki/Connectionist_temporal_classification) и в
   [Distill (2017)](https://distill.pub/2017/ctc/) есть свойства «длина Y не может превышать длину
   X» и «между двумя одинаковыми символами нужен blank», из которых правило выводится; сама
   конвенция «2L+1» зафиксирована в коде проекта и в `train/README.md`. Искал запросами
   «CTC input length must be at least twice the target length», «CTC time steps at least twice the
   number of characters» — через `ddgs` (duckduckgo/bing/brave/mojeek/yahoo/startpage/google);
   поисковая выдача была пустой или отваливалась по таймауту.
3. **Не дочитал раздел про декодирование в Distill** (greedy / beam / prefix beam search): страница
   обрезается примерно на 40 % текста и `web_fetch` возвращает только начало. Пробовал живую
   версию и архивную копию
   ([web.archive.org/web/20171127180056](https://web.archive.org/web/20171127180056/https://distill.pub/2017/ctc/)) —
   обрезается в том же месте. Поэтому про greedy/lexicon декодирование я цитирую по
   [CRNN §2.3](https://arxiv.org/abs/1507.05717) (там есть и формула, и BK-дерево, и цифры по
   времени), а про beam — по [Hori et al.](https://arxiv.org/abs/1706.02737). Исходник статьи Distill
   на GitHub (`distill-public/ctc`) не нашёлся: `/contents/` API вернул 403 (rate limit),
   `article.yaml` по веткам `master` и `main` — 404.
4. **Не нашёл опубликованного head-to-head «int8: CRNN vs трансформерный OCR-распознаватель».**
   Утверждение «CRNN квантуется лучше всего» в §6.3 — это конструктивный аргумент (ReLU-активации,
   отсутствие LayerNorm/softmax, преобладание свёрток), а не измеренный результат. Проверяемо
   локально: экспорт в ONNX + `onnxruntime.quantization.quantize_static` /
   `quantize_dynamic` и сравнение CER.
5. **Не нашёл отдельной статьи именно про TTA (test-time augmentation) в распознавании сцен-текста.**
   Ближайший опубликованный прецедент — multi-size resizing в SVTRv2
   ([arXiv:2411.15858](https://arxiv.org/abs/2411.15858)); сам приём TTA описан в отчёте как
   проектная гипотеза.
6. **Не нашёл авторитетной страницы документации ONNX Runtime про динамические формы**
   (`.../graph-optimizations/dynamic-shape-optimization.html` → 404; общая
   `graph-optimizations.html` — про графовые оптимизации, а не про dynamic shapes). Поэтому в §2.5
   про dynamic shape я опирался на цитату из документации по квантизации («our quantization tool
   works best when the tensor's shape is known») и на собственную реализацию проекта.
7. **Не смог прочитать PDF-источники через `web_fetch`** (например, §16.4 «CTC» из Jurafsky &
   Martin, SLP3) — инструмент возвращает ошибку «unsupported content type application/pdf».
8. **Не проверял PaddleOCR 3.0 Technical Report (arXiv:2507.05595) и PP-OCRv5/PP-OCRv6
   первоисточники** — использовал README PaddleOCR и PP-OCRv2 ([arXiv:2109.03144](https://arxiv.org/abs/2109.03144)).
   Числа «+4.6 % detection / +5.1 % recognition» из README **не переносил** в отчёт как свои
   выводы — они относятся к бенчмаркам PaddleOCR, а не к CaptchaOCR.
9. **Не измерял ничего сама**: ни обучение, ни инференс на GPU, ни экспорт ONNX не запускались.
   Все числа в разделе 7.3 получены чтением `labels.jsonl` (воспроизводимая команда ниже), числа
   про архитектуру — из кода проекта.
10. **Не проверял, насколько `roi` в `labels.jsonl` «честный»** (т.е. всегда ли указывает именно на
    строку с ответом, а не на соседнюю строку) — это работа для `tools/check_band_vs_answer.py`,
    она вне рамок направления C.

---

## Воспроизведение данных раздела 7.3

```powershell
python -c "
import json,os,collections
roots=['dataset/out','dataset/out_ru']
lens=collections.Counter()
for root in roots:
    for dp,dn,fn in os.walk(root):
        if 'labels.jsonl' not in fn: continue
        for line in open(os.path.join(dp,'labels.jsonl'),encoding='utf-8'):
            line=line.strip()
            if line:
                lens[len(json.loads(line).get('answer') or '')]+=1
print(dict(sorted(lens.items())))
print('total rows:', sum(lens.values()))
"
```

Ожидаемый вывод: 4600 строк; гистограмма `{1: 266, 2: 167, 3: 1089, 4: 783, 5: 837, 6: 657,
7: 65, 8: 119, 9: 144, 10: 54, 11: 35, 12: 30, 13: 117, 14: 20, 15: 3, 16: 2, 17: 8, 18: 1,
19: 7, 20: 5, 21: 6, 22: 8, 23: 15, 24: 19, 25: 16, 26: 17, 27: 8, 28: 2, 63: 1, 64: 4,
65: 8, 66: 19, 67: 24, 68: 27, 69: 13, 70: 4}`.

---

## Список источников

**Статьи**

| Работа | Ссылка | Что взято |
|---|---|---|
| Shi, Bai, Yao — CRNN (TPAMI 2017) | [arXiv:1507.05717](https://arxiv.org/abs/1507.05717) · [полный текст](https://ar5iv.labs.arxiv.org/html/1507.05717) | вход W×32, только нормализация высоты, пулинги 1×2, CTC-транскрипция, greedy/lexicon-декод, BK-дерево, времена |
| Zhou et al. — EAST (CVPR 2017) | [arXiv:1704.03155](https://arxiv.org/abs/1704.03155) | детекция строк произвольной ориентации одной сетью, F 0.7820 @ 13.2 fps |
| Liao et al. — DBNet (AAAI 2020) | [arXiv:1911.08947](https://arxiv.org/abs/1911.08947) · [полный текст](https://ar5iv.labs.arxiv.org/html/1911.08947) | дифференцируемая бинаризация, формула, box formation, ResNet-18 F 82.8 @ 62 FPS, 30 % времени на постпроцессинг |
| Baek et al. — CRAFT (CVPR 2019) | [arXiv:1904.01941](https://arxiv.org/abs/1904.01941) · [код](https://github.com/clovaai/CRAFT-pytorch) | character region + affinity, minimum bounding rectangles |
| Hu et al. — GTC (AAAI 2020) | [arXiv:2002.01276](https://arxiv.org/abs/2002.01276) | CTC vs attention: скорость vs точность, guided training, ×6 быстрее |
| Du et al. — SVTR (IJCAI 2022) | [arXiv:2205.00159](https://arxiv.org/abs/2205.00159) | single visual model, character components, линейный предсказатель вместо RNN |
| Du et al. — SVTRv2 (ICCV 2025) | [arXiv:2411.15858](https://arxiv.org/abs/2411.15858) | multi-size resizing, feature rearrangement, «CTC beats encoder-decoder» |
| Xiao et al. — MASTER (Pattern Recognition 2021) | [arXiv:1910.02562](https://arxiv.org/abs/1910.02562) | attention-подход в распознавании текста |
| Hori et al. — Joint CTC/Attention (INTERSPEECH 2017) | [arXiv:1706.02737](https://arxiv.org/abs/1706.02737) | beam search с объединением CTC, attention и LM |
| Li et al. — TrOCR | [arXiv:2109.10282](https://arxiv.org/abs/2109.10282) | трансформерный image→text OCR |
| Zhang et al. — TrOCR для чеков (тайлинг) | [arXiv:2212.05525](https://arxiv.org/abs/2212.05525) | разбиение страницы на 15 кусков, 4.98 % CER; цена двухэтапного конвейера |
| Zhan & Lu — ESIR (CVPR 2019) | [arXiv:1812.05824](https://arxiv.org/abs/1812.05824) | итеративное исправление перспективы/кривизны |
| Du et al. — PP-OCRv2 | [arXiv:2109.03144](https://arxiv.org/abs/2109.03144) | связка «детектор + распознаватель» |
| Graves et al. — CTC (ICML 2006) | [через Wikipedia](https://en.wikipedia.org/wiki/Connectionist_temporal_classification) | оригинальная работа, blank, схлопывание, монотонность |

**Документация**

| Источник | Ссылка | Что взято |
|---|---|---|
| Distill — Sequence Modeling with CTC (2017) | [distill.pub/2017/ctc](https://distill.pub/2017/ctc/) · [архив](https://web.archive.org/web/20171127180056/https://distill.pub/2017/ctc/) | маргинализация по выравниваниям, blank, правила, len(Y) ≤ len(X) |
| ONNX Runtime — Quantize ONNX models | [docs](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html) | формула scale/zero_point, PTQ static/dynamic, рекомендация dynamic для RNN / static для CNN, per-channel, U8S8/S8S8, GPU требует Tensor Cores, «not a loss-less transformation» |
| ONNX Runtime — Graph optimizations | [docs](https://onnxruntime.ai/docs/performance/model-optimizations/graph-optimizations.html) | слияние Conv+BatchNorm, shape inference |
| PyTorch — `torch.ao.quantization.observer` | [исходник](https://github.com/pytorch/pytorch/blob/main/torch/ao/quantization/observer.py) | PTQ/QAT, `PerTensor` vs `PerAxis`, формулы scale/zero_point, `reduce_range`, per-channel weight observer |
| PyTorch — квантизация (документация) | [docs.pytorch.org](https://docs.pytorch.org/docs/stable/quantization.html) | обзор API квантизации |
| Pillow — Concepts (Resampling) | [docs](https://pillow.readthedocs.io/en/stable/handbook/concepts.html) | фильтры ресайза и таблица качества даунскейла/апскейла |
| NVIDIA NeMo — SSL config | [configs.rst](https://raw.githubusercontent.com/NVIDIA/NeMo/main/docs/source/asr/ssl/configs.rst) | bucketing: «ensure similar utterance lengths within batches», `bucketing_strategy`, `bucketing_batch_size` |
| HuggingFace — метрика CER | [metric card](https://huggingface.co/spaces/evaluate-metric/cer) | формула CER, «не всегда 0..1», «не показывает природу ошибок» |
| PaddleOCR | [README](https://github.com/PaddlePaddle/PaddleOCR) | эталонный индустриальный конвейер det + rec |

**Файлы репозитория CaptchaOCR**

| Файл | Что взято |
|---|---|
| [`train/captcha_crnn.py`](../../train/captcha_crnn.py) | архитектура (`T = W/4`), датасет (масштаб по глифу, `4*(2L+1)`, collate с padding), измерение высоты глифа, аугментации, greedy-декод с уверенностью, `levenshtein`/`cer` |
| [`train/README.md`](../train/README.md) | правило `T >= 2L + 1`, плато all-blank, роль `roi`, per-type приоры (алфавит, длина) |
| [`AGENTS.md`](../AGENTS.md) | контракт датасета, `roi`, расхождение `text`/`answer` в 8 из 46 типов, высоты глифов 14–15 и ~55 px, состояние `export_hf.py` |
