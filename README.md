# CaptchaOCR — открытый датасет капт Minecraft-антиботов и распознавание этих капт

**Открытый датасет из 46 типов капч (4600 размеченных картинок) и первая нейросеть, которая
учится их читать.** Проект — лабораторная работа по машинному зрению на Python и Java.

---

## Что это такое

В Minecraft есть плагины-антиботы: они показывают игроку картинку с кодом и просят ввести этот
код в чат, чтобы отсечь автоматические боты. Их называют **капчами** (captcha). Таких плагинов
десятки, и каждый рисует капчу по-своему: свой шрифт, свой размер холста, свои линии-помехи, свои
ошибки.

Готовые модели распознавания текста на таких картинках работают плохо — это и замерено в этом
репозитории (см. раздел «Модель»). Чтобы разобраться, почему, нужен датасет: настоящие капчи,
а не абстрактные буквы на белом фоне.

**Этот репозиторий и есть такой датасет.** На Java 21 написаны генераторы, которые заново
отрисовывают капчи тех же открытых Minecraft-плагинов — пиксель в пиксель, с теми же шрифтами,
теми же искажениями и даже с теми же **ошибками** оригинала. Каждый тип капчи снабжён
разметкой: что нарисовано на картинке, что игрок должен ввести, и где на картинке лежит полоса
с ответом.

Вторая половина проекта — **модель**: сравнение готовых OCR-моделей на этом датасете и обучение
своей нейросети (CRNN + CTC) с нуля.

Кому это может быть полезно: тем, кто делает системы компьютерного зрения, тем, кто изучает
OCR, и тем, кому просто интересно, как устроены капчи и почему нейросети на них ломаются.

## Задача

Взять картинку-капту Minecraft-антибота и **выдать ответ, который игрок должен ввести**.

Это не одна задача, а три разных, и их полезно различать:

| | что это | сколько типов |
|---|---|---|
| **A** | ответ **нарисован** в картинке — его достаточно прочитать | 20 типов (2000 картинок) |
| **B** | картинку надо прочитать, а потом преобразовать (перевернуть строку, посчитать пример, перевести слова в цифры) | 11 типов (1100 картинок) |
| **C** | это вообще **не задача чтения текста**: ответ — цвет, номер слота или заранее известная константа | 15 типов (1500 картинок) |

Разбивка на группы A/B/C — измерена по разметке, а не по догадкам (`agents/INDEX.md` §4).

## Что внутри

### Цифры

| | |
|---|---|
| Типов капч | **46** |
| Размеченных PNG | **4600** (по 100 на тип) |
| Плагинов-источников | **23** |
| Из них: faithful / clean-room / reconstructed | **12 / 10 / 1** (по типам: 25 / 16 / 5) |
| Эталонных скриншотов (не обучающих, в публику не идут) | 517 |
| Модель | CRNN + CTC, 4 623 615 параметров |

Два дерева-источника:

* `dataset/out/` — **34 типа** от **18** плагинов из публичных репозиториев (Bukkit, Spigot,
  Velocity, BungeeCord, Paper, Forge). Путь: `dataset/out/<owner>/<repo>/<тип>/NNN.png`.
* `dataset/out_ru/` — **12 типов** от **5** источников: `LimboFilter`, `BotFilter`, `CaptchaGUI`,
  `CaptchaVerifyZ` и группа `GalleryCaptcha/*` (5 реконструированных типов). Путь:
  `dataset/out_ru/<Плагин>/<тип>/NNN.png`.

### Что означают режимы

| Режим | Что это | Когда так бывает |
|---|---|---|
| **faithful** | построчная реализация по исходникам плагина | лицензия апстрима это разрешает |
| **clean-room** | алгоритм прочитан по исходникам, но код, имена и комментарии написаны заново | лицензия запрещает копирование, либо лицензии нет |
| **reconstructed** | плагина за каптой нет; стиль восстановлен по эталонным скриншотам | тип из группы `GalleryCaptcha/*` |

### Плагины, чьи капты воспроизведены

**`dataset/out/` — 18 плагинов, 34 типа**

| Плагин | Платформа | Лицензия | Типы | Режим |
|---|---|---|---|---|
| [LagBug/XProtect](https://github.com/LagBug/XProtect) | Bukkit/Spigot | MIT | `code` `color` `different` `drop` `equation` `gui` `jump` `map` `picture` `reverse` `slot` `sneak` | faithful |
| [jonesdevelopment/sonar](https://github.com/jonesdevelopment/sonar) | Velocity | GPL-3.0 | `standard` `complex` `legacy` | clean-room |
| [Archy-X/Krypton](https://github.com/Archy-X/Krypton) | Bukkit | нет | `map` `menu` | clean-room |
| [FeelingAlive0/AdvancedCaptcha](https://github.com/FeelingAlive0/AdvancedCaptcha) | Bukkit | MIT | `button` `math` | faithful |
| [jSdCool/minecaptcha](https://github.com/jSdCool/minecaptcha) | Fabric (серверный мод) | CC0-1.0 | `text` `image` | faithful |
| [Z4OLLIEZ4/reCaptcha](https://github.com/Z4OLLIEZ4/reCaptcha) | Bukkit | MIT | `captchasx` | faithful |
| [Joey61021/captcha](https://github.com/Joey61021/captcha) | Bukkit | MIT | `colorgui` | faithful |
| [laforetbrut/are-you-sure](https://github.com/laforetbrut/are-you-sure) | Forge + NeoForge (клиент) | MIT | `code` | faithful |
| [Mrbysco/Captcha](https://github.com/Mrbysco/Captcha) | Forge (сервер) | MIT | `math` | faithful |
| [Yukun99/Captchas](https://github.com/Yukun99/Captchas) | Bukkit | нет | `itemslot` | clean-room |
| [China2B2T/Captcha](https://github.com/China2B2T/Captcha) | Bukkit | GPL-3.0 | `wool` | clean-room |
| [InstantlyMoist/Captcha](https://github.com/InstantlyMoist/Captcha) | Bukkit/Spigot | MIT | `textcaptcha` | faithful |
| [JSH32/Minecaptcha](https://github.com/JSH32/Minecaptcha) | Bukkit | MIT | `map` | faithful |
| [haq/mapcha](https://github.com/haq/mapcha) | Bukkit | MIT | `map` | faithful |
| [just-captcha/ProstoCaptcha](https://github.com/just-captcha/ProstoCaptcha) | Velocity 3 | MIT | `map` | faithful |
| [irootdev/AnBot](https://github.com/irootdev/AnBot) | BungeeCord | GPL-3.0 | `captcha` | clean-room |
| [ringoame196-s-mcPlugin/ReproductionCAPTCHA](https://github.com/ringoame196-s-mcPlugin/ReproductionCAPTCHA) | Paper (Kotlin) | файла лицензии нет | `map` | clean-room |
| [n1zamu/NCaptcha](https://github.com/n1zamu/NCaptcha) | Bukkit | MIT | `anvil` | faithful |

**`dataset/out_ru/` — 5 источников, 12 типов**

| Источник | Платформа | Лицензия | Типы | Режим |
|---|---|---|---|---|
| [Elytrium/LimboFilter](https://github.com/Elytrium/LimboFilter) | Velocity | AGPL-3.0 | `map` `symbols` `framed2x2` `framed3x3` | clean-room |
| `BotFilter` (Leymooo, BungeeCord) | BungeeCord | BSD с дополнительной оговоркой | `map` | clean-room |
| `CaptchaGUI` (Supl1n) | Bukkit | не указана | `clickblock` | clean-room |
| `CaptchaVerifyZ` | Bukkit | все права защищены (Modrinth: `LicenseRef-All-Rights-Reserved`) | `map` | clean-room, **проверено по пикселям** |
| группа `GalleryCaptcha/*` | — | — | `ru-numberword` `ru-numberword-caption` `ru-symbols` `ru-web` `ru-object-swatch` | reconstructed |

> Два разных плагина называются **Minecaptcha**: `JSH32/Minecaptcha` (пакет `riku32.captcha`) и
> `jSdCool/minecaptcha` (пакет `org.cbigames.captcha`). Это разные кодовые базы с разными
> платформами, их нельзя сливать.

### Дефекты апстрима воспроизводятся, а не чинятся

Это главный принцип датасета. Модель, обученная на «исправленной» капче, будет работать
хорошо на датасете и плохо на реальном сервере. Поэтому каждая найденная ошибка оригинала
воспроизведена и задокументирована. Несколько примеров:

* `haq/mapcha` и `JSH32/Minecaptcha` выбирают символ как `nextInt(len - 1)` — последний символ
  алфавита (`'Z'`) недостижим, код всегда из 61 символа, а не из 62.
* `jSdCool/minecaptcha` переставляет `L` и `M` в алфавите. Это **не** «пропавшая буква»: все
  26 заглавных присутствуют, неверен только порядок.
* `China2B2T/Captcha` объявляет счётчик ошибок **внутри** обработчика клика, поэтому ветка
  «кикнуть за 3 ошибки» недостижима — неправильные клики не наказываются.
* `Yukun99/Captchas` подставляет имя нужного предмета в заголовок окна — ответ напечатан в
  самом заголовке.
* `just-captcha/ProstoCaptcha` проверяет ответ с учётом регистра, а его алфавит не содержит
  `l`, `I` и `O` — три буквы никогда не рисуются.
* `irootdev/AnBot` проверяет ответ как **подстроку** сырого чата: подойдёт любое сообщение,
  содержащее код.

Полный список — в `agents/INDEX.md` и в отчётах.

### Разметка

По одному `labels.jsonl` на тип, одна строка JSON на картинку:

| Поле | Что это |
|---|---|
| `file` | имя PNG внутри каталога типа, например `001.png` |
| `plugin` | плагин-источник (совпадает с каталогом уровнем выше) |
| `captcha` | тип капчи (совпадает с именем каталога) |
| `answer` | что игрок должен ввести. Регистр и формат значимы |
| `text` | что **нарисовано**. У 9 типов из 46 отличается от `answer` (русские слова-числа, арифметические примеры, разворот строки) |
| `roi` | прямоугольник полосы с ответом `[x, y, w, h]` или `null`, если полосы нет |
| `prompt` | текст задания, который видит игрок |
| `width`, `height` | размер картинки в пикселях |
| `source` | класс и метод апстрима, откуда взят алгоритм |

**Правило полосы: полоса, которая не помещается в кадр, — это не полоса.** Если в прямоугольник
попало только часть ответа, `roi` возвращается как `null`, а не как обрезанный прямоугольник.
Полосу несут 29 типов из 46: у остальных ответ либо занимает весь кадр, либо его в кадре нет.

## Датасет на Hugging Face

Полный датасет — **4600 PNG, около 43.6 МБ** — лежит **не в git**, а в отдельном датасет-репозитории
на Hugging Face.

**Почему так.** Git хранит историю: каждый коммит с картинками навсегда остаётся в `.git`, даже
если файлы удалить из рабочей копии. Полная история репозитория с этим датасетом весит **около
142 МБ** (`git count-objects -vH`) при 43.6 МБ самих размеченных картинок — репозиторий растёт
быстрее, чем полезная нагрузка, и клонируется тяжело.
Hugging Face для датасетов подходит лучше: там картинки лежат обычными файлами, обновляются
по кускам и качаются по HTTP без git.

**Скачать полный датасет** — одной командой из корня репозитория:

```powershell
python tools\fetch_dataset.py
```

Скрипт `tools/fetch_dataset.py` качает датасет-репозиторий `Titlehhhh/captchaocr-dataset`
в `dataset/full/` (кэш — `HF_HUB_CACHE`/`HF_HOME`, а если общий кэш на этой машине не пишется —
то `.hf-cache/` рядом с репозиторием). Полезные флаги:

```powershell
python tools\fetch_dataset.py --dry-run                       # печатает план и НЕ ходит в сеть
python tools\fetch_dataset.py --types "haq/mapcha/map" "GalleryCaptcha/ru-symbols"
python tools\fetch_dataset.py --cache-dir .hf-cache           # кэш целиком внутри репозитория
```

`--dry-run` печатает, что именно скачается (46 типов, 4600 PNG, 43.6 МБ) — и ничего не качает.

Если `huggingface_hub` не установлен, тот же набор файлов можно забрать и без него:

```powershell
pip install -U huggingface_hub
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Titlehhhh/captchaocr-dataset', repo_type='dataset', local_dir='dataset/full')"
```

**Что остаётся в git-репозитории:**

* генераторы на Java 21 (`dataset/generator/`, `dataset/generator_ru/`) — они и есть источник
  датасета, и по ним видно, как каждая картинка получена;
* разметка `labels.jsonl` на каждый тип (46 файлов) и `index.html` каждого дерева;
* **образцы**: по 5 картинок на каждый из 46 типов в `dataset/samples/` — 230 PNG, 2.2 МБ,
  плюс `dataset/samples/README.md` и витрина `dataset/samples/index.html`;
* весь код обучения и бенчмарков.

**Почему картинок датасета в репозитории нет.** Правила `.gitignore` (`dataset/out/**/*.png`,
`dataset/out_ru/**/*.png`) убирают 4600 PNG из индекса git: `labels.jsonl` и `index.html`
остаются отслеживаемыми, а сами картинки живут на Hugging Face. Заодно из индекса уходят
эталонные скриншоты `real_shots/` — чужие скриншоты в публику не идут. Посмотреть, что вообще
бывает, можно по образцам: `dataset/samples/index.html` — контактный лист по 5 картинок
на тип с ответами.

Датасет **воспроизводим по типам**: пересборка генераторов даёт те же 46 типов и ту же разметку.
Но **генераторы не засеяны**, так что набор сэмплов каждый раз разный: системные шрифты AWT
те же, а сами случайные значения — новые. Поэтому датасет генерируется один раз и используется
как артефакт.

## Как запустить

Всё проверено на **Windows** (PowerShell 5.1). Скрипт `build.ps1` на этой машине выполнить
нельзя (запуск `.ps1` заблокирован политикой), поэтому команды даны инлайн — их можно копировать
и вставлять как есть.

Нужен **Java 21** (в примере — `I:\ForAndroid\Java\21`) и **Python** (для проверок и обучения).

```powershell
# 1. Скомпилировать оба дерева генераторов
$java = "I:\ForAndroid\Java\21\bin"
$core = Get-ChildItem -File dataset\generator\dev\captha\*.java | % FullName
& "$java\javac.exe" -encoding UTF-8 -d build\classes -sourcepath dataset\generator $core (Get-ChildItem -Recurse -Filter *.java dataset\generator | % FullName)
& "$java\javac.exe" -encoding UTF-8 -d build\classes_ru -sourcepath dataset\generator_ru $core (Get-ChildItem -Recurse -Filter *.java dataset\generator_ru | % FullName)

# 2. Сгенерировать датасет (по 100 картинок на тип) и проверить его
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes    dev.captcha.Gen      dataset\out    100
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes    dev.captcha.Validate dataset\out
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Gen      dataset\out_ru 100
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Validate dataset\out_ru

# 3. Проверить разметку и полосы
python tools\check_labels_and_roi.py dataset\out_ru
python tools\check_band_vs_answer.py dataset\out_ru

# 4. Обучить (нужен venv с CUDA-сборкой torch; системный python — только CPU)
.venv-gpu\Scripts\python.exe train\train.py --trees both --epochs 80 --val-types "haq/mapcha/map" "CaptchaVerifyZ/map"
```

Три консольные утилиты генератора:

| Команда | Что делает |
|---|---|
| `dev.captcha.Gen <outDir> <count>` | Рисует все генераторы `count` раз, пишет PNG, `labels.jsonl` на тип и `index.html` |
| `dev.captcha.Validate <outDir>` | Таблица по типам `n / minColors / blank / dupes / labels`: ловит пустые кадры, дубли и расхождения меток |
| `dev.captcha.Stats <png\|dir>` | Гистограмма цветов картинки — способ проверить рендер, не глядя на неё |

Все три работают без графического экрана (`java.awt.headless=true`).

### Как добавить свой тип капч

1. Положить в `dataset/generator/dev/captcha/gens/` класс `public static final class X implements Cg`
   с **публичным конструктором без аргументов**.
2. Реализовать `plugin()`, `id()`, `answer()`, `image()`, `source()`; при необходимости
   переопределить `prompt()` и `roi()`.
3. Пересобрать. `Gen` находит классы рефлексией и регистрирует их сам — **реестр править не надо**.

Подробные правила (в том числе «faithful over pretty» и правило полосы) — в
`dataset/generator/AGENTS.md`.

## Модель

### Архитектура

**CRNN (свёрточная сеть + двунаправленный LSTM) + CTC-декодирование**, обучение с нуля:
4 623 615 параметров, 63 класса (blank + `0-9A-Za-z`). Код — `train/captcha_crnn.py`,
тренажёр — `train/train.py`.

Почему так: 4600 картинок против 334 миллионов параметров у TrOCR — на этой задаче мелкая
доменная модель выигрывает. CTC, а не attention: метки случайные, языковой модели нечего
эксплуатировать, а CTC сразу даёт распределение по символам.

### Как измеряем

* **exact match** (доля картинок, где строка угадана целиком) и **CER** (частота ошибок по
  символам);
* **разбиение — по типам, а не по картинкам.** Единица обобщения здесь — плагин: если один тип
  попал в обучение, а его родственник — в проверку, модель «знает» шрифт и рендерер и метрика
  ничего не значит. Поэтому проверка идёт по целым семействам типов (4 фолда), а главное
  число — **медиана по типам**, а не среднее по фолду.

### Измеренные числа

Готовые модели на тех же данных (по 20 картинок на тип, все 46 типов, `reports/bench_models/`):

| Модель | по полосе `roi` | по всему кадру | CER (по полосе) |
|---|---|---|---|
| `PP-OCRv6_medium_rec` | **0.404** | 0.078 | 0.566 |
| `PP-OCRv5_mobile_rec` | 0.315 | 0.028 | 0.530 |
| `EasyOCR` | 0.115 | — | 1.861 |
| `jtrecenti/txtcaptcha-crnn` | 0.002 | 0.000 | 1.046 |

**Главный вывод из этих чисел: решает кроппер, а не модель.** На 29 типах, у которых есть полоса,
`PP-OCRv6_medium_rec` даёт **0.552** по полосе и **0.035** по целому кадру — в **16 раз** хуже
на кадре. Отсюда правило всего проекта: модель получает не кадр, а вырезанную полосу.

**А вот честная часть про нашу собственную модель.** CRNN, обученная с нуля на 10 типах
(1000 картинок), даёт **accuracy 1.000 на типах, на которых учили**, и **accuracy 0.000 на
невиданных типах** (CER 0.912–1.058, медиана 0.954; в 4-фолдном прогоне — acc 0.000, медиана CER
0.958). Это не баг, а измерение границы текущих данных: модель **запоминает**, а не обобщает.
Полный разбор — `reports/TRAINING_MINIMAL_LATIN.md`.

Что из этого следует и что дальше: нужны больше типов (сейчас пригодно к обучению заметно меньше
половины), расширение алфавита (кириллица и пробел), и предобучение на публичном корпусе капч.
Мы это ещё не сделали, и это честное «не сделано», а не обещание.

## Структура репозитория

```
dataset/generator/       генераторы капт (Java 21): 18 плагинов, 34 типа
dataset/generator_ru/    генераторы второй половины: 5 источников, 12 типов
dataset/out/             картинки 34 типов (в git не входят) + labels.jsonl
dataset/out_ru/          картинки 12 типов (в git не входят) + labels.jsonl
dataset/samples/         образцы: по 5 PNG на каждый тип (230 файлов, 2.2 МБ) + index.html
bench/                   харнессы для чужих моделей + единый протокол bench_models.py
train/                   CRNN+CTC, тренажёр, экспорт в ONNX и Hugging Face
tools/                   проверки меток и полос, анализ капч, сборка отчётов
site/                    сайт-атлас: все капты крупно и разбивка по типам
research/                исходники апстримов, декомпиляция, эталонные рендеры
reports/                 измеренные результаты и отчёты (research/, research2/, research3/)
docs/                    онбординг, глоссарий, ADR, проектная записка
agents/                  карта репозитория, журнал сессий, правила для агентов
AGENTS.md                правила работы в репозитории
HANDOVER.md              состояние проекта и все измеренные числа
CONTINUE.md              что сделано, что делать дальше
```

## Лицензии и этика

**Лицензия каждого плагина-источника — в таблице выше.** Датасет нельзя выкладывать одним
монолитом: часть плагинов под GPL-3.0 и AGPL-3.0, у трёх лицензии нет вовсе. Поэтому публикация
разбита по семействам лицензий, и в каждой записи стоит режим (faithful / clean-room /
reconstructed) и лицензия апстрима.

**Правило «faithful vs clean-room».** `faithful` — построчная реализация по исходникам, её
лицензия разрешает. `clean-room` — алгоритм и картинка прочитаны по исходникам, но код,
комментарии, идентификаторы и заголовки авторских прав **не перенесены**; так делается всегда,
где лицензия запрещает копирование или где лицензии нет.

**В репозитории нет материалов сторонних коммерческих сервисов.** В датасет не попали ни
картинки, ни страницы, ни ответы API коммерческих сервисов решения капт; **чужие скриншоты из
репозитория удалены** — в публику идёт только то, что воспроизведено нашими собственными
генераторами. Эталонные скриншоты, по которым делались реконструкции, в датасет и в git не
входят.

**Ещё два принципа.**

* **Дефекты апстрима не «чинятся»** — они воспроизводятся и документируются. Иначе модель будет
  хороша на датасете и бесполезна на сервере.
* **Источник каждой строки разметки известен** — поле `source` в `labels.jsonl` и метод `source()`
  в каждом генераторе. Если исходник плагина найти не удалось, это сказано прямо, а тип помечен
  как clean-room или reconstructed; выдуманных ссылок на исходники в проекте нет.

## Ссылки

* **Датасет на Hugging Face** (заглушка, будет опубликован):
  <https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset>
* **Модель на Hugging Face** (заглушка, будет опубликована):
  <https://huggingface.co/Titlehhhh/captchaocr-ppocrv6>
* **Репозиторий**: <https://github.com/Titlehhhh/CaptchaOCR>

Статьи, на которые опирается проект (все упомянуты в отчётах `reports/research/` и
`reports/research2/`):

* CRNN — Shi et al., *An End-to-End Trainable Neural Sequence Recognition and Its Application to
  Scene Text Recognition* — [arXiv:1507.05717](https://arxiv.org/abs/1507.05717)
* PP-OCRv6 — [arXiv:2606.13108](https://arxiv.org/abs/2606.13108)
* SVTRv2 — [arXiv:2411.15858](https://arxiv.org/abs/2411.15858)
* GTC (внимание к контексту) — [arXiv:2002.01276](https://arxiv.org/abs/2002.01276)
* SynthTIGER — [arXiv:2107.09313](https://arxiv.org/abs/2107.09313)
* StrDA — [arXiv:2410.09913](https://arxiv.org/abs/2410.09913)
* SynthText — [arXiv:1704.04811](https://arxiv.org/abs/1704.04811)

---

Проект — лабораторная работа. Если что-то в документации не сходится с измерениями, правы
измерения: они лежат в `reports/`, а решения — в `agents/INDEX.md` и `docs/adr/`.
