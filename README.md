# CaptchaOCR

![пять капч Minecraft-антиботов с кодами](docs/img/hero.png)

*`Archy-X/Krypton/map` · `haq/mapcha/map` · `jonesdevelopment/sonar/standard` · `just-captcha/ProstoCaptcha/map` · `LimboFilter/symbols` — пять капч из датасета; все — вывод генераторов, не иллюстрация.*

[![dataset](https://img.shields.io/badge/dataset-210k_PNG-blue)](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset)
[![types](https://img.shields.io/badge/types-21-informational)](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset)
![plugins](https://img.shields.io/badge/upstream_plugins-13-informational)
![exact](https://img.shields.io/badge/exact_match-62%25-brightgreen)
[![model](https://img.shields.io/badge/model-PP--OCRv6_universal__v1-orange)](https://huggingface.co/Titlehhhh/captchaocr-ppocrv6)
![license](https://img.shields.io/badge/license-MIT_%2B_upstream-blue)
![java](https://img.shields.io/badge/java-21-red)

Открытый датасет капч Minecraft-антиботов и модель, которая читает их полосу с ответом.

Плагин-антибот показывает игроку картинку с кодом и просит ввести его в чат, чтобы отсечь ботов. Такую картинку называют капчей. Каждый открытый плагин рисует по-своему: свой шрифт, холст, помехи и свои ошибки. Готовые OCR-модели на таких картинках работают плохо.

Здесь лежат генераторы тех же плагинов на Java: они заново рисуют капчи пиксель в пиксель и пишут разметку — что нарисовано, что вводить и где полоса с ответом. На этой разметке обучена модель PP-OCRv6 и сняты замеры. Главный вывод: кроп по полосе важнее самой модели.

*A dataset of Minecraft anti-bot captchas and a PP-OCRv6 recogniser.*

[Установка](#установка) · [Использование](#использование) · [Датасет, модель, демо](#датасет-модель-демо) · [Что работает](#что-работает-и-что-нет) · [Результаты](#результаты) · [Структура](#структура-репозитория) · [Куда дальше](#куда-дальше) · [Участие](#участие) · [Лицензия](#лицензия)

## Установка

```powershell
git clone https://github.com/Titlehhhh/CaptchaOCR
cd CaptchaOCR
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Для модели хватит Python. Генераторам нужен JDK 21.

## Использование

```python
import torch
from PIL import Image
from transformers import PPOCRV6SmallRecForTextRecognition
from transformers import PPOCRV6SmallRecImageProcessor

REPO = "Titlehhhh/captchaocr-ppocrv6"
model = PPOCRV6SmallRecForTextRecognition.from_pretrained(REPO).eval()
proc = PPOCRV6SmallRecImageProcessor.from_pretrained(REPO)
inputs = proc(images=[Image.open("band.png").convert("RGB")], return_tensors="pt")
with torch.no_grad():
    logits = model(**inputs)
print(proc.post_process_text_recognition(logits))
```

`band.png` — обрезок полосы с ответом, а не скриншот: модель ждёт кроп, а не кадр игры.

## Датасет, модель, демо

- **Датасет** — [Titlehhhh/captchaocr-dataset](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset): 20 типов, 200 000 строк, 9 Parquet-шардов.
- **Модель** — [Titlehhhh/captchaocr-ppocrv6](https://huggingface.co/Titlehhhh/captchaocr-ppocrv6): `universal_v1`, median exact 0.8875 на 18 типах с полосой из разметки.
- **Демо** — `.venv\Scripts\python webapp\app.py`, дальше <http://127.0.0.1:8765/>; работает офлайн.

```python
from huggingface_hub import snapshot_download
snapshot_download("Titlehhhh/captchaocr-dataset", repo_type="dataset", local_dir="data")
```

## Что работает и что нет

- Датасет опубликован; метки пересчитаны и сошлись.
- Модель опубликована с весами и карточкой.
- Генераторы воспроизводят 13 плагинов вместе с их ошибками.
- Кроп по полосе поднимает exact против целого кадра.

- 3 типа рисуют число словом: нужен шаг-solver, OCR их не берёт.
- Своя CRNN на невиданных плагинах узнаёт меньше половины.
- TrOCR хуже и заметно медленнее.
- Датасет не воспроизводим: генераторы не засеяны, пересборка даёт другой набор.

## Результаты

![схема: капча → кроп → текст](docs/img/pipeline.png)

| полоса из разметки (oracle) | кроппер AUTO | весь кадр |
|---:|---:|---:|
| 66.79 % | **62.26 %** | 43.57 % |

840 сэмплов, по 40 на тип. Числа сняты на этом датасете; 3 типа дают 0 даже с oracle.

## Структура репозитория

| путь | что внутри |
|---|---|
| `dataset/generator/`, `dataset/generator_ru/` | Java 21: генераторы капч |
| `dataset/out/`, `dataset/out_ru/` | 210 000 PNG (21 тип × 10 000) с разметкой; в git их нет |
| `train/` | CRNN+CTC с нуля, дообучение PP-OCRv6 и TrOCR |
| `webapp/` | офлайн-демо на `http.server` |
| `reports/`, `docs/` | измерения, онбординг, формат данных |

## Куда дальше

- [Все измеренные числа](reports/HTML/index.html)
- [Онбординг](docs/ONBOARDING.md)
- [Как обучать](docs/HOW_TO_TRAIN.md)
- [Формат датасета](docs/DATASET_FORMAT.md)
- [Плагины и режимы реконструкции](docs/PLUGINS.md)

Статьи: [CRNN (1507.05717)](https://arxiv.org/abs/1507.05717) · [PP-OCRv6 (2606.13108)](https://arxiv.org/abs/2606.13108) · [SVTRv2 (2411.15858)](https://arxiv.org/abs/2411.15858).

## Участие

Issues и PR принимаются. Новый тип капчи — один java-файл в `dataset/generator/dev/captcha/gens/`; замер чужой модели тоже приветствуется. Писать — в issue.

## Лицензия

Код — MIT ([`LICENSE`](LICENSE)). Картинки — под лицензиями плагинов-источников, разбор в [`docs/LICENSES.md`](docs/LICENSES.md).
