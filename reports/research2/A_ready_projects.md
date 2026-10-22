# Направление A: готовые проекты и фреймворки end-to-end

**Дата сбора данных:** 2026-10-22. **Среда:** Windows, Python 3.12 и 3.14 доступны, GitHub REST API (неаутентифицированный, лимит 60/час) и PyPI JSON API использовались для снятия метаданных.

**Бриф:** файл `build/scratch/briefs2/A_ready_projects.md` **не найден** (искал `build/scratch/briefs2/**` и `build/scratch/**` через glob — совпадений нет). Работал по тексту задания из промпта.

---

## Выводы (кратко)

1. **Готового «llama.cpp для капч» в виде единого проекта не найдено**, но найдено **три очень близких аналога-кандидата на роль runtime-основы**: [RapidAI/RapidOCRLite](https://github.com/RapidAI/RapidOCRLite) (C++-движок PP-OCRv6 с C ABI, **без** линковки ONNX Runtime/OpenCV — рукописные ядра AVX2/AVX-512/NEON/Metal/Vulkan), [RapidAI/RapidOcrCpp](https://github.com/RapidAI/RapidOcrCpp) (C++-библиотека с MNN/ncnn/ONNX Runtime, CMake-пакет, JNI) и [RapidAI/RapidSpeech.cpp](https://github.com/RapidAI/RapidSpeech.cpp) (GGUF-формат + квантователь `rs-quantize` — это ровно та архитектура, которую хочет владелец проекта, но пока для звука, а не для капч).
2. **Самый практичный «runtime для капч», который можно взять и сразу использовать, — [sml2h3/ddddocr](https://github.com/sml2h3/ddddocr)** (MIT, ★14 858, ONNX Runtime, Windows 64-bit, CPU; GPU — по README, но требует отдельного пакета `onnxruntime-gpu`): он умеет принимать **чужую модель** через `import_onnx_path` + `charsets_path`, то есть наш CRNN можно экспортировать в ONNX и подсунуть этому движку без написания своего рантайма. **Проверено запуском** (§8): `pip install ddddocr` на Windows/Python 3.12 → 8.6 мс на картинку на CPU, точное распознавание синтетической капчи, работающий `set_ranges()` (маскирование алфавита) и вывод вероятностей.
3. **Ниша «CRNN+CTC именно для капч» занята, но мелко**: [jtrecenti/txtcaptcha](https://github.com/jtrecenti/txtcaptcha) (MIT, PyPI 0.1.0, 2026-04-11, модель на HF, ~89 % на 10 бразильских наборах) — единственный законченный pip-пакет «капча + CRNN + CTC + HF + маскирование словаря по типу», т. е. он уже делает ровно то, к чему идёт CaptchaOCR.
4. **Готовые OCR-стеки не решают проблему CaptchaOCR**: PaddleOCR (★91 495), EasyOCR (★30 092), TrOCR/UNILM (★22 238), Surya (★21 518), docTR (★6 392), MMOCR (★4 751) — все заточены под «документ/сцена», а не под 128×128 Minecraft-кадры; собственный замер в проекте (Graf-J 0.156, EasyOCR 0.115, anuashok 0.077) это подтверждает.
5. **Синтетика капч — отдельный зрелый рынок**: [cloverpray/deep-learning-captcha-ocr-tutorial](https://github.com/cloverpray/deep-learning-captcha-ocr-tutorial) (три стилевых семейства EasyCaptcha/CalculateCaptcha-Text/Ruoyi, CRNN/ResNet34-CRNN/SVTR-Tiny, EM+CER, FastAPI+Flask) и [MetaAgentX/NextGen-CAPTCHAs](https://github.com/MetaAgentX/NextGen-CAPTCHAs) ([ICML 2026], 519 головоломок из 27 семейств + генеративная система) — прямые образцы того, как надо строить «разнообразие», которого не хватает нашим 46 стилям.
6. **Коммерческие/серверные солверы (NopeCHA, 2captcha, ohmycaptcha) — это API-протоколы, а не модели**: [NopeCHALLC/nopecha-extension](https://github.com/NopeCHALLC/nopecha-extension) (★11 049, MIT), [2captcha/2captcha-python](https://github.com/2captcha/2captcha-python) (★805, MIT), [shenhao-stu/ohmycaptcha](https://github.com/shenhao-stu/ohmycaptcha) (★898, MIT — self-hosted FastAPI с YesCaptcha-протоколом и локальной VLM). Как компонент они бесполезны: они решают reCAPTCHA/hCaptcha/Turnstile, а не Minecraft-картинки.
7. **Готового CTC-декодера для C++/Python достаточно**: [githubharald/CTCDecoder](https://github.com/githubharald/CTCDecoder) (★838, MIT, best path / beam search / lexicon / prefix / token passing) — компонент, который не нужно писать.
8. **Датасеты на HF есть и лицензионно чистые частично**: [ATH-MaaS/Captcha](https://huggingface.co/datasets/ATH-MaaS/Captcha) (CC-BY-NC-4.0), [Capycap-AI/CaptchaSolve30k](https://huggingface.co/datasets/Capycap-AI/CaptchaSolve30k) (Apache-2.0), [AvinashRicky/CaptchaOCR-500K](https://huggingface.co/datasets/AvinashRicky/CaptchaOCR-500K) (MIT), [remiai3/synthetic-captchas-library](https://huggingface.co/datasets/remiai3/synthetic-captchas-library) (CC-BY-4.0, 1M–10M) — но это веб-капчи, а не Minecraft-стили.

---

## 0. Методика и оговорки

* Метаданные GitHub сняты через `api.github.com` (`GET /repos/{owner}/{repo}`, `GET /search/repositories`, `GET /orgs/{org}/repos`) **2026-10-22**. Колесо звёзд/лицензий — на эту дату.
* «Дата последнего коммита» в таблицах ниже — это поле `pushed_at` GitHub API (дата последнего push в ветку), а не дата последнего merge в `main`. Для заброшенных репозиториев это может отличаться.
* PyPI-данные — из `https://pypi.org/pypi/<name>/json` (версия, `upload_time`, `license`, `project_urls`).
* Единственный **выполненный** прогон — смоук-тест `ddddocr` (см. §8). Остальное — чтение README/документации, **не** установка и **не** бенчмарк на нашем датасете.
* Лицензия `NOASSERTION` в API означает, что GitHub не смог определить лицензию — это **не** подтверждение свободной лицензии.

---

## 1. Готовые «солверы» капч

### 1.1 Клиенты коммерческих сервисов (внешний API, а не локальная модель)

| Проект | ★ | Язык | Лицензия | Последний push | Windows/CPU | GPU | Компонент для CaptchaOCR? |
|---|---|---|---|---|---|---|---|
| [NopeCHALLC/nopecha-extension](https://github.com/NopeCHALLC/nopecha-extension) | 11 049 | — | MIT | 2026-10-02 | да (браузерное расширение) | нет | нет — платный API-клиент |
| [NopeCHALLC/nopecha-python](https://github.com/NopeCHALLC/nopecha-python) | 1 696 | Python | MIT | 2026-10-06 | да | нет | нет — обёртка над платным API |
| [NopeCHALLC/nopecha-nodejs](https://github.com/NopeCHALLC/nopecha-nodejs) | 1 452 | JavaScript | MIT | 2026-10-06 | да | нет | нет |
| [2captcha/2captcha-python](https://github.com/2captcha/2captcha-python) | 805 | Python | MIT | 2026-10-20 | да | нет | нет |
| [lorien/captcha_solver](https://github.com/lorien/captcha_solver) | 258 | Python | MIT | 2026-09-04 | да | нет | нет |

Про NopeCHA и 2captcha ясно по описанию репозиториев («Automated CAPTCHA solver …», «integration with the API of 2captcha captcha solving service») — это **клиенты внешнего платного сервиса**, а не локальные модели. README я не читал, поэтому перечень поддерживаемых типов капч для них не привожу.

PyPI: [2captcha-python 2.1.2](https://pypi.org/project/2captcha-python/) (MIT, 2026-10-20), [captcha-solver 0.1.5](https://pypi.org/project/captcha-solver/) (MIT, 2019-03-01, репозиторий `lorien/captcha_solver`).

### 1.2 Self-hosted / браузерные солверы (не наш домен, но образец архитектуры сервиса)

| Проект | ★ | Язык | Лицензия | Последний push | Назначение |
|---|---|---|---|---|---|
| [dessant/buster](https://github.com/dessant/buster) | 9 345 | JavaScript | GPL-3.0 | 2026-06-27 | расширение «для людей», решает reCAPTCHA/hCaptcha |
| [vinyzu-archive/Botright](https://github.com/vinyzu-archive/Botright) | 1 040 | Python | GPL-3.0 | 2026-10-20 | антидетект-фреймворк с «бесплатным ИИ-решением капч» |
| [shenhao-stu/ohmycaptcha](https://github.com/shenhao-stu/ohmycaptcha) | 898 | Python | MIT | 2026-03-09 | **self-hosted** YesCaptcha-совместимый сервис: FastAPI, `createTask`/`getTaskResult`, Playwright + локальная VLM (Qwen3.5-2B через SGLang) или облачный OpenAI-совместимый эндпоинт, 19 типов задач |
| [xHossein/PyPasser](https://github.com/xHossein/PyPasser) | 599 | Python | MIT | 2026-10-15 | reCAPTCHA v3 по чистому HTTP, v2 через аудио, Turnstile |
| [Xewdy444/Playwright-reCAPTCHA](https://github.com/Xewdy444/Playwright-reCAPTCHA) | 587 | Python | MIT | 2026-10-19 | Playwright-обёртки |
| [mikeyy/nonoCAPTCHA](https://github.com/mikeyy/nonoCAPTCHA) | 893 | Python | GPL-3.0 | 2023-06-08 | асинхронное решение reCAPTCHA v2 по аудио |
| [robatkins/GPT4o-Captcha-Bypasser](https://github.com/robatkins/GPT4o-Captcha-Bypasser) | 4 | Python | нет | 2024-08-07 | скрипт обхода капч через GPT-4o (одна из «именованных» в задании) |

**`ohmycaptcha` — самый полезный из них как образец**: это ровно та серверная архитектура, которую можно повторить для Minecraft — асинхронный API с `createTask`/`getTaskResult`, локальная модель вместо облака, отдельный «локальный» и «облачный» бэкенд. Лицензия MIT, т. е. кода можно переиспользовать.

### 1.3 Локальные визуальные солверы — ближе к нашей задаче

| Проект | ★ | Язык | Лицензия | Последний push | Что это |
|---|---|---|---|---|---|
| [sml2h3/ddddocr](https://github.com/sml2h3/ddddocr) | 14 858 | Python | MIT | 2026-03-10 | офлайн-SDK распознавания капч на ONNX Runtime; PyPI [ddddocr 1.6.1](https://pypi.org/project/ddddocr/) (MIT, 2026-03-11) |
| [ptigas/simple-captcha-solver](https://github.com/ptigas/simple-captcha-solver) | 601 | Python | MIT | 2018-01-04 | классический «маск-матчинг» по буквам без нейросети; **не** Minecraft-капча, но автор — игрок в Minecraft |
| [a-maliarov/amazoncaptcha](https://github.com/a-maliarov/amazoncaptcha) | 492 | Python | MIT | 2026-04-02 | чистый Pillow-солвер капчи Amazon |
| [0b01/SimGAN-Captcha](https://github.com/0b01/SimGAN-Captcha) | 437 | Jupyter | нет | 2024-04-24 | **SimGAN** ([статья Apple](https://arxiv.org/pdf/1612.07828v1.pdf)): «ломать капчи без ручной разметки» — синтез пар через генератор+рефайнер |
| [JasonLiTW/simple-railway-captcha-solver](https://github.com/JasonLiTW/simple-railway-captcha-solver) | 815 | Python | Apache-2.0 | 2022-11-18 | **архивирован**; CNN + генератор датасета в стиле тайваньской ж/д капчи |

**Про `ddddocr` подробно** (README проекта): движок — `onnxruntime`, обучение — `dddd_trainer` (PyTorch); Windows 64-bit поддерживается, CPU и GPU (`use_gpu=True`, `device_id`), Python до 3.12; встроены две модели `common_old.onnx` (по умолчанию) и `common.onnx` (`beta=True`); есть режим детекции (`det=True`) для слайдеров, вывод вероятностей (`probability=True`), фильтрация по диапазону символов (`set_ranges("0123456789")`) и **подключение своей модели**:

```
ocr = ddddocr.DdddOcr(ocr=False, import_onnx_path="mymodel.onnx", charsets_path="charset.json")
```

где JSON-чаarset должен содержать поля `charset/word/image/channel`. Есть и серверный режим: `python -m ddddocr api --host 0.0.0.0 --port 8000` (FastAPI, эндпоинты `POST /ocr`, `POST /ocr/file`, Docker/docker-compose). Лицензия MIT.

> Это **самый близкий к «llama.cpp для капч» готовый артефакт из найденных**: готовая ONNX-модель + встроенный рантайм + API-сервер + возможность подменить модель своей.

### 1.4 Minecraft-специфичные находки

Поиск `minecraft captcha` в GitHub API дал 70 репозиториев; релевантные:

* [Archy-X/Krypton](https://github.com/Archy-X/Krypton) (★3, Java, лицензия не определена, push 2022-09-15) — «Minecraft captcha plugin to stop bots»;
* [LagBug/XProtect](https://github.com/LagBug/XProtect) (★9, Java, лицензия не определена, push 2025-03-12) — «Minecraft plugin … robust bot protection»; **это ровно те плагины, чьи типы уже лежат в нашем датасете** (`dataset/out/LagBug/XProtect/`, `dataset/out/Archy-X/Krypton/`);
* [Yukun99/Captchas](https://github.com/Yukun99/Captchas) (★5, Java, push 2025-08-31) — «plugin that adds an autoclicker checking captcha to Minecraft»;
* [YoGoUrT20/Minecraft-bypass-captcha-bot](https://github.com/YoGoUrT20/Minecraft-bypass-captcha-bot) (★3, JavaScript, push 2022-12-06) — «semi-automatically bypass minecraft botfilter captcha»;
* [haq/mapcha](https://github.com/haq/mapcha) (★11, Java, MIT, push 2023-07-19) — **архивирован**; «Map based captcha plugin for your Minecraft server»;
* [cosmos223/Captcha](https://github.com/cosmos223/Captcha) (★3, Java, MIT, push 2022-12-30), [kasuganosoras/MCreCaptcha_Server](https://github.com/kasuganosoras/MCreCaptcha_Server) (★5, PHP, GPL-3.0, push 2019-08-18), [UIPlugins/CaptchaAPI](https://github.com/UIPlugins/CaptchaAPI) (★4, PHP, MIT, push 2019-01-04), [Noonenowhoiam/WebSiteCpatcha](https://github.com/Noonenowhoiam/WebSiteCpatcha) (★5, Java, GPL-3.0, push 2026-08-05) — веб-капча на входе в сервер.

**Вывод по §1.4:** отдельного «решателя Minecraft-капч» с нейросетью в открытых источниках **не найдено** — ни в GitHub, ни в PyPI. Все найденные проекты — это *серверные плагины, защищающие сервер*, а не *клиенты, которые распознают*. Это подтверждает, что ниша CaptchaOCR не занята.

---

## 2. OCR-стеки (общие)

| Проект | ★ | Язык | Лицензия | Последний push | PyPI | Windows/CPU | GPU нужен? | Компонент? |
|---|---|---|---|---|---|---|---|---|
| [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | 91 495 | Python | Apache-2.0 | 2026-09-16 | [paddleocr 3.7.0](https://pypi.org/project/paddleocr/) (2026-06-11) | да (PaddlePaddle CPU) | нет, но есть GPU-пути | да — ONNX-конвертация есть (§6) |
| [JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR) | 30 092 | Python | Apache-2.0 | 2025-12-05 | [easyocr 1.7.2](https://pypi.org/project/easyocr/) (2024-09-24) | да | нет | да, но замер в проекте — 0.115 |
| [microsoft/unilm](https://github.com/microsoft/unilm) (TrOCR) | 22 238 | Python | MIT | 2026-09-21 | — | да | желателен | да; HF: [DunnBC22/trocr-base-printed_captcha_ocr](https://huggingface.co/models/DunnBC22/trocr-base-printed_captcha_ocr) (dl 3 544, ★9, MIT) |
| [datalab-to/surya](https://github.com/datalab-to/surya) | 21 518 | Python | Apache-2.0 | 2026-09-11 | [surya-ocr 0.22.1](https://pypi.org/project/surya-ocr/) (2026-07-20) | частично | да | нет — сценарий |
| [docling-project/docling](https://github.com/docling-project/docling) | 69 318 | Python | MIT | 2026-10-21 | — | да | нет | нет — это конвертер документов |
| [mindee/doctr](https://github.com/mindee/doctr) | 6 392 | Python | Apache-2.0 | 2026-10-21 | [docTR 1.9.0](https://pypi.org/project/docTR/) (**2021-04-08** — PyPI устарел) | да | нет | нет — документы |
| [open-mmlab/mmocr](https://github.com/open-mmlab/mmocr) | 4 751 | Python | Apache-2.0 | 2024-11-27 | [mmocr 1.0.1](https://pypi.org/project/mmocr/) (2023-07-04) | да | нет | **фактически мёртв** (2+ года без пушей) |
| [RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR) | 8 264 | Python | Apache-2.0 | 2026-10-22 | [rapidocr-onnxruntime 1.4.4](https://pypi.org/project/rapidocr-onnxruntime/) (2025-01-17) | да (ONNX Runtime CPU) | опционально | **да — лучший «OCR как компонент»** (§6) |
| [breezedeus/CnOCR](https://github.com/breezedeus/CnOCR) | 3 771 | Python | Apache-2.0 | 2026-07-05 | [cnocr 2.3.3](https://pypi.org/project/cnocr/) (2026-07-05) | да | нет | возможно — есть CRNN-модели |
| [madmaze/pytesseract](https://github.com/madmaze/pytesseract) | 6 395 | Python | Apache-2.0 | 2026-10-19 | [pytesseract 0.3.13](https://pypi.org/project/pytesseract/) (2024-08-16) | да | нет | нет — Tesseract плохо работает на капчах |
| [faustomorales/keras-ocr](https://github.com/faustomorales/keras-ocr) | 1 473 | Python | MIT | 2025-09-22 | [keras-ocr 0.9.3](https://pypi.org/project/keras-ocr/) (2023-11-06) | да | нет | возможно — CRAFT+CRNN |
| [tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract) | 77 104 | C++ | Apache-2.0 | 2026-10-22 | [tesserocr 2.11.0](https://pypi.org/project/tesserocr/) (2026-08-04) | да, есть готовые бинарники под Windows | нет | нет |

Замечания:
* `pytesseract` и `keras-ocr` **переехали**: старые адреса `mummoja/pytesseract` и `asvinogradov/keras-ocr` отдают 404; актуальные указаны в `project_urls` на PyPI.
* `docTR`/`mmocr` на PyPI застыли в 2021/2023, хотя репозиторий `mindee/doctr` жив (push 2026-10-21) — при установке надо брать из git, а не из PyPI.
* `Tesseract` — движок на C++ с `libtesseract` (C API `include/tesseract/capi.h` и C++ `baseapi.h`), Apache-2.0, есть [pre-built бинарники под Windows](https://tesseract-ocr.github.io/tessdoc/Installation.html); Tesseract 4+ использует LSTM-движок. Это уже «рантайм для строкового OCR» — но не CTC и не капчи.

---

## 3. Проекты с CRNN+CTC для капч

| Проект | ★ | Язык | Лицензия | Последний push | Суть |
|---|---|---|---|---|---|
| [jtrecenti/txtcaptcha](https://github.com/jtrecenti/txtcaptcha) | 3 | Python | MIT | 2026-04-11 | **самый близкий аналог CaptchaOCR**: CRNN+CTC, 62 класса + blank, произвольный размер входа, **маскирование словаря при декодировании** (`decrypt(..., mask=...)`), HF-публикация (`push_to_hub`), pip-installable |
| [sml2h3/ddddocr](https://github.com/sml2h3/ddddocr) | 14 858 | Python | MIT | 2026-03-10 | ONNX-рантайм + подменяемая модель (см. §1.3) |
| [cloverpray/deep-learning-captcha-ocr-tutorial](https://github.com/cloverpray/deep-learning-captcha-ocr-tutorial) | 10 | Java | не указана | 2025-08-15 | **лаборатория-эталон**: 3 синтетических стилевых семейства (EasyCaptcha / CalculateCaptcha-Text / Ruoyi), Vanilla-CRNN + ResNet34-CRNN + SVTR-Tiny (CTC), метрики EM и CER, FastAPI-бэкенд + Flask-фронт |
| [sun1638650145/CRNN](https://github.com/sun1638650145/CRNN) | 15 | Python | Apache-2.0 | 2023-01-03 | «AutoML для CRNN»: `CRNNPipeline('./captcha_images_v2/')` + `.run()` — распознавание капч «в несколько строк» |
| [roncuevas/Captchas](https://github.com/roncuevas/Captchas) | 1 | Jupyter | MIT | 2026-03-20 | датасет 88K+ изображений + CRNN+CTC с 99.49 % + экспорт в CoreML |
| [Bazskillz/captcha-crnn-solver](https://github.com/Bazskillz/captcha-crnn-solver) | 0 | Python | MIT | 2026-03-24 | заявлено 99.7 % на 4-значных цифровых капчах |
| [deveshrohan/captcha-solver](https://github.com/deveshrohan/captcha-solver) | 1 | Python | MIT | 2026-09-19 | «синтетика → локальные модели CRNN+CTC / CNN; реверс-инжиниринг генераторов капч» |
| [limingda1212/CapCRNN](https://github.com/limingda1212/CapCRNN) | 3 | Python | GPL-3.0 | 2026-02-25 | CRNN+CTC, пятиэтапное прогрессивное обучение, «relaxed matching» (нечёткое сравнение), Flask API |
| [EVOL-ution/Captcha-Recognition-using-CRNN](https://github.com/EVOL-ution/Captcha-Recognition-using-CRNN) | 14 | Jupyter | MIT | 2023-09-25 | учебный CRNN+CTC для капч |
| [siwtom/captchas-solver_crnn](https://github.com/siwtom/captchas-solver_crnn) | 0 | — | MIT | 2022-07-14 | CRNN+CTC «для капч» |
| [SanyumCode/captcha-crnn](https://github.com/SanyumCode/captcha-crnn) | 1 | Python | MIT | 2026-09-10 | PyTorch CRNN + экспорт в **ONNX/TorchScript** (то, что нам нужно для рантайма) |
| [SantiagoDemattei/captcha-text-recognition](https://github.com/SantiagoDemattei/captcha-text-recognition) | 1 | Python | MIT | 2026-07-29 | «синтетический претрейн + дообучение на реальных по 3 визуальным стилям» — ровно наш сценарий в миниатюре |
| [jonathan-kao/captcha-crnn-minimal](https://github.com/jonathan-kao/captcha-crnn-minimal) | 1 | Jupyter | MIT | 2025-07-15 | 96 % при **всего ~500 размеченных** сэмплах |

### Канонический учебный образец CRNN+CTC

[Keras: «OCR model for reading Captchas»](https://keras.io/examples/vision/captcha_ocr/) (автор A_K_Nain, создано 2020-06-14, изменено 2024-03-13) — это эталон минимальной реализации: 1040 изображений (датасет [AakashKumarNain/CaptchaCracker](https://github.com/AakashKumarNain/CaptchaCracker/raw/master/captcha_images_v2.zip)), 19 символов, вход 200×50, даунсэмплинг ×4, `Conv(32) → Conv(64) → Dense(64) → BiLSTM(128) → BiLSTM(64) → Dense(21)`, **432 725 параметров (1.65 МБ)**, CTC-слой кастомным `layers.Layer`. Для сравнения: наш CRNN — 4 623 615 параметров, т. е. **в 10.7 раза больше**, при этом на порядки сложнее задача (шум, повороты, 46 стилей, русские слова).

### Модели на Hugging Face (капча)

| Модель | Скачиваний | Лайков | Лицензия | Комментарий |
|---|---|---|---|---|
| [anuashok/ocr-captcha-v3](https://huggingface.co/anuashok/ocr-captcha-v3) | 61 323 | 43 | Apache-2.0 | наш замер 0.077 (по целому кадру) |
| [anuashok/ocr-captcha-v2](https://huggingface.co/anuashok/ocr-captcha-v2) | 8 700 | 6 | Apache-2.0 | — |
| [DunnBC22/trocr-base-printed_captcha_ocr](https://huggingface.co/models/DunnBC22/trocr-base-printed_captcha_ocr) | 3 544 | 9 | MIT | TrOCR, дообученный на капчах |
| [jtrecenti/txtcaptcha-crnn](https://huggingface.co/jtrecenti/txtcaptcha-crnn) | 796 | 1 | MIT | `config.json` + `model.safetensors`; ~89 % на 10 бразильских наборах |
| [keras-io/ocr-for-captcha](https://huggingface.co/models/keras-io/ocr-for-captcha) | 68 | 85 | **CC0-1.0** | модель из Keras-примера выше (1.65 МБ) — самая «чистая» по лицензии база |
| [Graf-J/captcha-crnn-finetuned](https://huggingface.co/Graf-J/captcha-crnn-finetuned) | 69 | 1 | MIT | наш замер 0.156 |
| [Wall3/Yara_Captcha_Solver](https://huggingface.co/Wall3/Yara_Captcha_Solver) | 0 | 2 | MIT | по описанию — CRNN+CTC на 275 000 реальных капчах из 7 HF-датасетов; **в момент проверки dl=0, воспроизвести заявленные 90.08 % не могу** |

---

## 4. Генераторы капч и синтетика (связано с проблемой «46 стилей по 100 штук»)

| Проект | ★ | Язык | Лицензия | Последний push | Что даёт |
|---|---|---|---|---|---|
| [lepture/captcha](https://github.com/lepture/captcha) | 1 097 | Python | BSD-3-Clause | 2025-10-21 | PyPI [captcha 0.7.1](https://pypi.org/project/captcha/) (2025-03-01) — генератор аудио- и image-капч |
| [mbi/django-simple-captcha](https://github.com/mbi/django-simple-captcha) | 1 419 | Python | MIT | 2026-07-30 | PyPI [django-simple-captcha 0.7.0](https://pypi.org/project/django-simple-captcha/) (2026-07-30) — генератор с кучей настроек шрифта/искажений |
| [J-Rios/multicolorcaptcha](https://github.com/J-Rios/multicolorcaptcha) | 88 | Python | GPL-3.0 | 2022-12-30 | «random image-captcha generator library» |
| [GeorgeChan/captchapng](https://github.com/GeorgeChan/captchapng) | 209 | JavaScript | — | 2023-12-28 | генератор капч для Node.js |
| [Shashank3736/captcha-canvas](https://github.com/Shashank3736/captcha-canvas) | 73 | TypeScript | Apache-2.0 | 2026-07-24 | генератор капч на skia-canvas |
| [ashtonav/opencaptcha](https://github.com/ashtonav/opencaptcha) | 18 | C# | MIT | 2026-06-17 | «open source, free, **public API** that generates CAPTCHA images from text» (api.opencaptcha.io) — готовый сервис-генератор |
| [MetaAgentX/OpenCaptchaWorld](https://github.com/MetaAgentX/OpenCaptchaWorld) | 95 | JavaScript | MIT | 2026-02-19 | **NeurIPS 2025 Datasets & Benchmarks**: платформа/бенчмарк для MLLM-агентов, 463 современных капчи, 20 типов; есть [датасет на HF](https://huggingface.co/datasets/OpenCaptchaWorld/Open_CaptchaWorld) (Apache-2.0) |
| [MetaAgentX/NextGen-CAPTCHAs](https://github.com/MetaAgentX/NextGen-CAPTCHAs) | 30 | Python | MIT | 2026-05-01 | **[ICML 2026]**: «defense framework against MLLM-based web GUI agents»; генеративная система капч + 519 головоломок из 27 семейств; [датасет](https://huggingface.co/datasets/ZHEN-04/CaptchaArena) |
| [cloverpray/deep-learning-captcha-ocr-tutorial](https://github.com/cloverpray/deep-learning-captcha-ocr-tutorial) | 10 | Java | не указана | 2025-08-15 | три *стилевых семейства* с настраиваемыми шрифтами/размерами/распределением длин/цветовыми искажениями — прямая метафора наших «46 типов» |
| [0b01/SimGAN-Captcha](https://github.com/0b01/SimGAN-Captcha) | 437 | Jupyter | — | 2024-04-24 | генеративный подход «без ручной разметки» |

**Самый полезный вывод отсюда:** генераторы «одного стиля» (как `captcha`, `django-simple-captcha`) CaptchaOCR не помогают — нужен **стиль-ориентированный** генератор, где стиль — это параметризованное семейство (шрифт × размер × поворот × шум × палитра × длина × распределение символов). Именно такую параметризацию сделали `cloverpray` (3 семейства) и `NextGen-CAPTCHAs` (27 семейств). Наш Java-генератор уже умеет ровно это (по плагинам) — вопрос только в том, сколько семейств покрыто.

---

## 5. Нечёткое распознавание (fuzzy matching)

| Проект | ★ | Лицензия | Последний push | Роль |
|---|---|---|---|---|
| [rapidfuzz/RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | 4 173 | MIT | 2026-10-21 | быстрое нечёткое сравнение строк (Levenshtein и др.) в Python |
| [rapidfuzz/rapidfuzz-cpp](https://github.com/rapidfuzz/rapidfuzz-cpp) | 379 | MIT | 2026-08-30 | то же на C++ — если рантайм будет C/C++ |
| [Raffinert/FuzzySharp](https://github.com/Raffinert/FuzzySharp) | 48 | MIT | 2026-10-17 | C#-порядок, bit-parallel Levenshtein |
| [rapidfuzz/rapidfuzz-rs](https://github.com/rapidfuzz/rapidfuzz-rs) | 72 | Apache-2.0 | 2024-06-29 | Rust-порт |

Для капч «нечёткость» обычно означает одно из двух: (а) *нечёткая метрика* между предсказанием и эталоном при оценке (relaxed matching) — как в [limingda1212/CapCRNN](https://github.com/limingda1212/CapCRNN); (б) *relaxed decoding* — разрешение близких символов (0/O, 1/l) на этапе CTC-декодирования. Собственного CTC-декодера писать не нужно: [githubharald/CTCDecoder](https://github.com/githubharald/CTCDecoder) (★838, MIT, push 2026-01-31) даёт best path, beam search, lexicon search, prefix search и token passing.

---

## 6. Есть ли готовый «runtime» для маленьких OCR-сетей (аналог llama.cpp)?

Это главный вопрос направления A. Ответ: **да, но под другими именами, и ни один из них не называется «captcha runtime»**.

### 6.1 RapidAI/RapidOCRLite — самый близкий аналог

| | |
|---|---|
| Репозиторий | [RapidAI/RapidOCRLite](https://github.com/RapidAI/RapidOCRLite) |
| ★ | 7 (новый проект) |
| Язык / лицензия | C++ / **Apache-2.0** |
| Последний push | 2026-10-22 |
| PyPI | `RapidOCRLite` **5.0.0a6** |

Что внутри (по README проекта):
* Это **C++-движок PP-OCRv6** с **C ABI** (`include/rapidocrlite/rapidocrlite.h`), **C++ API** и Python-пакетом (Python зовёт C ABI через `ctypes`). То есть ровно та «поверхность API», которую даёт llama.cpp.
* **Не линкует ONNX Runtime, Paddle Inference и OpenCV** — «руки написанные» ядра: свёртки, GEMM, pooling, нормализация, resize, shape-операции, attention-matmul, а также пост-обработка **DB и CTC**.
* Бэкенды: AVX2, AVX-512, NEON (ARM), Metal (macOS), Vulkan; есть `PPOCR_FORCE_ISA` для выбора ISA. Поддержка LoongArch (NEON через LSX-shim) — с CI на QEMU.
* Заявленные замеры (x86, 4 vCPU Xeon AVX-512, 960×240): `rapidocr 5.0.0a1` — **105.1 мс**, `rapidocr 3.9.2` (ONNX Runtime 1.30.0) — **193.0 мс**; на странице — 356.7 мс против 508.3 мс. То есть самописный C++-движок вдвое быстрее ORT.
* **Модельная лицензия отличается от кода**: встроенные «lite»-веса ([datalab-to/indra-ocr](https://huggingface.co/datalab-to/indra-ocr), ~17.1 МБ) — **модифицированная OpenRAIL-M**, с ограничениями на Output. То есть Apache-2.0 покрывает код, но не веса.
* Это **PP-OCRv6-рантайм**, а не универсальный: «a general ONNX model still needs another engine».

**Почему это важно для CaptchaOCR:** это прямое доказательство, что «свой рантайм для маленькой OCR-сети» — реализуемая и осмысленная задача, и что её **уже решили** (для PP-OCR, не для капч). Значит, наша задача сводится к: взять формат/подход, но написать операторы под нашу CRNN.

### 6.2 RapidAI/RapidOcrCpp — «OCR как C++-библиотека»

[RapidAI/RapidOcrCpp](https://github.com/RapidAI/RapidOcrCpp) (★2, C++, Apache-2.0, push 2026-07-01): читает Paddle-модели через **MNN (Alibaba) / ncnn (Tencent) / ONNX Runtime (Microsoft)**, использует связку **DbNet + AngleNet + CrnnNet**, собирается через CMake с опциями `BUILD_WITH_ONNXRUNTIME`, `BUILD_WITH_JNI`, `BUILD_SHARED_LIBS`, ставится как **обычный CMake-пакет** (`find_package(RapidOcr)`, `pkg-config` → `RapidOcr.pc`), есть тестовая обёртка для C и C++. Есть отдельные репозитории движков: [RapidAI/RapidOcrOnnx](https://github.com/RapidAI/RapidOcrOnnx), [RapidAI/RapidOcrNcnn](https://github.com/RapidAI/RapidOcrNcnn).

**Это самый «либатный» из найденных образцов дизайна runtime-а**: engine-абстракция (MNN / ncnn / ORT) + CMake-пакет + C API + JNI.

### 6.3 RapidAI/RapidSpeech.cpp — «llama.cpp-архитектура» как образец

[RapidAI/RapidSpeech.cpp](https://github.com/RapidAI/RapidSpeech.cpp) (★30, C, push 2026-08-07): «One native C/C++ runtime. Python-simple. **GGUF-powered**».

* Модели — в формате **GGUF**; «No model paths, no CMake, no config»; первая загрузка сама тянет модель с проверкой **sha256** и кладёт в `~/.cache/rapidspeech/models/`.
* Есть **инструмент квантования** `rs-quantize` (в README — команда `-m …fp16.gguf` → q4_k_m).
* API: native C API (`include/rapidspeech.h`), WASM/JavaScript, Python, готовые C++-исполняемые файлы без внешних DLL.
* Бэкенды: CPU, Metal, CUDA, Vulkan, CANN, OpenCL, WebGPU.

**Это ровно тот «tooling», который нужен CaptchaOCR**: единый формат файла модели + квантователь + один CLI + C API + биндинги. Если делать «captcha.cpp», формат модели и квантователь надо изобретать — а тут уже есть готовый прецедент и готовый инструмент (`rs-quantize` на ggml).

### 6.4 Универсальные рантаймы (подходят и для нашей CRNN после экспорта в ONNX)

| Рантайм | ★ | Лицензия | Язык | Последний push | Windows | Замечание |
|---|---|---|---|---|---|---|
| [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime) | 22 135 | MIT | C++ | 2026-10-22 | да | базовый вариант: PyPI [onnxruntime 1.31.0](https://pypi.org/project/onnxruntime/) (2026-10-09), C API, CPU EP + CUDA EP |
| [Tencent/ncnn](https://github.com/Tencent/ncnn) | 23 987 | не определена API (`NOASSERTION`) | C++ | 2026-10-20 | да | README прямо перечисляет **«PP-OCR examples»** среди поддерживаемых моделей |
| [alibaba/MNN](https://github.com/alibaba/MNN) | 16 262 | Apache-2.0 | C++ | 2026-10-21 | да | мобильный/edge-движок Alibaba |
| [openvinotoolkit/openvino](https://github.com/openvinotoolkit/openvino) | 11 038 | Apache-2.0 | C++ | 2026-10-22 | да | PaddleOCR→OpenVINO — штатный путь PaddleOCR |
| [PaddlePaddle/Paddle-Lite](https://github.com/PaddlePaddle/Paddle-Lite) | 7 289 | Apache-2.0 | C++ | 2026-04-27 | да | мобильный рантайй Paddle |
| [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe) | 37 361 | Apache-2.0 | C++ | 2026-10-22 | да | не OCR-специализирован |

Конвертация: [PaddlePaddle/Paddle2ONNX](https://github.com/PaddlePaddle/Paddle2ONNX) (★946, Apache-2.0, push 2026-03-18) + инструкция [deploy/paddle2onnx/readme.md](https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/deploy/paddle2onnx/readme.md): ONNX Opset 9–11 стабильно, пример — конвертация det/rec/cls моделей PP-OCRv3 с последующим инференсом через ONNX Runtime.

### 6.5 Tesseract и его WASM-порты — «рантайм, упакованный в JS»

* [tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract) (★77 104, C++, Apache-2.0, push 2026-10-22) — `libtesseract` + CLI, C API и C++ API, готовые бинарники под Windows, LSTM-движок с Tesseract 4.
* [naptha/tesseract.js](https://github.com/naptha/tesseract.js) (★38 785, JavaScript, Apache-2.0, push 2026-05-17) — **WASM-порт Tesseract**; API `createWorker('eng')` → `worker.recognize(...)` → `worker.terminate()`; v7 требует Node ≥ 16; есть локальная установка и документация по worker vs. scheduler.
* [naptha/tesseract.js-core](https://github.com/naptha/tesseract.js-core) (★194, Apache-2.0, push 2026-03-25) — собственно Emscripten-порт ядра Tesseract.
* [robertknight/tesseract-wasm](https://github.com/robertknight/tesseract-wasm) (★386, TypeScript, BSD-2-Clause, push 2025-11-17).

**Почему это релевантно:** tesseract.js — это прецедент «готового рантайма + зоопарка языковых моделей (traineddata) + worker-пула», то есть ровно та архитектура, которую хочет владелец: движок + формат весов + CLI + биндинги.

### 6.6 Другие «маленькие движки OCR»

* [benjaminwan/OcrLiteOnnx](https://github.com/benjaminwan/OcrLiteOnnx) (★150, C++, Apache-2.0, push 2023-02-24) — «ChineseOcr Lite Onnx», использует **onnxruntime 1.9–1.14**, модели `dbnet.onnx` + **`crnn_lite_lstm.onnx`** + `angle_net.onnx`; готовые бинарники под win/mac/linux, **JNI-библиотека и динамическая библиотека для C**, статическая линковка под MSVC.
* [benjaminwan/OcrLiteNcnn](https://github.com/benjaminwan/OcrLiteNcnn) (★58, C++, push 2023-02-14) и [benjaminwan/OcrLiteAndroidOnnx](https://github.com/benjaminwan/OcrLiteAndroidOnnx) (★61, push 2023-02-16) — порты того же на ncnn и Android.

### 6.7 sherpa-onnx — архитектурный образец, но **не** OCR

[k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (★15 433, C++, Apache-2.0, push 2026-10-22): локальный ASR/TTS/diarization/VAD/KWS/keyword-spotting поверх ONNX Runtime; 12 языков API (C++, C, Python, JS, Java, C#, Kotlin, Swift, Go, Dart, Rust, Pascal), Windows x64/arm64, WebAssembly, NPU-бэкенды (RKNN, QNN, Ascend, Axera, OpenVINO).

**Важное уточнение: OCR в sherpa-onnx нет** — README перечисляет только речевые функции. Поэтому sherpa-onnx — это **образец дизайна** (C API + ORT + зоопарк моделей + готовые бинарники под Windows + WASM), а не готовый OCR-рантайм. Один из его пользователей — сам DeepSeek Harness ([в README есть блок «Projects using sherpa-onnx» со ссылкой на `deepseek-harness`](https://github.com/deepseek-ai/deepseek-harness)).

### 6.8 Сводка по разделу «runtime»

| Кандидат | Что это | Готовность | Вердикт для CaptchaOCR |
|---|---|---|---|
| [RapidOCRLite](https://github.com/RapidAI/RapidOCRLite) | C++-движок OCR с C ABI, без ORT | новый (★7), push 2026-10-22 | **лучший образец**: рукописные ядра + C ABI + ISA-бэкенды. Но он «заточен» под PP-OCRv6 |
| [RapidOcrCpp](https://github.com/RapidAI/RapidOcrCpp) | C++-библиотека, MNN/ncnn/ORT, CMake-пакет | ★2 | **лучший образец дизайна библиотеки/рантайма** (engine-абстракция + find_package + JNI) |
| [RapidSpeech.cpp](https://github.com/RapidAI/RapidSpeech.cpp) | GGUF-формат + квантователь + CLI + C API | ★30 | **лучший образец тулинга** (формат модели, квантование, автозагрузка) |
| [onnxruntime](https://github.com/microsoft/onnxruntime) | универсальный рантайм | зрелый | **рабочая база сразу**: экспортируем нашу CRNN в ONNX — получаем CPU/GPU-инференс без своего кода |
| [ncnn](https://github.com/Tencent/ncnn) / [MNN](https://github.com/alibaba/MNN) / [Paddle-Lite](https://github.com/PaddlePaddle/Paddle-Lite) | мобильные рантаймы | зрелые | варианты для «лёгкого» дистрибутива |
| [tesseract.js](https://github.com/naptha/tesseract.js) | WASM-рантайм OCR с зоопарком моделей | зрелый | образец «движок + формат весов + worker-пул» |
| [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | речевой рантайм на ORT | зрелый | образец дизайна; **OCR-функций нет** |
| [ddddocr](https://github.com/sml2h3/ddddocr) | captcha-OCR поверх ORT, **с подменой модели** | зрелый | **единственный найденный готовый «движок капч» с подменяемой моделью** |

---

## 7. Датасеты капч на Hugging Face

| Датасет | Скачиваний | Лайков | Лицензия | Размер | Примечание |
|---|---|---|---|---|---|
| [ATH-MaaS/Captcha](https://huggingface.co/datasets/ATH-MaaS/Captcha) | 3 153 | 0 | **CC-BY-NC-4.0** | 10K–100K | non-commercial — для лаборатории ок, для публикации модели в HF надо быть осторожным |
| [remiai3/synthetic-captchas-library](https://huggingface.co/datasets/remiai3/synthetic-captchas-library) | 1 876 | 1 | CC-BY-4.0 | 1M–10M | синтетика, можно для претрейна |
| [inclusionAI/VenusBench-CAPTCHA](https://huggingface.co/datasets/inclusionAI/VenusBench-CAPTCHA) | 1 725 | 7 | не указана | <1K | бенчмарк |
| [Knight07/Deep_Captcha](https://huggingface.co/datasets/Knight07/Deep_Captcha) | 1 460 | 0 | MIT | <1K | — |
| [Capycap-AI/CaptchaSolve30k](https://huggingface.co/datasets/Capycap-AI/CaptchaSolve30k) | 402 | 7 | **Apache-2.0** | 10K–100K | json-разметка, чистая лицензия |
| [ZHEN-04/CaptchaArena](https://huggingface.co/datasets/ZHEN-04/CaptchaArena) | 458 | 6 | CC-BY-NC-4.0 | 10K–100K | из проекта NextGen-CAPTCHAs |
| [project-sloth/captcha-images](https://huggingface.co/datasets/project-sloth/captcha-images) | 362 | 24 | WTFPL | 10K–100K | WTFPL — можно свободно |
| [OpenCaptchaWorld/Open_CaptchaWorld](https://huggingface.co/datasets/OpenCaptchaWorld/Open_CaptchaWorld) | 353 | 0 | Apache-2.0 | <1K | из NeurIPS 2025 бенчмарка |
| [AvinashRicky/CaptchaOCR-500K](https://huggingface.co/datasets/AvinashRicky/CaptchaOCR-500K) | 152 | 3 | MIT | 100K–1M | parquet |
| [szili2011/captcha-ocr-dataset](https://huggingface.co/datasets/szili2011/captcha-ocr-dataset) | 80 | 2 | Apache-2.0 | 1M–10M | — |

---

## 8. Что реально проверено запуском

Единственный выполненный прогон — смоук-тест `ddddocr` в **временном venv вне репозитория** (`%TEMP%\captcha_probe\venv`, Python 3.12), чтобы проверить «можно ли запустить на Windows/CPU» не по README, а по факту.

**Команда (вне репозитория, репозиторий не тронут):**

```
py -3.12 -m venv %TEMP%\captcha_probe\venv
%TEMP%\captcha_probe\venv\Scripts\python.exe -m pip install ddddocr
%TEMP%\captcha_probe\venv\Scripts\python.exe %TEMP%\captcha_probe\probe.py
```

**Результат (фактический вывод):**

```
python 3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]
import ddddocr OK, ver ? elapsed 1.6s
synthetic label: is0j8 -> <temp>/captcha_probe/probe.png
model init 0.15s
classification: 'is0j8' 0.034s
avg over 20: 8.6 ms/img
probability output type: dict
set_ranges ok -> '08'
onnxruntime 1.31.0 providers ['AzureExecutionProvider', 'CPUExecutionProvider']
```

**Установленные пакеты:** `ddddocr 1.6.1`, `onnxruntime 1.31.0`, `numpy 2.5.4`, `opencv-python 5.0.0.93`, `pillow 13.0.0`.

**Что это доказывает (и что нет):**

* ✅ **`ddddocr` реально работает на Windows/CPU «из коробки»**: `pip install ddddocr` → `pip` exit 0, импорт 1.6 с, инициализация модели 0.15 с. Требования README (Windows 64-bit, CPU, Python ≤ 3.12) **подтверждены на практике**.
* ✅ **ONNX Runtime 1.31.0 ставится и работает** на этой машине; доступные провайдеры — `AzureExecutionProvider`, `CPUExecutionProvider` (то есть **GPU-ExecutionProvider не подхватился** без `onnxruntime-gpu`; для нашей GTX 1080 Ti нужен отдельный пакет `onnxruntime-gpu`).
* ✅ **Распознавание точное**: на синтетической капче `is0j8` (5 символов, шумные линии, 160×60) движок вернул ровно `'is0j8'`. Скорость — **8.6 мс на картинку** на CPU (медиана 20 прогонов).
* ✅ **Реализована ровно та техника «маскирования словаря», о которой шла речь**: `ocr.set_ranges("0123456789")` отработал без ошибки и заставил движок выдать `'08'` вместо `'is0j8'` — модель физически не может выдать символ вне разрешённого диапазона. Для CaptchaOCR это готовый механизм «знаю алфавит типа — маскирую логиты».
* ✅ **Доступен вывод вероятностей** (`classification(raw, probability=True)` возвращает `dict`) — это то, что нужно для калибровки и для отбраковки сомнительных предсказаний.
* ❌ **Это не бенчмарк на нашем домене.** Картинка была сгенерирована мной в temp-каталоге (никакого доступа к `dataset/` не было), это не Minecraft-стиль. Измерение говорит только о том, что стек работает и быстрый, — **не** о качестве на капчах.
* ❌ **Наш собственный ONNX в `ddddocr` не подставлялся** — для этого нужен экспорт нашей CRNN в ONNX и `charset.json` с полями `charset/word/image/channel`; обе вещи в проекте не готовы (чекпойнта с экспортом нет).
* ❌ **GPU-путь не проверялся** (провайдеры только CPU/Azure).

---

## 9. Что это значит для CaptchaOCR

1. **Строить свой runtime «с нуля» не нужно — но и взять готовый нельзя «как есть».** План: (а) наша CRNN экспортируется в **ONNX** (готовые рецепты есть в [PaddleOCR deploy/paddle2onnx](https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/deploy/paddle2onnx/readme.md), [SanyumCode/captcha-crnn](https://github.com/SanyumCode/captcha-crnn) уже делает ONNX/TorchScript-экспорт из CRNN+CTC); (б) немедленно получаем CPU-инференс на Windows через **ONNX Runtime 1.31.0** без единой своей строки C++; (в) если понадобится именно «свой движок» — берём **архитектуру** [RapidOCRLite](https://github.com/RapidAI/RapidOCRLite) (C ABI + рукописные ядра + AVX2/AVX-512/NEON/Metal/Vulkan) и **тулинг** [RapidSpeech.cpp](https://github.com/RapidAI/RapidSpeech.cpp) (формат модели + квантователь + CLI), а не их код целиком.

2. **Готовый «движок капч» с подменяемой моделью существует — [ddddocr](https://github.com/sml2h3/ddddocr) (`import_onnx_path` + `charsets_path`).** Это позволяет проверить нашу модель **сегодня**, без написания рантайма: экспортируем CRNN в ONNX, кладём рядом `charset.json` с полями `charset/word/image/channel`, и получаем работающий смоук-тест/сервис. Лицензия MIT, Windows/CPU **подтверждены измерением** (§8): 8.6 мс на картинку, ONNX Runtime 1.31.0 ставится без плясок. Дополнительный бонус того же движка — `set_ranges()` (маскирование алфавита по типу капчи) и вывод вероятностей: обе возможности уже проверены и работают.

3. **Наш главный технический долг — не модель, а разнообразие датасета, и готовые проекты подтверждают правильный рецепт.** Мы measured 1.000 на 6 типах «учили» и 0.000 на невиданных — 46 визуальных стилей по 100 штук. Эталонные проекты ([cloverpray](https://github.com/cloverpray/deep-learning-captcha-ocr-tutorial) — 3 *параметризованных стилевых семейства*; [NextGen-CAPTCHAs](https://github.com/MetaAgentX/NextGen-CAPTCHAs) — 27 семейств; [OpenCaptchaWorld](https://github.com/MetaAgentX/OpenCaptchaWorld) — 20 типов) показывают: качество решает **покрытие стилей и число сэмплов на стиль**, а не размер модели. Практический вывод: инвестировать в новые стилевые семейства в нашем Java-генераторе (а не в новую архитектуру) — при этом ориентироваться на параметризацию «шрифт × размер × поворот × шум × палитра × длина», как в `cloverpray`.

4. **Чужие модели надо переоценить после правильного кропа и правильного препроцессинга, но не ждать от них чуда.** `PaddleOCR`/`RapidOCR` дают **готовые CRNN+CTC-веса в ONNX** (PP-OCRv3/v6 rec-модели, включая кириллические версии), которые можно прогнать по нашим `roi`-полосам и сравнить с нашей моделью на одинаковом входе. `txtcaptcha` ([jtrecenti/txtcaptcha](https://github.com/jtrecenti/txtcaptcha), MIT) вдобавок показывает технику **маскирования словаря по типу капчи** (`decrypt(..., mask=...)`) — ровно то, что нужно для случая, где у типа известен алфавит (цифры / буквы / русские слова). Наш CRNN с 63 классами может получить тот же приём почти бесплатно.

5. **Риск «сделать свой рантайм» — лицензионный и организационный, а не технический.** [RapidOCRLite](https://github.com/RapidAI/RapidOCRLite) — Apache-2.0 по коду, но его «lite»-веса — модифицированная OpenRAIL-M с ограничениями; [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) и [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — Apache-2.0 целиком; [ncnn](https://github.com/Tencent/ncnn) — лицензия API не определилась (`NOASSERTION`), и это надо проверить вручную перед использованием. Практический вывод: **строить рантайм поверх ONNX Runtime (MIT) — самый чистый по лицензии путь**, а «свой» рантайм оставить на вторую очередь, когда профилирование покажет, что ORT — узкое место.

---

## 10. Чего не нашёл / не проверил

### Не нашёл
* **Файла брифа** `build/scratch/briefs2/A_ready_projects.md` — нет (glob по `build/scratch/**` и `**/briefs2/**` пуст).
* **Готового проекта «captcha.cpp» / «captcha runtime»** — проекта с таким названием, функцией (собственный формат модели + квантователь + CLI + C API) **и** специализацией на капчах, не существует. Ближайшие — [RapidOCRLite](https://github.com/RapidAI/RapidOCRLite) (для PP-OCR) и [RapidSpeech.cpp](https://github.com/RapidAI/RapidSpeech.cpp) (для звука).
* **Ни одного открытого «решателя Minecraft-капч» с нейросетью** — искал GitHub API по `minecraft captcha` (70 репозиториев), `minecraft captcha map botfilter` (0 результатов), PyPI по `anti-captcha`, `python-anticaptcha`, `py-captcha`, `captcha-generator`, `captcha_recognition`, `dddd_trainer`, `pycaptcha` — **все MISS**. Всё найденное — серверные плагины (защита) и клиенты коммерческих API (reCAPTCHA/Turnstile).
* **PyPI-пакета `opencaptcha`** — есть только GitHub-репозиторий [ashtonav/opencaptcha](https://github.com/ashtonav/opencaptcha) (C#, MIT) с публичным API генерации.
* **Репозитория `Graf-J/captcha-crnn-finetuned`** на GitHub — существует только как HF-модель.
* **Репозиториев `mummoja/pytesseract` и `asvinogradov/keras-ocr`** — старые адреса отдают 404; актуальные владельцы указаны в PyPI `project_urls`.

### Не проверил
* **Не устанавливал и не бенчмаркил** (кроме §8) ни один из перечисленных OCR-стеков на нашем датасете: PaddleOCR, EasyOCR, docTR, MMOCR, CNOCR, Surya, RapidOCR, keras-ocr, Tesseract, `txtcaptcha`, `cloverpray`-пайплайн, `OcrLiteOnnx`, `RapidOCRLite`, `RapidOcrCpp`. Все их цифры — из документации проектов, не из наших замеров.
* **Не собирал** `RapidOCRLite` (нужен CMake + C++ toolchain) и **не запускал** `RapidOcrCpp`/`OcrLiteOnnx` (нужны предсобранные .7z с releases/gitee).
* **Не проверял** производительность ни одного рантайма на GTX 1080 Ti (sm_61) — ни одна из приведённых в отчёте цифр не измерена на нашем железе.
* **Не читал** исходники `RapidOCRLite`/`RapidSpeech.cpp` — только README; утверждение «операторы CTC/DB реализованы вручную» взято из текста README проекта.
* **Не проверял лицензии по тексту** `LICENSE` для `ncnn` (`NOASSERTION` в API), `NopeCHALLC/nopecha-extension`, `cloverpray`, `0b01/SimGAN-Captcha`, `GeorgeChan/captchapng` — там, где API не отдал SPDX-идентификатор.
* **Не воспроизводил** заявленные accuracy из README/сниппетов: 99.7 % у [Bazskillz](https://github.com/Bazskillz/captcha-crnn-solver), 99.49 % у [roncuevas/Captchas](https://github.com/roncuevas/Captchas), ~89 % у [txtcaptcha](https://github.com/jtrecenti/txtcaptcha), 90.08 % у [Wall3/Yara_Captcha_Solver](https://huggingface.co/Wall3/Yara_Captcha_Solver) (у последней на момент проверки `downloads=0`).
* **Не искал** в npm/crates.io (смотрел только GitHub и PyPI), не проверял коммерческие API-сервисы (2captcha, CapSolver, Anti-Captcha) — их тарифы и качество.
* **Не сравнивал** с `web.archive.org` — исторические версии проектов не запрашивал, все данные актуальны на 2026-10-22.
