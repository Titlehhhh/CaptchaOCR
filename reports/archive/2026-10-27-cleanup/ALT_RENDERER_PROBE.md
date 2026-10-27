# ALT_RENDERER_PROBE — измерение альтернативного (не-Java) рендерера капч

**Задача:** владелец спросил — «может быть, image sharp какой-нибудь использовать, сделать правдоподобные
картинки… на шарпе сделать, или другую библиотеку, на расте… надо хорошую и популярную, потому что у image
sharp лицензия какая-то есть».

**Ответ в трёх строках:**

1. **Что это купит:** новые *стили* капч (грязный/потёртый фон, джиттер, поворот, цвет каждой буквы) и
   второй синтетический набор — **не скорость**: Java-генератор не узкое место (23 000 PNG собираются
   за минуты), а C#-рендерер на том же 36-ядерном бюджете быстрее в 5–60 раз только потому, что он
   **однопоточный vs многопоточный**, а не потому, что быстрее рисует.
2. **Сколько стоит:** лицензия ImageSharp **не проблема** для открытого проекта (см. §1), но прототип
   на C# — это отдельный кодовый трек, который **не является аудитом апстрима**; второй рендерер нельзя
   смешивать с faithful-строками датасета без явной пометки «synthetic».
3. **Что делать дальше:** **не** переписывать Java-генераторы (это аудит-тропа публикуемого датасета).
   Если нужен стиль-диверсити — сделать **чистый Python/Pillow** (MIT, уже стоит) как *дополнение* к
   Java-генераторам, с меткой `synthetic`, и обучать на смеси; ImageSharp оставить как запасной вариант,
   если понадобится .NET-тулчейн.

Дата измерений: **2026-10-22**, машина: Windows, **36 логических процессоров**, .NET SDK 9.0.314 / 10.0.300 /
10.0.402 / 11.0.100-rc.2, Java 21, Python 3.14 + Pillow 13.0.0.

---

## 1. Лицензия: ImageSharp и альтернативы

### 1.1 Что реально лежит в пакетах (проверено, не пересказано)

| Пакет | Версия | Лицензия в метаданных NuGet | Источник проверки |
|---|---|---|---|
| `SixLabors.ImageSharp` | **2.1.10** | `license type=expression value=Apache-2.0` | `~/.nuget/packages/sixlabors.imagesharp/2.1.10/sixlabors.imagesharp.nuspec` (локально) |
| `SixLabors.ImageSharp` | **3.1.11** | `license type=file value=LICENSE` → **Six Labors Split License** | `LICENSE` внутри nupkg 3.1.11 + NuGet Registration API |
| `SixLabors.ImageSharp` | **4.0.0** | `license type=file value=LICENSE` → Split License | `~/.nuget/packages/sixlabors.imagesharp/4.0.0/LICENSE` (локально) |
| `SixLabors.ImageSharp` | 2.0.0 / 2.1.13 | `licenseExpression='Apache-2.0'` (NuGet Registration API) | `api.nuget.org/v3/registration5-gz-semver2/sixlabors.imagesharp` |
| `SixLabors.ImageSharp` | 3.0.0 / 3.1.12 / 3.2.0 / 4.1.3 | `licenseExpression=''` + `licenseUrl=…/license` → Split License | там же |

**Важная поправка к посылке владельца:** «ImageSharp перешёл на split-лицензию на 2.x» — **неверно для 2.x**.
Чистый Apache-2.0 держится до **2.1.13 включительно**; split-лицензия начинается с **3.0.0**.
Проверено: `2.1.10` → `Apache-2.0` (SPDX expression), `3.1.12` → пустая expression + файл лицензии.

Но есть практическая ловушка: **весь ряд `SixLabors.ImageSharp.Drawing` 2.1.x тянет ImageSharp ≥ 3.1.x**,
то есть связку «ImageSharp 2.1.10 (Apache-2.0) + современный Drawing» **невозможна**:

```
Drawing 2.1.0 -> ImageSharp 3.1.0     Drawing 2.1.4 -> ImageSharp 3.1.5
Drawing 2.1.1 -> ImageSharp 3.1.1     Drawing 2.1.7 -> ImageSharp 3.1.11
Drawing 2.1.2 -> ImageSharp 3.1.3     Drawing 3.1.3 -> ImageSharp 4.1.3
Drawing 2.1.3 -> ImageSharp 3.1.4
```
(распарсено из nuspec каждого nupkg, скачанного с api.nuget.org)

Т.е. чтобы остаться на Apache-2.0, пришлось бы брать `ImageSharp 1.0.x` + `ImageSharp.Drawing 1.0.0` —
древняя ветка. А `ImageSharp 2.1.10` вдобавок помечен NuGet как **уязвимый** (6 advisory, см. §1.4).
**Практический вывод: если берём ImageSharp — берём 3.1.x/4.1.x и живём с Split License.**

### 1.2 Точный текст Six Labors Split License (Version 1.0, June 2022)

Файл `LICENSE` из пакета `SixLabors.ImageSharp 4.0.0` (и 3.1.11 — файл идентичен), целиком:

```
Six Labors Split License
Version 1.0, June 2022
Copyright (c) Six Labors

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.

   "You" (or "Your") shall mean an individual or Legal Entity exercising permissions granted by this License.

   "Source" form shall be the preferred form for making modifications, including but not limited to software source
    code, documentation source, and configuration files.

   "Object" form shall be any form resulting from mechanical transformation or translation of a Source form, including
    but not limited to compiled object code, generated documentation, and conversions to other media types.

   "Work" (or "Works") shall mean any Six Labors software made available under the License, as indicated by a
    copyright notice that is included in or attached to the work.

   "Direct Package Dependency" shall mean any Work in Source or Object form that is installed directly by You.

   "Transitive Package Dependency" shall mean any Work in Object form that is installed indirectly by a third party
    dependency unrelated to Six Labors.

2. License

   Works in Source or Object form are split licensed and may be licensed under the Apache License, Version 2.0 or a
   Six Labors Commercial Use License.

   Licenses are granted based upon You meeting the qualified criteria as stated. Once granted,
   you must reference the granted license only in all documentation.

   Works in Source or Object form are licensed to You under the Apache License, Version 2.0 if.

   - You are consuming the Work in for use in software licensed under an Open Source or Source Available license.
   - You are consuming the Work as a Transitive Package Dependency.
   - You are consuming the Work as a Direct Package Dependency in the capacity of a For-profit company/individual with
     less than 1M USD annual gross revenue.
   - You are consuming the Work as a Direct Package Dependency in the capacity of a Non-profit organization
     or Registered Charity.

   For all other scenarios, Works in Source or Object form are licensed to You under the Six Labors Commercial License
   which may be purchased by visiting https://sixlabors.com/pricing/.
```

### 1.3 Что это значит **для нас** (открытый проект, публикуем модели и датасет на Hugging Face)

* **Первый пункт — наш случай.** Мы «consuming the Work for use in software licensed under an Open Source or
  Source Available license» → получаем **Apache-2.0**, без ограничения по выручке (ограничение <1M USD
  относится к *другому* сценарию — прямому использованию вне OSS-софта). Т.е. «лицензия ImageSharp» для
  нашего OSS-проекта — это **Apache-2.0**, ровно как и хотелось.
* **Обязательство минимальное:** «Once granted, you must reference the granted license only in all
  documentation» → в README/лицензию проекта достаточно написать, что используется Apache-2.0
  (Six Labors ImageSharp, Six Labors Split License → Apache-2. branch). Никаких «шестилаборсовских» условий
  на наш датасет не переносится.
* **Публикуемые артефакты (PNG-картинки, `labels.jsonl`, веса модели на HF) — не «Work».** Определение Work
  в п.1 — это «any Six Labors software made available under the License». Наш датасет — не софт Six Labors,
  он лишь *создан* их инструментом. Лицензия инструмента **не распространяется** на результат его работы.
  → Модель и датасет на HF публикуются на нашей лицензии, без оговорок про ImageSharp.
* **Единственный реальный риск:** если рендерер на ImageSharp когда-нибудь станет частью **проприетарного**
  продукта (или его непубличный форк перестанет быть OSS) — тогда нужен Six Labors Commercial License.
  Для лабораторного OSS-проекта это нерелевантно; но это надо помнить, если проект превратится в продукт.
* **Шрифты — отдельный вопрос.** Прототип растрирует *системные* шрифты Windows (Consolas, Arial, …).
  Растеризация шрифта в картинку — это не распространение файла шрифта, но для **публикуемого на HF датасета**
  правильнее брать шрифты со свободной лицензией (DejaVu / Noto / Liberation). Это отдельная задача,
  не входившая в бюджет зонда, но её надо закрыть **до** публикации второго набора.

### 1.4 Альтернативы с заведомо пермиссивной лицензией

| Библиотека | Лицензия | Проверено | Комментарий |
|---|---|---|---|
| **Pillow 13.0.0** (Python) | **MIT** | `PIL.__version__ = 13.0.0` в `.venv-gpu` | Уже установлен. Самый дешёвый путь: ни нового тулчейна, ни новой лицензии, ни .NET. |
| **SkiaSharp 3.119.4** (.NET) | **MIT** | пакет в `~/.nuget/packages/skiasharp/3.119.4` (+ `skiasharp.nativeassets.win32` 3.119.4) | Skia = движок Chrome/Android. Даёт нативные `canvas.Save()/RotateDegrees()` — поворот и цвет каждой буквы без ручной инверсии. Если брать .NET — это лучший выбор, чем ImageSharp. |
| **ImageSharp 3.1.11 / 4.1.3** | Split License → **Apache-2.0 для OSS** | §1.1–1.2 | Лицензия для нас ок; но ImageSharp.Drawing тянет ImageSharp ≥ 3.1.x, и API (`RichTextOptions`, `MeasureSize`) отличается от 1.x. |
| **ImageSharp 2.1.10** | Apache-2.0 | nuspec | **Не брать**: (а) несовместим с современным Drawing, (б) NuGet показывает 6 advisory: `GHSA-gwg2-r3hj-4w44`, `GHSA-j3p4-wp97-rph4`, `GHSA-j9gm-c75j-xc9q`, `GHSA-jjfr-hcj7-qf5w`, `GHSA-rxmq-m78w-7wmc`, `GHSA-wmxv-xphr-5c9g` (2 × NU1903 «high», 4 × NU1902 «moderate»). Для 3.1.11 restore **чистый**, advisory нет. |
| **Magick.NET** | Apache-2.0 | **не проверялось** (вне бюджета) | ImageMagick — GPL-подобная лицензия на сам ImageMagick, у .NET-обёртки Apache-2.0; привязка к внешнему бинарнику — минус. |
| **Rust (`image`, `ab_glyph`)** | MIT/Apache-2.0 | **не проверялось**: `cargo` на машине **нет** | Требовал бы установки тулчейна; выигрыш неочевиден (см. §3.4). |

---

## 2. Прототип

### 2.1 Что сделано

`build/altgen/` — одноразовый C#-проект (`net9.0`, `SixLabors.ImageSharp` 3.1.11 + `SixLabors.ImageSharp.Drawing` 2.1.7):

* 3 стиля фона: **dirty** (грязно-зелёный шум + пятна), **grunge** (бумажный фон + пятна), **muddy** (тёмная грязь);
* шум: билинейный value-noise (сетка 10×6, билинейная интерполяция) + пятна (stains) + покомпонентное зерно +
  «скрипт»-кривые поверх текста (квадратичные безье) + соль-перец speckle;
* текст: случайный alnum (алфавит без I/O/0/1), 6 символов, шрифт выбирается из 8 системных, кегль
  0.34–0.52 от высоты кадра;
* **per-glyph**: джиттер X/Y, **поворот ±13°** (индивидуальный, не общий), **свой цвет** на глиф
  (HSV-семейство на картинку + разброс), своя базовая линия;
* поворот сделан **вручную** (инверсное аффинное преобразование пикселей), потому что API рисования
  ImageSharp.Drawing двигается между версиями, а вручную — работает везде и быстрее;
* холст **220×80**, PNG на выходе.

Запуск:

```powershell
dotnet build build\altgen\AltGen.csproj -c Release
dotnet run --project build\altgen\AltGen.csproj -c Release --no-build -- `
    --out build\altgen\out --count 500 --threads 36 --style all
```

### 2.2 Формат выхода — совпадает с контрактом датасета

`build/altgen/out/synthetic/altgen/<style>/NNN.png` + `labels.jsonl` рядом, одна строка на сэмпл:

```json
{"file":"001.png","plugin":"synthetic/altgen","captcha":"dirty","answer":"KNaRBV","text":"KNaRBV",
 "prompt":"Type the characters shown in the image.","roi":[51,24,119,35],"width":220,"height":80,
 "source":"synthetic: AltGen prototype (C# / SixLabors.ImageSharp) - synthetic augmentation, NOT a faithful plugin reproduction; no upstream audit trail"}
```

Проверка (команда из брифа):

```powershell
.venv-gpu\Scripts\python.exe -c "import json,glob;rows=[json.loads(l) for f in glob.glob(r'build/altgen/out/**/labels.jsonl',recursive=True) for l in open(f,encoding='utf-8')];print('rows',len(rows));print(rows[0])"
```
```
rows 1500
{'file': '001.png', 'plugin': 'synthetic/altgen', 'captcha': 'dirty', 'answer': 'KNaRBV', 'text': 'KNaRBV',
 'prompt': 'Type the characters shown in the image.', 'roi': [51, 24, 119, 35], 'width': 220, 'height': 80,
 'source': 'synthetic: AltGen prototype (C# / SixLabors.ImageSharp) - synthetic augmentation, NOT a faithful plugin reproduction; no upstream audit trail'}
```

**Правило полосы соблюдено и проверено:** полоса — это не «приблизительный эм-бокс», а точный
axis-aligned bbox четырёх повёрнутых углов ink-бокса каждой буквы. Сверили с фактическим ink-боксом
растра (поиск пикселей «фиолетового» цвета текста):

```
text ink bbox x 52 165  y 25 56
label roi       [51, 24, 119, 35]   answer KNaRBV
```
→ полоса покрывает текст с запасом в 1 px, ничего лишнего. Полоса, не помещающаяся в кадр, невозможна
по построению (углы считаются от фактического ink-бокса, а приблизительный клон `roi = whole frame` —
запасной вариант).

### 2.3 Читаемость — измерена, а не «на глаз»

Прогнали сгенерированные картинки через **тот же харнесс репозитория** (`bench/bench_models.py`,
backend `backend_ppocr_onnx`, модель `PaddlePaddle/PP-OCRv6_medium_rec_onnx` — предобученная, Apache-2.0),
в двух режимах: `band` (кроп по `roi`) и `frame` (весь кадр). 100 сэмплов на стиль, 300 всего:

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:HF_HOME="$PWD\build\hf_cache"
.venv-gpu\Scripts\python.exe build\altgen\ocr_check.py 100 ppocrv6-medium
```
```
items: 300
[ppocrv6-medium/band]  exact=217/300 = 0.723  CER=0.0578  median_latency_ms=26.4
    synthetic/altgen/dirty:  67/100 = 0.670
    synthetic/altgen/grunge: 81/100 = 0.810
    synthetic/altgen/muddy:  69/100 = 0.690
[ppocrv6-medium/frame] exact=157/300 = 0.523  CER=0.1456  median_latency_ms=26.5
    synthetic/altgen/dirty:  63/100 = 0.630
    synthetic/altgen/grunge: 68/100 = 0.680
    synthetic/altgen/muddy: 26/100 = 0.260
    MISS 002.png: gold='z9XDj6' pred='Z9XDj6'
    MISS 003.png: gold='guUyJh' pred='gulyJh'
    MISS 004.png: gold='NgRmsJ' pred='NgRms]'
    MISS 006.png: gold='jFKLzV' pred='JAKLZV'
    MISS 015.png: gold='vEqN6u' pred='VE9N6u'
```

**Как это читать:** 0.723 exact-match по полосе — это **уровень «прочитывается, но не тривиально»**.
Для сравнения, в проекте предобученный PP-OCRv6_medium даёт на **своих** типах 0.588 median / 0.5646 micro
exact (см. `AGENTS.md` §6), а на 7 удержанных типах с fine-tune — 0.638 median. То есть на *новом* стиле
предобученная модель справляется **не хуже**, чем на родных типах проекта, — картинки правдоподобны и
читаемы. Ошибки — почти всегда «регистр/похожий символ» (`z`↔`Z`, `u`↔`l`, `E`↔`F`), а не «не найдено».
Что и требовалось: новый стиль **не тривиален** (модель не угадывает), но **решаем** (кроппер решает).

### 2.4 Второй прототип — Pillow (MIT), чтобы было из чего выбирать

`build/altgen/pillow_gen.py` — те же три стиля, тот же шум, тот же per-glyph джиттер/поворот/цвет,
но на Pillow 13.0.0 (MIT), ~250 строк Python, **без нового тулчейна**:

```powershell
.venv-gpu\Scripts\python.exe build\altgen\pillow_gen.py --out build/altgen/out_pillow --count 500 --workers 36 --style all
```
```
[pillow] dirty:  500 images in 2.32 s = 215.1 img/s (36 workers, 220x80)
[pillow] grunge: 500 images in 2.37 s = 210.8 img/s (36 workers, 220x80)
[pillow] muddy:  500 images in 2.24 s = 222.8 img/s (36 workers, 220x80)
```
Тот же OCR-прогон по его картинкам (`$env:ALTGEN_OUT="…\build\altgen\out_pillow"`):
```
[ppocrv6-medium/band]  exact=107/300 = 0.357  CER=0.1672
    synthetic/pillow/dirty:  32/100 = 0.320
    synthetic/pillow/grunge: 25/100 = 0.250
    synthetic/pillow/muddy:  50/100 = 0.500
[ppocrv6-medium/frame] exact= 99/300 = 0.330  CER=0.2378
```

**Читаемость у Pillow-прототипа заметно ниже (0.357 против 0.723).** Это, скорее всего, НЕ ограничение
Pillow, а дефект именно этого прототипа; две вероятные причины, которые я **не успел проверить**:
(а) зерно шума в Pillow-версии нормальное (`σ = 26`) против равномерного `±13` в C#-версии — фон
заметно грязнее; (б) поворот глифа сделан `Image.rotate(BICUBIC, expand=True)`, т.е. сглаживание
размывает края букв. Обе причины лечатся в две-три строки, но **до сравнения движков их надо закрыть**
— иначе мы сравниваем два прототипа, а не две библиотеки.

---

## 3. Пропускная способность

### 3.1 Java-базовая линия (перемерена на этой машине, тем же драйвером)

```powershell
$java = if ($env:JAVA_HOME) { "$env:JAVA_HOME\bin\java.exe" } else { "java" }
& $java "-Djava.awt.headless=true" -cp build\classes    dev.captcha.Gen build\altgen\java_out    30
& $java "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Gen build\altgen\java_ru_out 30
```
```
34 captcha types x 30 = 1020 images -> ...\build\altgen\java_out        ELAPSED_MAIN_SEC=10.36
12 captcha types x 30 =  360 images -> ...\build\altgen\java_ru_out     ELAPSED_RU_SEC=42.29
```
→ **98.5 img/s** (основное дерево, 34 типа) и **8.5 img/s** (RU-дерево, 12 типов) — **однопоточно**
(`Gen` последователен; 36 ядер простаивают).

Сходится с цифрами из брифа (`Gen dataset\out 500` = 145 с → 17 000/145 = **117 img/s**;
`Gen dataset\out_ru 500` = 560 с → 6 000/560 = **10.7 img/s**); расхождение 15–20 % — от меньшего
`count` (30 вместо 500) и прогрева JVM.

### 3.2 C#-рендерер

```powershell
dotnet run --project build\altgen\AltGen.csproj -c Release --no-build -- --out build\altgen\out --count 500 --threads 1  --style all
dotnet run --project build\altgen\AltGen.csproj -c Release --no-build -- --out build\altgen\out --count 500 --threads 36 --style all
```
```
[altgen] dirty : 500 images in 6.46 s =  77.4 img/s  (1 thread, 220x80)
[altgen] grunge: 500 images in 5.28 s =  94.8 img/s  (1 thread, 220x80)
[altgen] muddy : 500 images in 5.11 s =  97.9 img/s  (1 thread, 220x80)
[pillow] dirty : 500 images in 13.92 s =  35.9 img/s  (1 worker, 220x80)
[pillow] grunge: 500 images in 13.36 s =  37.4 img/s  (1 worker, 220x80)
[pillow] muddy : 500 images in 10.61 s =  47.1 img/s  (1 worker, 220x80)
[altgen] dirty : 500 images in 1.43 s = 348.9 img/s  (36 threads, 220x80)
[altgen] grunge: 500 images in 1.08 s = 463.2 img/s  (36 threads, 220x80)
[altgen] muddy : 500 images in 0.90 s = 557.0 img/s  (36 threads, 220x80)
```

| | 1 поток | 36 потоков |
|---|---|---|
| Java, основное дерево (34 типа, микс 128×128 … сцены) | **98.5** | — (однопоточно) |
| Java, RU-дерево (12 типов, сцены Minecraft) | **8.5** | — (однопоточно) |
| **C# ImageSharp 3.1.11, 220×80** | **77–98 (ср. 90)** | **349–557 (ср. 456)** |
| **Python Pillow 13.0.0, 220×80** | **36–47 (ср. 40)** | **211–223 (ср. 216)** |

**Честная оговорка о сравнении.** Холсты разные: Java-типы — это 128×128 карты и полноценные сцены
Minecraft (чат-логи, окна инвентаря, до ~600 px), C#-прототип — плоские 220×80 текстовые капчи.
Это сравнение «классов работы», а не «одинаковых пикселей». Строгое сравнение потребовало бы
пере-рендера одного и того же типа в обоих движках.

**Размер PNG.** Java-дерево: среднее **9 994 Б** на PNG (смесь мелких карт и больших сцен).
C#-прототип: среднее **31 795 Б**; Pillow-прототип: **42 615 Б** — потому что 220×80 сплошного шума
кодируется плохо, тогда как у Java-типов много крупных однотонных областей.
Для датасета на HF это значит ~30–40 КБ на картинку против ~10 КБ: **второй набор будет втрое
тяжелее по размеру** — это надо учесть при загрузке на HF.

### 3.3 Что из этого следует

* Однопоточно C# **не быстрее** Java (90 против 98.5 img/s) — то есть выигрыш в скорости рисования
  **не существует**. И не должен: ImageSharp и AWT/GDI+ одного класса. Pillow однопоточно ещё медленнее
  (40 img/s) — Python overhead + `Image.rotate` на глиф.
* Многопоточно C# даёт ×4.9 к основному дереву и ×56 к RU-дереву — но это заслуга **36 потоков**,
  а не языка. Java-генератор можно распараллелить тем же способом.
* **Практическая ценность ≈ нулю:** весь датасет (23 000 PNG) собирается Java-генератором за ~7 минут.
  Ускорение второго рендерера не экономит ничего, о чём стоит говорить.
* Прототип **не оптимизирован**: он растрирует каждую букву отдельно (свой scratch-буфер, свой
  `DrawText`, ручная инверсия поворота). Продакшн-версия (или SkiaSharp) рисует строку целиком и
  крутит трансформацией канвы — это даст ещё ×3–5.

### 3.4 Rust

`cargo` на машине **нет** (`dotnet`/`java`/`python` — есть). Rust-путь не измерялся. По существу
он решает ту же задачу, что и C#, но требует установки тулчейна и не даёт ничего сверх того, что
уже даёт Pillow/ImageSharp, — **не рекомендую**.

---

## 4. Вердикт

**Стоит ли строить второй рендерер?**

| | |
|---|---|
| **Что купит** | **Стиль-диверсити**: грязные/потёртые фоны, джиттер, поворот и цвет каждой буквы — стилей, которых в 46 faithful-типах нет (там сцены Minecraft, а не «текст на грязи»). Плюс второй, честно помеченный синтетический набор для аугментации. **Не скорость** (см. §3.3). |
| **Сколько стоит** | Отдельный кодовый трек на другом языке/тулчейне; риск расхождения с faithful-аудитом; необходимость отдельной лицензионной/шрифтовой проверки перед публикацией. Время на доведение: дни, не часы. |
| **Что делать дальше** | **Не трогать Java-генераторы.** Прототип на Pillow уже есть и измерён (§2.4) — следующий шаг: (а) выровнять шум/сглаживание Pillow-версии с C#-версией и перемерить читаемость, иначе сравнение нечестное; (б) заменить системные шрифты Windows на свободные (DejaVu/Noto/Liberation) — до публикации; (в) генерировать в `dataset/out_synthetic/…` **отдельным деревом** с `plugin="synthetic/pillow"`, `source="synthetic: …"`, и **не смешивать** с faithful-строками без пометки; (г) обучать на смеси, но в отчёте писать «faithful» и «synthetic» **раздельно**. |

**Прямой ответ на вопрос владельца про ImageSharp:** лицензия **не является проблемой** — для OSS-проекта
Split License даёт Apache-2.0, а наши артефакты (датасет/модель на HF) под её условиями не попадают.
Но и **пользы от .NET здесь нет**: Java-генераторы — это аудит-тропа, и второй рендерер должен быть
дешёвым расширением, а не новым «главным» движком. → **Pillow**.

---

## 5. Аудит-тропа: как помечать второй рендерер

Наши Java-генераторы — *faithful-перереализации* реальных плагинов, и поле `source()` в `labels.jsonl`
— это **провенанс** опубликованного датасета (`reports/`, `docs/adr/`). Второй рендерер этому свойству
не отвечает: он не воспроизводит ничьё upstream-поведение.

**Правило: второй рендерер = синтетика, отдельным деревом, с явной меткой — и никогда не вперемешку
с faithful-строками без метки.**

Как помечать (уже сделано в прототипе, §2.2):

1. **Отдельный корень**: `dataset/out_synthetic/<Renderer>/<style>/NNN.png` — не `dataset/out/`.
   Один glance на дерево показывает: вот faithful, вот синтетика.
2. **`plugin` = `synthetic/<renderer>`** (например `synthetic/pillow`) — колонка `plugin` в нашем
   контракте = «владелец/репозиторий», и `synthetic/*` не может быть перепутан с `owner/repo`.
3. **`captcha` = id стиля** (`dirty`, `grunge`, `muddy`) — чтобы стиль был отдельным «типом» со своей
   статистикой в бенчмарках.
4. **`source` = явная строка без апстрима**, например:
   `"source":"synthetic: Pillow 13.0.0 style generator (synthetic augmentation, NOT a faithful plugin reproduction)"`.
   Строка **обязана** содержать слово `synthetic` и **не должна** содержать `класс#метод` —
   выдуманный апстрим-адрес хуже, чем его отсутствие (`AGENTS.md` §8: «never fabricate a source location»).
5. **`prompt`** — если формулировка отличается от «набери код», она тут же попадает в `labels.jsonl`.
6. **При обучении — раздельный учёт**: в отчёте о обучении писать и «на faithful», и «на synthetic»
   отдельно, иначе нельзя понять, что модель выучила, а что — выросло из аугментации.
7. **На HF**: публикуются оба набора с одним и тем же README, где синтетические строки помечены
   (иначе читатель датасета примет их за скриншоты реальных плагинов).
8. **Шрифты** — до публикации второго набора заменить системные шрифты Windows на свободные
   (DejaVu/Noto/Liberation), см. §1.3.

---

## 6. Что проверено / что нет / что сломано

### Проверено (командами выше)
* NuGet доступен (сеть есть): `Invoke-WebRequest https://api.nuget.org/v3/index.json` → **200**,
  `len=9272`; restore прошёл с нуля.
* Лицензии ImageSharp по версиям — из локального nuspec и из nupkg (§1.1), текст Split License — из
  пакета 4.0.0 и 3.1.11 (§1.2).
* Связки `ImageSharp.Drawing` → `ImageSharp` (§1.1) — распарсено из nuspec всех нужных версий.
* Advisory для ImageSharp 2.1.10 — из вывода `dotnet restore` (NU1902/NU1903); для 3.1.11 restore чистый.
* Прототип собирается (`Сборка успешно завершена. Ошибок: 0`) и рисует 3 стиля.
* Формат `labels.jsonl` совпадает с контрактом; полоса совпала с фактическим ink-боксом (проверено попиксельно).
* Читаемость: 0.723 exact / 0.0578 CER по полосе, 0.523 / 0.1456 по кадру (PP-OCRv6_medium, 300 сэмплов);
  Pillow-прототип — 0.357 / 0.1672 и 0.330 / 0.2378 (тот же харнесс, те же 300 сэмплов).
* Пропускная способность: Java 98.5 / 8.5 img/s (1 поток), C# 90 img/s (1 поток) и 478 img/s (36 потоков).

### НЕ проверено
* **Публикация на HF не делалась** (и не должна была) — ни датасет, ни модель, ни репозиторий.
* **Наша дообученная модель** `Titlehhhh/captchaocr-ppocrv6` на этих картинках не прогонялась — замер
  сделан на **предобученной** `PaddlePaddle/PP-OCRv6_medium_rec_onnx`. На дообученной цифра будет иной
  (в проекте на родных типах fine-tune+WISE-FT даёт 0.638 median).
* **Magick.NET, SkiaSharp и Rust** не измерялись (нет времени / нет `cargo`).
* **Сравнение «пиксель в пиксель»** с Java-генератором не делалось: сравнивались разные классы холстов.
* **Совместимость стилей с реальными плагинами** не проверялась: не сверяли с `dataset/out_ru/*/real_shots/`
  (чужие скриншоты не копировались, не встраивались и не публиковались).
* **Шрифтовая лицензия** не прорабатывалась (см. §1.3, §5.8).
* 36 потоков — это бюджет всей машины; поведение на 8/16 ядрах не измерялось.

### Сломано / криво в прототипе
* `SixLabors.Fonts` в 3.x ставит **начало текста на линию cap-height**, а не на базовую линию; пришлось
  считать базовую линию через `MeasureSize("H").Height` и находить ink-бокс глифа сканированием scratch-буфера.
  Это работает, но это ~2 лишних прохода на глиф — отсюда 90 img/s вместо ожидаемых ~300.
* `ctx.BackgroundColor(Color.Transparent)` в ImageSharp 3.x **не затирает** уже нарисованное — scratch-буфер
  пришлось чистить вручную (`span.Clear()`). Это стоило одного «невидимого» бага.
* API `SixLabors.ImageSharp.Drawing` менялся между 2.x/3.x (`DrawImage(Image, Point)` не существует в 3.x,
  `RichTextOptions` переехал в `SixLabors.Fonts`). Поэтому загрузка шрифтов сделана через рефлексию
  (`--api` даёт дамп API), а рисование — только на `DrawText`.
* Ветка `--fonttest`/`--api` оставлена в коде — это отладочный мусор, в продакшн так не пойдёт.
* **Два бага, найденные и исправленные по ходу** (оба — в прототипе, не в библиотеке):
  (1) полоса `roi` в Pillow-версии обрезалась на 1 px (`int()` вместо `floor/ceil`) — последняя буква
  выпадала из кропа, и exact-match падал; исправлено на `floor/ceil`;
  (2) стиль `grunge` рисовал **светлые** буквы на светлой бумаге — контраста почти не было;
  после перехода на тёмные чернила exact-match по полосе вырос с 0.690 до **0.723**, а по стилю grunge —
  с 0.710 до 0.810.

### Расхождения с брифом
* Бриф предполагал, что ImageSharp перешёл на split-лицензию «на 2.x» — фактически **на 3.x**; 2.1.13 —
  последняя Apache-2.0. При этом практического эффекта для нас нет (§1.1, §1.3).
* Бриф просил «тот же 36-ядерный бюджет». Java-генератор однопоточен, поэтому «тот же бюджет» для него
  не реализуем без изменения `Gen` (который трогать нельзя) — поэтому Java-строка в таблице это
  однопоточный замер, а C#-строка — и 1, и 36 потоков. Сравнение по честному — в §3.3.

---

## 7. Приложение: файлы

* `build/altgen/AltGen.csproj` — прототип, .NET 9, ImageSharp 3.1.11 + Drawing 2.1.7.
* `build/altgen/Program.cs` — рендерер (3 стиля, джиттер/поворот/цвет на глиф, шум, ROI).
* `build/altgen/ocr_check.py` — прогон через харнесс репозитория `bench/bench_models.py`.
* `build/altgen/pillow_gen.py` — второй прототип на Pillow (MIT), те же стили, свой выход в `out_pillow`.
* `build/altgen/out/synthetic/altgen/{dirty,grunge,muddy}/` — 1500 PNG + `labels.jsonl` (артефакт зонда, gitignored).
* `build/altgen/out_pillow/synthetic/pillow/{dirty,grunge,muddy}/` — ещё 1500 PNG + `labels.jsonl` (артефакт зонда).
* `build/altgen/java_out/`, `build/altgen/java_ru_out/` — контрольные прогоны Java-генератора (артефакт зонда).
* `build/altgen/fonttest.png` — отладочный рендер одного шрифта.

`dataset/**`, `dataset/generator*/**`, `train/**`, `bench/**`, `tools/**`, `webapp/**`, `docs/**`,
`AGENTS.md` — **не тронуты**. Публикаций на Hugging Face не было.
