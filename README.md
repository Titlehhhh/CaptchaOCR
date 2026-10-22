# CaptchaOCR — модель для распознования и датасет Minecraft-антибот каптч 

**Открытый датасет из 46 типов капч (4600 размеченных картинок) плюс измерения OCR-моделей на нём.**
Лабораторная работа по машинному зрению: Java 21 (генераторы) и Python (модели).

В Minecraft плагины-антиботы показывают игроку картинку с кодом и просят ввести этот код в чат,
чтобы отсечь ботов. Такие картинки называют **капчами** (captcha); открытых Minecraft-плагинов,
которые их рисуют, десятки, и каждый рисует по-своему: свой шрифт, размер холста, линии-помехи,
свои ошибки. Готовые модели распознавания текста на них работают плохо — это замерено здесь.

На Java 21 написаны генераторы, которые заново отрисовывают капчи тех же открытых плагинов —
пиксель в пиксель, с теми же шрифтами, искажениями и даже **ошибками** оригинала. Каждый тип
снабжён разметкой: что нарисовано, что игрок должен ввести, где лежит полоса с ответом.

## Как выглядят эти капчи

Фрагменты из датасета — по одному примеру на стиль. Подпись под картинкой: **тип**, размер холста,
описание и **золотой ответ** из `labels.jsonl` — то, что игрок должен ввести.

| | | |
|---|---|---|
| ![Пример 1](dataset/samples/haq/mapcha/map/001.png) | ![Пример 2](dataset/samples/LagBug/XProtect/code/001.png) | ![Пример 3](dataset/samples/LimboFilter/symbols/001.png) |
| `haq/mapcha/map` — 128×128, карта Minecraft, латинский код из 4 символов · ответ `s8TO` | `LagBug/XProtect/code` — 130×130, белый фон, чёрные помехи, латиница · ответ `EzhYNY` | `LimboFilter/symbols` — 128×128, тёмный фон, кириллица, 3 символа · ответ `ЪМИ` |
| ![Пример 4](dataset/samples/GalleryCaptcha/ru-web/001.png) | ![Пример 5](dataset/samples/LimboFilter/framed2x2/001.png) | ![Пример 6](dataset/samples/LagBug/XProtect/gui/001.png) |
| `GalleryCaptcha/ru-web` — 150×90, «веб-капча»: белый фон, тонкие линии · ответ `DpZ7D` | `LimboFilter/framed2x2` — 256×256, пазл-рамка 2×2, число записано словами · ответ `638` | `LagBug/XProtect/gui` — 380×260, GUI-сцена: чат и инвентарь · ответ `Glowstone` |
| ![Пример 7](dataset/samples/FeelingAlive0/AdvancedCaptcha/button/001.png) | ![Пример 8](dataset/samples/n1zamu/NCaptcha/anvil/001.png) | ![Пример 9](dataset/samples/GalleryCaptcha/ru-numberword/001.png) |
| `FeelingAlive0/AdvancedCaptcha/button` — 730×84, чат-сцена с кнопками · ответ `[ClickThat] in white color` | `n1zamu/NCaptcha/anvil` — 420×150, GUI наковальни, цифры · ответ `28612` | `GalleryCaptcha/ru-numberword` — 250×150, кириллица, число записано числительными · ответ `825` |

Полная витрина — по 5 картинок на каждый из 46 типов — в
[`dataset/samples/index.html`](dataset/samples/index.html).

---

## Что внутри

| | |
|---|---|
| Типов капчи | **46** — 34 в `dataset/out/`, 12 в `dataset/out_ru/` |
| Размеченных PNG | **4600** — ровно по 100 на тип, ~43.6 МБ |
| Плагинов-источников | **23** открытых Minecraft-плагина |
| В этом репозитории | генераторы (Java), чекеры меток, обучение и измерения |
| Полный датасет | на Hugging Face (ссылка ниже) |

## Ссылки

* **Датасет** — <https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset> — опубликован
  22 октября 2026: 4600 размеченных PNG (43.6 МБ) и `labels.jsonl` на каждый тип.
* **Репозиторий модели** — <https://huggingface.co/Titlehhhh/captchaocr-ppocrv6> — создан
  22 октября 2026: карточка с измеренными метриками; **весов модели пока нет**.

## Как попробовать

```powershell
pip install huggingface_hub
python tools\fetch_dataset.py
```

Посмотреть все 46 типов без установки чего-либо:
[`dataset/samples/index.html`](dataset/samples/index.html). Добавить свой тип капчи — это один
Java-файл в `dataset/generator/dev/captcha/gens/`; правила — в
[`dataset/generator/AGENTS.md`](dataset/generator/AGENTS.md) и в
[`docs/ONBOARDING.md`](docs/ONBOARDING.md).

## Что измерено

Готовые модели на тех же данных (46 типов × 20 картинок, единый протокол): лучшая,
`PP-OCRv6_medium_rec`, даёт **0.404** exact match по полосе с ответом и **0.078** по всему кадру.
На 29 типах, у которых полоса есть, — **0.552** против **0.035**, то есть в **16 раз** хуже на
кадре: решает кроппер, а не модель. Наша CRNN, обученная с нуля, даёт **1.000** на знакомых типах
и **0.000** на невиданных — запоминает, а не обобщает. Подробности — в `reports/`.

<details>
<summary>Сводка по 23 плагинам-источникам: лицензия и режим</summary>

| Лицензия | Плагины | Режим |
|---|---|---|
| MIT (11) | `LagBug/XProtect`, `FeelingAlive0/AdvancedCaptcha`, `Z4OLLIEZ4/reCaptcha`, `Joey61021/captcha`, `laforetbrut/are-you-sure`, `Mrbysco/Captcha`, `InstantlyMoist/Captcha`, `JSH32/Minecaptcha`, `haq/mapcha`, `just-captcha/ProstoCaptcha`, `n1zamu/NCaptcha` | faithful |
| GPL-3.0 (3) | `jonesdevelopment/sonar`, `China2B2T/Captcha`, `irootdev/AnBot` | clean-room |
| AGPL-3.0 (1) | `Elytrium/LimboFilter` | clean-room |
| CC0-1.0 (1) | `jSdCool/minecaptcha` | faithful |
| BSD с оговоркой (1) | `BotFilter` | clean-room |
| не указана (2) | `CaptchaGUI`, `CaptchaVerifyZ` | clean-room |
| лицензии нет (4) | `Archy-X/Krypton`, `Yukun99/Captchas`, `ringoame196-s-mcPlugin/ReproductionCAPTCHA` (файла лицензии нет) | clean-room |
| — (1 группа) | `GalleryCaptcha/*` | reconstructed |

Построчная таблица с платформой, ссылками и типами — в
[`docs/PLUGINS.md`](docs/PLUGINS.md); лицензии и что покрыто MIT — в
[`docs/LICENSES.md`](docs/LICENSES.md).

</details>

## Куда смотреть

| Хочу | Файл |
|---|---|
| Скачать датасет и разобраться, что внутри | [`docs/DATASET.md`](docs/DATASET.md) |
| Пройти маршрут с нуля: посмотреть → обучить → добавить тип → проверить метки | [`docs/ONBOARDING.md`](docs/ONBOARDING.md) |
| Плагины, лицензии, режимы реконструкции | [`docs/PLUGINS.md`](docs/PLUGINS.md) · [`docs/LICENSES.md`](docs/LICENSES.md) |
| Дефекты апстрима: почему их воспроизводят, а не чинят | [`docs/UPSTREAM_DEFECTS.md`](docs/UPSTREAM_DEFECTS.md) |
| Контракт `labels.jsonl` и правило полосы | [`docs/DATASET_FORMAT.md`](docs/DATASET_FORMAT.md) |
| Обучение модели | [`train/README.md`](train/README.md) |
| Измерения: JSON-протоколы и их разбор | [`reports/`](reports/) |

Статьи: CRNN — [arXiv:1507.05717](https://arxiv.org/abs/1507.05717) · PP-OCRv6 —
[arXiv:2606.13108](https://arxiv.org/abs/2606.13108) · SVTRv2 —
[arXiv:2411.15858](https://arxiv.org/abs/2411.15858)

Код репозитория — MIT ([`LICENSE`](LICENSE)); картинки подчиняются лицензиям соответствующих
плагинов-источников ([`docs/LICENSES.md`](docs/LICENSES.md)).
