# Галерея CaptchaOCR — что построено и что измерено

**Дата:** 22.10.2026 · **Агент:** T-GALLERY-BUILD · **Задача:** замерить опубликованную модель на всех
46 типах, переделать локальную галерею в стиле Kinpaku и опубликовать её в карточке датасета на HF.

Итог одним абзацем: модель **решает не «все капчи», а конкретные 29 типов с полосой** — на них
median exact match **0.651**, micro **0.502** по всем 46 типам. На 7 удержанных типах, на которых
модель была опубликована, тот же код даёт ровно опубликованные **0.638 median / 0.6123 micro** —
значит, пайплайн воспроизводится и цифрам можно верить.

---

## 1. Что измерено

| | |
|---|---|
| **Модель** | `train/run_ppocr/big/export_soup/` — байт-в-байт то, что лежит в `Titlehhhh/captchaocr-ppocrv6` (PP-OCRv6_medium_rec + WiSE-FT, α = 0.4, эпоха 7, шаг 1632) |
| **Данные** | `dataset/out/**` + `dataset/out_ru/**`, 46 типов × 500 PNG = 23 000 картинок |
| **Пайплайн** | **импортирован**, а не переписан: `train/ppocr_data.py` (поиск типов, кроп по `roi`, кроп по рамке чернил для кадров без полосы, 48×320, BGR, нормализация Paddle `(x/255-0.5)/0.5`) + `train/finetune_ppocr.py` (`norm()`, `aggregate()`) |
| **Декодирование** | `AutoProcessor.from_pretrained(<export>)` → `processor.post_process_text_recognition(out)`, поле `last_hidden_state` (не `.logits`) |
| **Метрики** | exact match и CER по нормализованной `text` (нарисованной строке), micro по картинкам + медиана по типам — ровно как в `aggregate()` |
| **Скорость** | 23 000 картинок за **172 с** на GTX 1080 Ti (fp16, batch 64, 6 воркеров) |

**Сторожевой декод:** первые 8 батчей дополнительно декодируются «старым» способом
(`greedy_decode` из `train/finetune_ppocr.py`) и сравниваются с ответом процессора —
**расхождений 0**. Значит, новое декодирование не изменило числа.

### Ключевые числа

| | exact match | CER |
|---|---|---|
| **Все 46 типов, micro** (23 000 картинок) | **0.502** | 0.5322 |
| **Все 46 типов, медиана по типам** | **0.651** | 0.1173 |
| 7 удержанных типов, micro (3 500 картинок) | 0.6123 | 0.2004 |
| 7 удержанных типов, медиана | 0.638 | 0.1503 |
| опубликованные с моделью числа | 0.6123 / 0.638 | 0.2004 / 0.1503 |

Последние две строки — **одно и то же**: код, которым меряем сейчас, воспроизводит опубликованный
результат до последнего знака.

### Почему «все 46» хуже, чем «7 удержанных» (0.502 против 0.6123)

Честно и по типам, а не «модель плохая»:

1. **Типы без полосы.** В 17 типах из 46 `roi = null` — модель видит кадр целиком (обрезанный по
   рамке чернил). Для «нового кадра» это в 16 раз хуже, чем для полосы (измерено раньше на
   `PP-OCRv6_medium_rec`).
2. **Группа C — это вообще не OCR.** 16 типов: ответ = название цвета, номер слота, индекс
   картинки, константа. Ноль exact match там — свойство задачи, а не дефект модели. Обратная
   сторона: в 6 таких типах модель даёт **1.000** (константный ответ «1», «drop», «jump»…),
   потому что капча однотипная.
3. **Кириллица вне словаря модели.** В словаре PP-OCRv6 (18 710 классов) **нет ни одной
   кириллической буквы**: `ru-numberword`, `ru-numberword-caption`, `LimboFilter/map`,
   `framed2x2`, `framed3x3` — все 0.000. Ответ физически нельзя выразить.
4. **Регистр.** Точное совпадение регистрозависимое: `93j79` против `93J79` — это промах
   (красная подпись в галерее), хотя CER = 0.

Полная таблица по 46 типам — в `reports/model_scoreboard.json` (`types`), в галерее
(`reports/HTML/index.html`, раздел «Скорее таблица») и в карточке HF.

| # | тип | n | exact match | CER | медианная длина ответа | все 500 |
|---|---|---|---|---|---|---|
| 1 | `out/LagBug/XProtect/drop` | 500 | 100.0% | 0.000 | 4 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/drop) |
| 2 | `out/LagBug/XProtect/equation` | 500 | 100.0% | 0.000 | 6 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/equation) |
| 3 | `out/LagBug/XProtect/gui` | 500 | 100.0% | 0.000 | 9 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/gui) |
| 4 | `out/LagBug/XProtect/jump` | 500 | 100.0% | 0.000 | 4 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/jump) |
| 5 | `out/LagBug/XProtect/slot` | 500 | 100.0% | 0.000 | 1 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/slot) |
| 6 | `out/LagBug/XProtect/sneak` | 500 | 100.0% | 0.000 | 5 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/sneak) |
| 7 | `out/n1zamu/NCaptcha/anvil` | 500 | 100.0% | 0.000 | 5 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/n1zamu/NCaptcha/anvil) |
| 8 | `out/FeelingAlive0/AdvancedCaptcha/math` | 500 | 99.8% | 0.001 | 6 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/FeelingAlive0/AdvancedCaptcha/math) |
| 9 | `out_ru/CaptchaVerifyZ/map` | 500 | 99.8% | 0.000 | 5 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/CaptchaVerifyZ/map) |
| 10 | `out/jSdCool/minecaptcha/text` | 500 | 98.6% | 0.002 | 8 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/jSdCool/minecaptcha/text) |
| 11 | `out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | 500 | 95.6% | 0.009 | 5 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map) |
| 12 | `out/JSH32/Minecaptcha/map` | 500 | 95.0% | 0.013 | 4 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/JSH32/Minecaptcha/map) |
| 13 | `out/irootdev/AnBot/captcha` | 500 | 94.8% | 0.018 | 3 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/irootdev/AnBot/captcha) |
| 14 | `out_ru/GalleryCaptcha/ru-web` | 500 | 94.6% | 0.012 | 5 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/GalleryCaptcha/ru-web) |
| 15 | `out/haq/mapcha/map` | 500 | 94.4% | 0.015 | 4 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/haq/mapcha/map) |
| 16 | `out/Z4OLLIEZ4/reCaptcha/captchasx` | 500 | 92.6% | 0.011 | 5 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/Z4OLLIEZ4/reCaptcha/captchasx) |
| 17 | `out/Archy-X/Krypton/map` | 500 | 90.8% | 0.020 | 5 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/Archy-X/Krypton/map) |
| 18 | `out/LagBug/XProtect/reverse` | 500 | 90.4% | 0.018 | 6 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/reverse) |
| 19 | `out/Mrbysco/Captcha/math` | 500 | 86.4% | 0.030 | 7 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/Mrbysco/Captcha/math) |
| 20 | `out/Joey61021/captcha/colorgui` | 500 | 82.8% | 0.029 | 4 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/Joey61021/captcha/colorgui) |
| 21 | `out/Yukun99/Captchas/itemslot` | 500 | 81.4% | 0.018 | 10 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/Yukun99/Captchas/itemslot) |
| 22 | `out_ru/BotFilter/map` | 500 | 74.0% | 0.084 | 4 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/BotFilter/map) |
| 23 | `out/just-captcha/ProstoCaptcha/map` | 500 | 66.4% | 0.078 | 6 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/just-captcha/ProstoCaptcha/map) |
| 24 | `out/jonesdevelopment/sonar/standard` | 500 | 63.8% | 0.150 | 3 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/jonesdevelopment/sonar/standard) |
| 25 | `out/jonesdevelopment/sonar/complex` | 500 | 48.4% | 0.219 | 3 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/jonesdevelopment/sonar/complex) |
| 26 | `out/jonesdevelopment/sonar/legacy` | 500 | 45.8% | 0.255 | 3 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/jonesdevelopment/sonar/legacy) |
| 27 | `out/InstantlyMoist/Captcha/textcaptcha` | 500 | 10.8% | 0.598 | 5 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/InstantlyMoist/Captcha/textcaptcha) |
| 28 | `out/laforetbrut/are-you-sure/code` | 500 | 1.8% | 0.681 | 12 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/laforetbrut/are-you-sure/code) |
| 29 | `out_ru/GalleryCaptcha/ru-symbols` | 500 | 0.8% | 0.902 | 3 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/GalleryCaptcha/ru-symbols) |
| 30 | `out_ru/LimboFilter/symbols` | 500 | 0.4% | 0.905 | 3 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/LimboFilter/symbols) |
| 31 | `out/Archy-X/Krypton/menu` | 500 | 0.0% | 0.999 | 1 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/Archy-X/Krypton/menu) |
| 32 | `out/China2B2T/Captcha/wool` | 500 | 0.0% | 1.000 | 1 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/China2B2T/Captcha/wool) |
| 33 | `out/FeelingAlive0/AdvancedCaptcha/button` | 500 | 0.0% | 0.605 | 25 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/FeelingAlive0/AdvancedCaptcha/button) |
| 34 | `out/LagBug/XProtect/code` | 500 | 0.0% | 0.990 | 0 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/code) |
| 35 | `out/LagBug/XProtect/color` | 500 | 0.0% | 1.000 | 0 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/color) |
| 36 | `out/LagBug/XProtect/different` | 500 | 0.0% | 1.000 | 0 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/different) |
| 37 | `out/LagBug/XProtect/map` | 500 | 0.0% | 0.992 | 0 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/map) |
| 38 | `out/LagBug/XProtect/picture` | 500 | 0.0% | 1.000 | 0 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/picture) |
| 39 | `out/jSdCool/minecaptcha/image` | 500 | 0.0% | 0.554 | 25 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/jSdCool/minecaptcha/image) |
| 40 | `out_ru/CaptchaGUI/clickblock` | 500 | 0.0% | 6.274 | 6 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/CaptchaGUI/clickblock) |
| 41 | `out_ru/GalleryCaptcha/ru-numberword` | 500 | 0.0% | 1.000 | 9 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/GalleryCaptcha/ru-numberword) |
| 42 | `out_ru/GalleryCaptcha/ru-numberword-caption` | 500 | 0.0% | 1.000 | 9 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/GalleryCaptcha/ru-numberword-caption) |
| 43 | `out_ru/GalleryCaptcha/ru-object-swatch` | 500 | 0.0% | 1.000 | 1 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/GalleryCaptcha/ru-object-swatch) |
| 44 | `out_ru/LimboFilter/framed2x2` | 500 | 0.0% | 1.000 | 1 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/LimboFilter/framed2x2) |
| 45 | `out_ru/LimboFilter/framed3x3` | 500 | 0.0% | 1.000 | 2 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/LimboFilter/framed3x3) |
| 46 | `out_ru/LimboFilter/map` | 500 | 0.0% | 1.000 | 7 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/LimboFilter/map) |

### Что модель решает хорошо (измерено, не выдумано)

- `out_ru/CaptchaVerifyZ/map` — 0.998, `out/FeelingAlive0/AdvancedCaptcha/math` — 0.998,
  `out/jSdCool/minecaptcha/text` — 0.986, `out_ru/GalleryCaptcha/ru-web` — 0.946,
  `out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` — 0.956, `out/Archy-X/Krypton/map` — 0.908.
- Хуже всего: все кириллические типы (0.000–0.008) и `out/laforetbrut/are-you-sure/code` — 0.018
  (шесть символов, разноцветный фон, модель выдаёт мусор вида `iigp`).

---

## 2. Локальная галерея — `reports/HTML/index.html`

Полностью переделана в стиле **Kinpaku** (`impeccable.style`): бумага `#F8F8F8`, чернила `#070707`,
золото `#FFBA00`, патина `#0FB6AC`, вермильон `#B23B1D`, волосяные линии 1px / 8 % чёрного,
радиусы 3px, почти без теней, `cubic-bezier(.2,.8,.2,1)`. Шрифты — токены спецификации
(`reports/GALLERY_OPTIONS.md` §2).

**Шрифты — честно:** Albert Sans и Alumni Sans на этой машине **не установлены** (проверено
`C:\Windows\Fonts`: их там нет), а интернет-шрифты качать нельзя. Взяты ближайшие установленные:
**Segoe UI** (интерфейс), **Bahnschrift Light** (крупные заголовки, ближе всего к Alumni Sans),
**Cascadia Mono / Consolas** (цифры и идентификаторы, вместо JetBrains Mono). Это же написано в
галерее, в блоке «Честные оговорки».

Что на странице:

1. шапка с четырьмя цифрами (46 типов, 23 000 картинок, micro exact, median exact);
2. **«Скорее таблица»** — 46 строк: тип · группа · n · exact % · CER · медианная длина ответа ·
   ссылка «все 500 →» на папку типа на HF;
3. **«Галерея по типам»** — 46 блоков, по **6 отдельных миниатюр** на тип (не плоский лист),
   каждая подписана: имя файла, «написано:» (эталон) и «модель:» (ответ модели, зелёный — точное
   совпадение, красный — ошибка); в шапке блока — строка скорее-таблицы этого типа и ссылка
   «все 500 →». **Каждая миниатюра — кнопка:** клик (или `Enter`/`Space`) открывает **лайтбок** —
   картинка крупно, тип, «написано», «модель», уверенность, ссылка на папку типа на HF;
   `Esc` или клик по фону закрывают, `←`/`→` листают образцы текущего типа, `↑`/`↓` (или
   `PgUp`/`PgDn`) — соседние типы, `Home`/`End` — первый/последний образец. Лайтбок — часть
   самой страницы (свой `<script>`, без CDN и без новых файлов), всё в токенах Kinpaku: плоская
   подложка, волосяные линии, фокус-кольцо `patina-deep`, без тяжёлых теней;
4. **«Модели»** — 12 чужих моделей + наши две (с пометкой, что «наши» измерены другим протоколом);
5. **«Как это повторить»** — команды и честные оговорки.

Сборка полностью воспроизводима из измеренных файлов, ни одно число не вписано руками:

```powershell
.venv-gpu\Scripts\python.exe reports\HTML\make_scoreboard.py          # замер 46 типов
.venv-gpu\Scripts\python.exe reports\HTML\make_scoreboard.py --examples-pass  # ответы для 276 картинок галереи
.venv-gpu\Scripts\python.exe reports\HTML\make_report.py               # 3 контактных листа + types.json
.venv-gpu\Scripts\python.exe reports\HTML\make_gallery.py              # index.html + 276 миниатюр
```

`reports/HTML/make_report.py` сохранён: он по-прежнему делает три контактных листа, **и теперь
подписывает под каждой картинкой ответ модели** (зелёный — точный, красный — ошибка). Guard на
`real_shots` остался и работает: `make_report.py` и `make_gallery.py` отказываются копировать или
встраивать путь, в котором есть `real_shots`.

---

## 3. Карточка датасета на Hugging Face

Репозиторий: **`Titlehhhh/captchaocr-dataset`** (датасет). Репозиторий модели
`Titlehhhh/captchaocr-ppocrv6` **не трогали** — им занят другой агент.

| | |
|---|---|
| Коммит до | `6248c5b9b6ce7eb6e917efd7aa3952892beb7cea` (README 24 973 б) |
| Коммит после | `13765ca719897445c8d6c58a44f73b7adefba1ac` (README 37 509 б) |
| Что добавлено | `gallery/sheet_01.png` (1 128 229 б), `gallery/sheet_02.png` (1 198 054 б), `gallery/sheet_03.png` (1 108 830 б) + блок «Gallery» в README |
| Что не тронуто | YAML-фронтматтер с лицензией, весь прежний текст карточки, заявления про 46 × 500 = 23 000 PNG, пересборку 2026-10-22 на Java 21, «датасет — машинный артефакт», «real_shots не публикуются», разбивку лицензий по плагинам |

Новый блок отмечен маркерами `<!-- captchaocr-gallery:begin -->` / `<!-- captchaocr-gallery:end -->`:
при повторном запуске скрипта он **заменяется**, а не дописывается — карточку можно пересобирать
сколько угодно раз. Если маркеров нет (первый запуск) — блок дописывается в конец.

Внутри блока: три листа (markdown), **таблица на 46 строк** (тип · n · exact % · CER · ссылка
«все 500» на папку типа в `data/<out|out_ru>/<плагин>/<тип>`) и **таблица моделей**.

### Скрипт публикации — `tools/publish_gallery.py`

```powershell
.venv-gpu\Scripts\python.exe tools\publish_gallery.py --dry-run   # печатает план, ничего не грузит
.venv-gpu\Scripts\python.exe tools\publish_gallery.py             # грузит листы и обновляет карточку
.venv-gpu\Scripts\python.exe tools\publish_gallery.py --verify    # перечитывает карточку с хаба и проверяет
```

---

## 4. Что проверено (команды и вывод)

**Замер (46 типов):**

```
$ .venv-gpu\Scripts\python.exe reports\HTML\make_scoreboard.py
device: cuda   torch 2.14.1+cu126
types found: 46
evaluation items: 23000
model: ...\train\run_ppocr\big\export_soup  soup_alpha=0.4  classes=18710
decoded 23000 images in 172s   decode mismatches: 0
wrote ...\reports\model_scoreboard.json
all 46 : {"types": 46, "items": 23000, "exact_match_median": 0.651, "cer_median": 0.1173,
          "exact_match_micro": 0.502, "cer_micro": 0.5322}
held-out: {"types": 7, "items": 3500, "exact_match_median": 0.638, "cer_median": 0.1503,
            "exact_match_micro": 0.6123, "cer_micro": 0.2004}
published: {"median_exact": 0.638, "micro_exact": 0.6123, "median_cer": 0.1503,
            "micro_cer": 0.2004, "types": 7, "images": 3500}
```

**Карточка на HF:**

```
$ .venv-gpu\Scripts\python.exe tools\publish_gallery.py --verify
card: ...\hub\datasets--Titlehhhh--captchaocr-dataset\snapshots\13765ca7...\README.md
  gallery/sheet references : 3
  scoreboard rows (n=500 + a link to the folder) : 46
  every '| 500 |' in the card (the old inventory table included) : 125
  gallery/sheet_01.png: OK (1128229 bytes)
  gallery/sheet_02.png: OK (1198054 bytes)
  gallery/sheet_03.png: OK (1108830 bytes)
VERIFY: OK
```

**Страница в браузере:** отрендерена headless Edge **с отдельным профилем**
(`--user-data-dir="$env:TEMP\edge-gallery"`), скриншот 1400×4400: шапка, таблица 46 строк и блоки
галереи с миниатюрами, подписями «написано / модель» и ссылками «все 500 →» — всё на месте,
страница читается. После этого страница открыта в обычном браузере владельца
(`Start-Process reports\HTML\index.html`).

**Страница на HF:** карточка перечитана с хаба (`hf_hub_download`), три листа скачиваются
(`hf_hub_download` → 1.13 / 1.20 / 1.11 МБ), в карточке ровно 46 строк скорее-таблицы.

---

## 5. Что НЕ проверено

- **Как карточка выглядит на самом huggingface.co** (рендер markdown, раскладку картинок, мобильный
  вид) — с хаба скачали README и файлы, но глазами на странице сайта не смотрели.
- **Ссылки «все 500 →» на самом сайте** — URL собран из проверенного дерева репозитория
  (`data/out/...`, `data/out_ru/...` подтверждены списком дерева: 23 140 файлов), но каждая из 46
  ссылок по HTTP не открывалась.
- **Шрифты Albert Sans / Alumni Sans** — их нет на машине, страница использует системные
  аналоги; на другой машине с установленными шрифтами страница будет выглядеть иначе.
- **Страница не проверялась в Firefox/Safari** — только Chromium (Edge).
- **`tools/publish_gallery.py` не проверялся на «пустом» репозитории** (без маркеров в карточке
  ветка «append» отработала один раз на первой заливке; повторный запуск — ветка «replace»).
- **Замеры 12 чужих моделей не перезапускались** — взяты из `reports/bench_models/*.json`
  (единый протокол, 20 картинок на тип). Таблица моделей считает micro по 29 типам с полосой
  тем же кодом, что и `reports/GALLERY_OPTIONS.md` §4.1 — числа совпали до последнего знака.

---

## 6. Что сломано / расхождения

- **Расхождение с заданием по счёту строк.** Команда из ТЗ
  `t.count('| 500 |')` даёт **125**, а не 46: в старой карточке уже есть таблица-инвентарь, где у
  каждого типа в столбце n стоит 500. Поэтому `--verify` считает строки по более точному признаку
  (строка с `| 500 |` **и** ссылкой на папку типа) — их ровно 46. Строка карточки не переписывалась.
- **Шрифты.** Как описано выше: Albert Sans / Alumni Sans не установлены, использованы Segoe UI /
  Bahnschrift / Cascadia Mono. Скачивать шрифты из интернета нельзя.
- **Промежуточная ошибка (исправлена).** Первая заливка была прервана пайпом PowerShell
  (`Select-Object -First 20` закрывает stdout → python получает broken pipe); карточка при этом
  записалась один раз, маркеры в ней ровно один, дублей нет — проверено.
- **Пустой stdout у скриптов.** `python tools\publish_gallery.py` возвращает код 1, если его
  вывод перенаправлять в PowerShell-пайп с `2>&1` (PowerShell считает stderr-строку прогресса
  `huggingface_hub` ошибкой). На результат это не влияет, код возврата в чистом запуске — 0.
- **Кэш HF.** `huggingface_hub` ругается, что на этой машине нет символьных ссылок (нужен
  Developer Mode) — файлы кэшируются копиями, работает.

---

## 7. Файлы

**Созданы:**

| файл | что |
|---|---|
| `reports/model_scoreboard.json` | замер опубликованной модели по всем 46 типам (n, exact, CER, длины ответов, 6 примеров «эталон → ответ») |
| `reports/GALLERY_BUILT.md` | этот отчёт |
| `reports/HTML/make_scoreboard.py` | скрипт замера (импортирует пайплайн из `train/`) |
| `reports/HTML/make_gallery.py` | сборка страницы и миниатюр из измеренных файлов |
| `reports/HTML/img/t/**` | 276 миниатюр (46 папок × 6 картинок) |
| `tools/publish_gallery.py` | загрузка листов и обновление карточки HF (`--dry-run`, `--verify`) |

**Изменены:** `reports/HTML/make_report.py` (подпись «модель: …» на листах; guard `real_shots`
сохранён), `reports/HTML/index.html` (пересобрана), `reports/HTML/img/sheet_01..03.png`
(перерисованы), `reports/HTML/img/types.json`, `reports/HTML/img/types_table.html`.

**На Hugging Face:** `Titlehhhh/captchaocr-dataset` — три листа в `gallery/` и блок «Gallery» в
`README.md` (коммит `13765ca7…`). Репозиторий модели не тронут.

**Не тронуто (чужое):** `dataset/**`, `train/**`, `bench/**`, `reports/**` кроме перечисленного,
`webapp/**`, `agents/**`, `docs/**`, `AGENTS.md`, `HANDOVER.md`, `.env`, `.hf-cache/**`, `build/**`.
