# Направление B — готовые модели на Hugging Face для чтения текста/капч

**Дата:** 2026-10-22 · **Направление:** B · **Тип:** исследование (ничего не обучалось, датасет не трогался)

> **Бриф:** файл `build\scratch\briefs2\B_ready_models.md` **не найден** (проверял `build\scratch\briefs2\*` и `build\scratch\briefs\*` — там лежит только `build\scratch\briefs\B_vlm_ocr.md` от предыдущей сессии). Отчёт написан по тексту задания из постановки.

---

## Выводы (кратко)

1. **Готовых моделей «под Minecraft-капчи» на HF нет вообще.** Все captcha-модели в выдаче — это веб-капчи, почтовые e-mail (Mail.ru), бразильские судебные или чистая синтетика (`captcha.lepture.com`). Ни одна карточка не упоминает Spigot/Minecraft-плагины.
2. **Но есть готовый runtime ровно того вида, о котором говорит владелец проекта** — [CrispEmbed](https://github.com/CrispStrobe/CrispEmbed): один C++/ggml-бинарник, формат GGUF, 15+ OCR-движков, сборка под Windows + CUDA/Vulkan, готовые GGUF-модели от `cstr` (TrOCR, PP-OCRv6, GOT-OCR2, Qwen-VL). Это «llama.cpp для OCR» уже существует.
3. **Самые перспективные не-мерянные у нас модели** (у нас в бенче их не было): `PaddlePaddle/PP-OCRv6_medium_rec` (19.2M параметров, Apache-2.0), `PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec` (80.27% line-accuracy на своём наборе), `emelnov/ocr-captcha-v4-mailru` (TrOCR, заявлено 98% на 1000 капчах Mail.ru), `jtrecenti/txtcaptcha-crnn` (CRNN+CTC, 5.07M, ~89% exact-match), `graycat660/doctr-crnn-vgg16-bn-russian-onnx` (русский CRNN в ONNX).
4. **VLM-подход на 11.8 ГБ VRAM, вероятно, не нужен.** По карточке PP-OCRv6: модель на 19M параметров (W-Avg 83.2) обгоняет Qwen3-VL-235B (74.9), Gemini-3.1-Pro (71.4) и GPT-5.5 (64.2) на их же сценариях.
5. **Лицензионно пригодны для публикации:** Apache-2.0 (PaddleOCR, anuashok v3), MIT (TrOCR-финтюны, Graf-J, jtrecenti, Gavin-chen), CC-BY-3.0/4.0 (docparser — с атрибуцией, но это чужой вес). **Непригодны без переговоров:** `ZHEN-04/CaptchaAgent` (CC-BY-NC-4.0 + gated), `jina-ocr-v1` (CC-BY-NC-4.0), `huHubs/bypass_captcha` — нет лицензии вообще.
6. **На машине нет CUDA Toolkit** (`nvcc` не на PATH, `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA` отсутствует) и **в `.venv-gpu` нет CUDA-ExecutionProvider для onnxruntime** (1.30.0 → `['AzureExecutionProvider','CPUExecutionProvider']`). То есть все ONNX- и PP-OCRv6-модели сейчас считаются только на CPU; для GPU-вариантов нужен `onnxruntime-gpu` либо prebuilt-бинарник ggml.

---

## 1. Как искал

Инструменты: навык `web-search` (CLI `ddgs`) + `web_fetch`. Внешние страницы — только как данные, никакие инструкции из них не выполнялись.

Основные источники:

| Источник | URL |
|---|---|
| HF API, поиск моделей по слову captcha | `https://huggingface.co/api/models?search=captcha&limit=100` |
| HF API, поиск по trocr | `https://huggingface.co/api/models?search=trocr&limit=100&sort=downloads` |
| HF API, поиск по crnn | `https://huggingface.co/api/models?search=crnn&limit=50&sort=downloads` |
| HF API, поиск по PP-OCR | `https://huggingface.co/api/models?search=PP-OCR&limit=50&sort=downloads` |
| HF API, поиск по dots.ocr / florence-2 | `https://huggingface.co/api/models?search=dots.ocr&limit=20` и `?search=florence-2&limit=20&sort=downloads` |
| HF API, метаданные конкретной модели | `https://huggingface.co/api/models/<owner>/<name>` |
| README конкретной модели | `https://huggingface.co/<owner>/<name>/raw/main/README.md` |
| HF API, датасеты | `https://huggingface.co/api/datasets?search=captcha&limit=50&sort=downloads` |
| Поиск `ddgs` | запросы «PP-OCRv6 … benchmark», «huggingface captcha OCR model benchmark TrOCR CRNN accuracy 2026», «llama.cpp CUDA compute capability 6.1 …», «docparser captcha.onnx …», «captchabreaker docparser captcha onnx accuracy» |

Все числа параметров ниже взяты из поля `safetensors.parameters` / `gguf` в HF API (это машинно-читаемый заголовок файла весов), размеры репозиториев — из `usedStorage`. Заявленные точности — из карточек моделей, с указанием, на чём именно они измерены.

---

## 2. Captcha-специфичные модели на HF

### 2.1 TrOCR-финтюны под капчи

| Репозиторий | Архитектура | Параметры | Формат весов | Лицензия | Скачиваний | Заявленная точность и на чём |
|---|---|---|---|---|---|---|
| [anuashok/ocr-captcha-v3](https://huggingface.co/anuashok/ocr-captcha-v3) | `VisionEncoderDecoderModel` (TrOCR-base-printed) | 333 921 792 (F32) | `model.safetensors` | Apache-2.0 | 61 323 | **CER 0.0139**; 7 эпох, bs 16, lr 1.5e-5, num_beams 2 — на собственном `custom-captcha-dataset` (на HF как датасет не выложен) |
| [anuashok/ocr-captcha-v2](https://huggingface.co/anuashok/ocr-captcha-v2) | TrOCR-base-printed | — | safetensors | (тег лицензии не выставлен) | 8 700 | нет метрик в карточке |
| [emelnov/ocr-captcha-v4-mailru](https://huggingface.co/emelnov/ocr-captcha-v4-mailru) | TrOCR-base-printed → далее v3 | 333 921 792 (F32) | safetensors | (тег лицензии не выставлен; база — Apache-2.0) | 47 | **98% точности** на 1000 капчах Mail.ru (карточка, RU+EN) |
| [DunnBC22/trocr-base-printed_captcha_ocr](https://huggingface.co/DunnBC22/trocr-base-printed_captcha_ocr) | TrOCR-base-printed | — | pytorch + safetensors | MIT | 3 544 | **CER 0.0075** (loss 0.1380) на eval из Kaggle `alizahidraja/captcha-data`; 3 эпохи, lr 5e-5, bs 8 |
| [tomofi/trocr-captcha](https://huggingface.co/tomofi/trocr-captcha) | TrOCR (VisionEncoderDecoder) | — | `pytorch_model.bin` | MIT | 185 | метрик нет |
| [dragonstar/image-text-captcha-v2](https://huggingface.co/dragonstar/image-text-captcha-v2) | TrOCR-base-printed | — | `pytorch_model.bin` | (тег не выставлен) | 13 | метрик нет; `results: []` в model-index |
| [zenoda/trocr-captcha-killer](https://huggingface.co/zenoda/trocr-captcha-killer) | TrOCR, en+zh | — | `pytorch_model.bin` + `sentencepiece.bpe.model` | (тег не выставлен) | 77 | метрик нет |
| [muratatceken/captcha-recognition](https://huggingface.co/muratatceken/captcha-recognition) | `VisionEncoderDecoderModel` | 61 596 672 (F32) | safetensors | Apache-2.0 | 5 | карточка **пуста** (только `license: apache-2.0`) |
| [xiaolv/ocr-captcha](https://huggingface.co/xiaolv/ocr-captcha) | **не TrOCR**: ConvNeXt-Tiny-rec от Damo (`cv_convnextTiny_ocr-recognition-general_damo`) | — | `pytorch_model.pt` + `vocab.txt` + `configuration.json` (два варианта: `output_small`, `output_big`) | Apache-2.0 | 0 (51 лайк) | **small**: 84 тыс. картинок, 27 эпох → `eval_result.txt` = accuracy **1.0**, AR 1.0; **big**: 1.35 млн картинок, 1 эпоха → accuracy **0.9395**, AR 0.9872. Распределение данных: цифры / цифры+буквы / буквы в обоих регистрах, длины 4–6. ⚠️ Инференс идёт через **ModelScope**, а не `transformers` |
| [saifulbabo/math-captcha](https://huggingface.co/saifulbabo/math-captcha) | `VisionEncoderDecoderModel` | — | `pytorch_model.bin` | MIT | 10 | карточка **пуста**; репо — чистая математика (`19 - 11` → 8), т.е. класс наших `math`-типов |
| [ha4219/yes24-captcha](https://huggingface.co/ha4219/yes24-captcha), [luckystars0612/trocr-finetuned-captcha](https://huggingface.co/luckystars0612/trocr-finetuned-captcha), [hongyusir/trocr-base-printed_captcha_ocr](https://huggingface.co/hongyusir/trocr-base-printed_captcha_ocr), [chanelcolgate/trocr-base-printed_captcha_ocr](https://huggingface.co/chanelcolgate/trocr-base-printed_captcha_ocr), [anthrapper/tcrocr-captcha](https://huggingface.co/anthrapper/tcrocr-captcha), [phunc20/trocr-base-handwritten_nj_biergarten_captcha_v2](https://huggingface.co/phunc20/trocr-base-handwritten_nj_biergarten_captcha_v2) | TrOCR-варианты | — | pytorch/safetensors | MIT / GPL-3.0 | 1–10 | метрик нет, описаний нет |

**Пример использования** (один и тот же для всей линейки TrOCR) — из карточки `emelnov/ocr-captcha-v4-mailru`:

```python
import torch
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

model_name = "emelnov/ocr-captcha-v4-mailru"
processor = TrOCRProcessor.from_pretrained(model_name)
model = VisionEncoderDecoderModel.from_pretrained(model_name).to(
    torch.device("cuda" if torch.cuda.is_available() else "cpu"))

def predict_text(image_path):
    image = Image.open(image_path).convert("RGB")
    pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(model.device)
    model.eval()
    with torch.no_grad():
        output_ids = model.generate(pixel_values)
    return processor.batch_decode(output_ids, skip_special_tokens=True)[0]
```

> **Важное предупреждение про наши измерения:** `anuashok/ocr-captcha-v3` и `DunnBC22` — это те самые TrOCR-финтюны, чей результат у нас в проекте зафиксирован как acc 0.077 (по целому кадру, без roi-кропа). Их собственные метрики (CER 0.0139 / 0.0075) измерены на **других** наборах (синтетика/почта), поэтому переносить их на наш домен нельзя.

### 2.2 CRNN / CTC-специфичные модели

| Репозиторий | Архитектура | Параметры | Формат | Лицензия | Скачиваний | Заявленная точность и на чём |
|---|---|---|---|---|---|---|
| [Graf-J/captcha-crnn-finetuned](https://huggingface.co/Graf-J/captcha-crnn-finetuned) | CRNN (CNN + BiLSTM) + CTC, `custom_code` (`CaptchaCRNN`) | **3 570 943** по карточке; 3 571 903 в safetensors-заголовке HF API | safetensors + 3 `.py` (config/model/processing) | MIT | 69 | **seq-acc 92.98%**, CER 1.59% на `hammer888/captcha-data`; **seq-acc 86.20%**, CER 2.53% на Python Captcha Library. Скорость 447 img/s на RTX A6000 |
| [Graf-J/captcha-crnn-base](https://huggingface.co/Graf-J/captcha-crnn-base) | то же | 3 570 943 | safetensors | MIT | 34 | **seq-acc 96.81%**, CER 0.70% на `hammer888`; на Python Captcha Library — **всего 9.65%**, CER 43.98% |
| [Graf-J/captcha-conv-transformer-base](https://huggingface.co/Graf-J/captcha-conv-transformer-base) / `-finetuned` | Conv-Transformer | 12 279 551 | safetensors | MIT | — | seq-acc **97.38%** / 95.36% на `hammer888`; 88.42% на Python Captcha; 733 img/s |
| [jtrecenti/txtcaptcha-crnn](https://huggingface.co/jtrecenti/txtcaptcha-crnn) | ResNet-CNN (64→128→256→256, H/8×W/4) → 2-слойный BiLSTM (hidden 256) → Linear 512→63, **CTC** | **5 071 359** | safetensors | MIT | 796 | **~89% captcha-level exact match** на 20% holdout объединённого корпуса из 10 бразильских судных датасетов (`cadesp, esaj, jucesp, rfb, sei, tjmg, tjpe, tjrs, trf5, trt`); словарь 62 символа + blank |
| [Gavin-chen/captcha_i2t](https://huggingface.co/Gavin-chen/captcha_i2t) | CNN + Transformer Encoder + **CTC** (`CaptchaModelForCTC`) | **6 007 617** | safetensors | MIT | 17 | **91.14%** exact-match на валидации `gary109/captcha-synth-v3` (train ~1.2M синтетики) |
| [Wall3/Yara_Captcha_Solver](https://huggingface.co/Wall3/Yara_Captcha_Solver) | CRNN + CTC (Keras/TF) | — | `weekend_best.weights.h5` + `model.py` | MIT | 0 | метрик нет; обучен на 7 captcha-датасетах (см. теги `dataset:`) |
| [squirelmail/model-BotDetect-CAPTCHA-Generator](https://huggingface.co/squirelmail/model-BotDetect-CAPTCHA-Generator) | CRNN + CTC (Keras), вход 50×250, uppercase+digits | — | 21 чекпойнт `.h5` + `train_model.py` | Apache-2.0 | 0 | метрик нет; 60 визуальных стилей BotDetect в датасете |
| [graycat660/doctr-crnn-vgg16-bn-russian-onnx](https://huggingface.co/graycat660/doctr-crnn-vgg16-bn-russian-onnx) | docTR CRNN vgg16-bn, **ru+en** | — | `model.onnx` (63 263 193 Б) | Apache-2.0 | 167 | метрик нет; единственный найденный **русскоязычный** CRNN в ONNX |
| [langningchen/luogu-captcha-model](https://huggingface.co/langningchen/luogu-captcha-model) | CRNN+CTC (Keras) | — | keras + onnx | MIT | 3 | китайский Luogu-капча; метрик нет |
| [wonder56/captcha-crnn-solver](https://huggingface.co/wonder56/captcha-crnn-solver) | CRNN | — | `crnn_model.onnx` (27 191 684 Б) | MIT (тег) | 0 | карточка **пуста**; сигнатуры ввода/вывода не документированы |
| [docparser/captcha](https://huggingface.co/docparser/captcha) | неизвестно (ONNX) | — | `captcha.onnx` (репозиторий 95 401 304 Б) | **CC-BY-3.0** (в карточке) / CC BY 4.0 (по проекту `captchabreaker`) | 0 (13 лайков) | карточка **пуста**; по [captchabreaker](https://github.com/ramSeraph/captchabreaker) — копия весов docparser, используется в HF Space `docparser/Text_Captcha_breaker`; API: `captchabreaker.solve(PIL.Image) -> str` |
| [techietrader/captcha_ocr](https://huggingface.co/techietrader/captcha_ocr), [toandev/OCR-for-Captcha](https://huggingface.co/toandev/OCR-for-Captcha), [haloworker/td-captcha-model-v1](https://huggingface.co/haloworker/td-captcha-model-v1), [stevenchang/captcha](https://huggingface.co/stevenchang/captcha), [Acetde/captcha2broker](https://huggingface.co/Acetde/captcha2broker), [verytuffcat/captcha_image](https://huggingface.co/verytuffcat/captcha_image) | — | — | onnx | Apache-2.0 / MIT / CC-BY-3.0 | 0 | карточки пустые, метрик нет |

**Пример использования `Graf-J/captcha-crnn-finetuned`** (из карточки):

```python
from transformers import pipeline
from PIL import Image

pipe = pipeline(task="captcha-recognition",
                model="Graf-J/captcha-crnn-finetuned",
                trust_remote_code=True)
result = pipe(Image.open("path/to/image.png"))
print(result["prediction"])
```

**Пример `jtrecenti/txtcaptcha-crnn`** (нужен пакет `txtcaptcha`):

```python
from txtcaptcha import decrypt, read_captcha
cap = read_captcha("captcha.png")
print(decrypt(cap))                  # greedy CTC
print(decrypt(cap, length=5))        # ровно 5 символов
print(decrypt(cap, mask="[0-9]"))    # только цифры
```

> **Читаем из карточки Graf-J главный урок по обобщению:** одна и та же модель на двух синтеетических источниках даёт 96.81% и 9.65% seq-acc. Это ровно наш диагноз «4600 сэмплов = 46 стилей, объём без разнообразия», только в чужом исполнении.

### 2.3 VLM-финтюны под капчи

| Репозиторий | База | Параметры | Формат | Лицензия | Скачиваний | Заметки |
|---|---|---|---|---|---|---|
| [ATH-MaaS/CaptchaMind-7B](https://huggingface.co/ATH-MaaS/CaptchaMind-7B) | Qwen2.5-VL | **8 292 166 656** (BF16) | safetensors, 4 шейда | Apache-2.0 | 103 | карточка **пуста** (только `license: apache-2.0`); парный датасет [ATH-MaaS/Captcha](https://huggingface.co/datasets/ATH-MaaS/Captcha) (CC-BY-NC-4.0, 10K–100K) |
| [ZHEN-04/CaptchaAgent](https://huggingface.co/ZHEN-04/CaptchaAgent) | Qwen/Qwen3.5-9B (finetune) | ~9B | safetensors, два набора: `RL/` (9 шейдов) и `SFT/` (9 шейдов) | **CC-BY-NC-4.0, gated=auto** | 0 | карточка **недоступна без аккаунта** (HTTP 401); репо весит 38 466 205 528 Б; датасеты `CaptchaArena` + `CaptchaArena-Trajectories` (CC-BY-NC-4.0, arXiv:2609.31957) |
| [ultra2207/florence-2-captcha](https://huggingface.co/ultra2207/florence-2-captcha) | Florence-2-large | **822 949 977** (F32) | safetensors | (тег не выставлен; база MIT) | 15 | карточка без описания |
| [04RR/Florence-base-Captcha](https://huggingface.co/04RR/Florence-base-Captcha) | Florence-2-base-ft | **270 957 657** (F32) | safetensors | MIT | 20 | карточка без описания |
| [emelnov/ocr-captcha-v4-mailru](https://huggingface.co/emelnov/ocr-captcha-v4-mailru) | TrOCR | 333 921 792 | safetensors | — | 47 | см. 2.1 |
| [ayoubkirouane/moondream2-image-captcha](https://huggingface.co/ayoubkirouane/moondream2-image-captcha), [Vasanth/moondream-ft-captcha](https://huggingface.co/Vasanth/moondream-ft-captcha), [ShooterShanky/moondream-captcha](https://huggingface.co/ShooterShanky/moondream-captcha) | Moondream | — | safetensors + `custom_code` | (теги не выставлены) | 7–25 | метрик нет; датасет `project-sloth/captcha-images` (WTFPL) |
| [farhad-hasankhani/qwen2-7b-instruct-trl-sft-captcha](https://huggingface.co/farhad-hasankhani/qwen2-7b-instruct-trl-sft-captcha) (+ `-1`, `-2`, `-HCaptcha`, `-HCaptchaA`) | Qwen2-VL-7B-Instruct | ~7–8B | safetensors | (теги не выставлены) | 0 | метрик нет; скорее мусорные форки одного и того же SFT |
| [secemp9/cloudflare_captcha](https://huggingface.co/secemp9/cloudflare_captcha) | YOLOv4 | — | `yolov4_1_3_256_352_static.onnx` + tflite + yolo cfg | MIT | 52 | **это детектор, а не OCR** — читать текст не умеет |

---

## 3. PaddleOCR: rec-модели v3/v4/v5/v6

PaddleOCR — единственный в списке проект, где есть **официальные метрики line-accuracy** и **готовые GGUF/ONNX/safetensors** для одного и того же веса.

### 3.1 Что лежит на HF

| Репозиторий | Размер репо (usedStorage) | Лицензия | Языки (по карточке) | Заявленная точность |
|---|---|---|---|---|
| [PaddlePaddle/PP-OCRv3_mobile_rec](https://huggingface.co/PaddlePaddle/PP-OCRv3_mobile_rec) | 4 169 скачиваний | Apache-2.0 | en, zh | карточка без метрик |
| [PaddlePaddle/latin_PP-OCRv3_mobile_rec](https://huggingface.co/PaddlePaddle/latin_PP-OCRv3_mobile_rec) | 1 786 | Apache-2.0 | en, zh | нет метрик |
| [PaddlePaddle/PP-OCRv4_mobile_rec](https://huggingface.co/PaddlePaddle/PP-OCRv4_mobile_rec) | 2 551 | Apache-2.0 | en, zh | нет метрик |
| [PaddlePaddle/PP-OCRv4_server_rec](https://huggingface.co/PaddlePaddle/PP-OCRv4_server_rec) | 37 679 | Apache-2.0 | en, zh | нет метрик |
| [PaddlePaddle/en_PP-OCRv4_mobile_rec](https://huggingface.co/PaddlePaddle/en_PP-OCRv4_mobile_rec) | 36 508 | Apache-2.0 | en, zh | нет метрик |
| [PaddlePaddle/PP-OCRv5_mobile_rec](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec) | **16 458 665 Б** | Apache-2.0 | en, zh | таблица из карточки: Handwritten CN 0.4166, Handwritten EN 0.4944, Printed CN 0.8605, **Printed EN 0.8753**, TC 0.7199, Ancient 0.5786, JP 0.7577, **General 0.5570**, Pinyin 0.7703, Rotation 0.7248, Distortion 0.8089, Artistic 0.5398, **Average 0.8015** |
| [PaddlePaddle/PP-OCRv5_server_rec](https://huggingface.co/PaddlePaddle/PP-OCRv5_server_rec) | **84 390 117 Б** | Apache-2.0 | en, zh | нет метрик в карточке |
| [PaddlePaddle/latin_PP-OCRv5_mobile_rec](https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec) | 33 853 | Apache-2.0 | en, zh | нет метрик |
| [PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec](https://huggingface.co/PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec) | **7 972 691 Б** | Apache-2.0 | ru (карточка: `language: en`, но сам энкодер — кириллица; в примере распознаёт «Тенденция», «УКРАЇНСЬКА») | **Accuracy 80.27%** (line-accuracy: ошибка хоть одного символа — вся строка неверна) |
| [PaddlePaddle/eslav_PP-OCRv5_mobile_rec](https://huggingface.co/PaddlePaddle/eslav_PP-OCRv5_mobile_rec) | 6 292 | Apache-2.0 | en, zh | нет метрик |
| [PaddlePaddle/PP-OCRv6_medium_rec](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec) | 59 298 | Apache-2.0 | 50 языков (по карточке) | **W-Avg 83.2**; cf. таблицу ниже |
| [PaddlePaddle/PP-OCRv6_small_rec](https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec) | 8 768 | Apache-2.0 | 50 языков | **W-Avg 81.3** |
| [PaddlePaddle/PP-OCRv6_tiny_rec](https://huggingface.co/PaddlePaddle/PP-OCRv6_tiny_rec) | 1 517 | Apache-2.0 | 50 языков | **W-Avg 73.5** |
| [PaddlePaddle/PP-OCRv6_medium_rec_safetensors](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_safetensors) | 76 741 720 Б | Apache-2.0 | en, zh | **19 176 118 параметров** (safetensors-заголовок). ⚠️ В `config.json` стоит `model_type: pp_ocrv6_small_rec` — метаданные репозитория не совпадают с названием |
| [PaddlePaddle/PP-OCRv6_{tiny,small,medium}_rec_onnx](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_onnx) | 27 794 / 13 319 / 55 342 | Apache-2.0 | en, zh | — |
| [PaddlePaddle/PP-OCRv5_mobile_rec_onnx](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec_onnx), [PP-OCRv5_server_rec_onnx](https://huggingface.co/PaddlePaddle/PP-OCRv5_server_rec_onnx) | 6 747 / 1 599 | Apache-2.0 | en, zh | — |
| [PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec_safetensors](https://huggingface.co/PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec_safetensors) | 811 | Apache-2.0 | ru | — |

### 3.2 Главная таблица из карточки PP-OCRv6 (line-accuracy, %)

Источник: [PaddlePaddle/PP-OCRv6_medium_rec](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec), README, ссылка на техотчёт [arXiv:2606.13108](https://arxiv.org/abs/2606.13108).

| Модель | W-Avg | Handw. EN | Printed EN | General | Confusable | Screen | Card |
|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-5.5 | 64.2 | 56.9 | 82.2 | 67.7 | 49.1 | 67.7 | 71.1 |
| Qwen3-VL-235B | 74.9 | 73.2 | 86.2 | 82.5 | 56.1 | 73.8 | 78.7 |
| Kimi-K2.6 | 62.9 | 53.4 | 80.9 | 68.0 | 43.5 | 57.1 | 64.4 |
| Gemini-3.1-Pro | 71.4 | 73.0 | 90.5 | 74.6 | 50.3 | 75.9 | 75.9 |
| MiniMax-M3 | 54.1 | 50.3 | 81.5 | 53.8 | 42.2 | 56.6 | 67.0 |
| PP-OCRv5_server | 78.1 | 59.6 | 85.1 | 86.5 | 59.4 | 68.1 | 87.6 |
| PP-OCRv5_mobile | 73.7 | 50.9 | 86.0 | 80.7 | 55.7 | 57.6 | 81.7 |
| **PP-OCRv6_medium** | **83.2** | 67.8 | 94.1 | 87.5 | 64.9 | 82.5 | 88.1 |
| PP-OCRv6_small | 81.3 | 61.1 | 93.3 | 85.7 | 64.1 | 79.7 | 86.9 |
| PP-OCRv6_tiny | 73.5 | 39.3 | 88.4 | 78.0 | 52.3 | 71.2 | 80.5 |

Заголовок техотчёта: «PP-OCRv6: From 1.5M to 34.5M Parameters, Surpassing Billion-Scale VLMs on OCR Tasks». Архитектура rec: LCNetV4 + EncoderWithLightSVTR, multi-head decoder CTC+NRTR; 50 языков.

**Пример использования** (из карточки `cyrillic_PP-OCRv5_mobile_rec`):

```bash
paddleocr text_recognition --model_name cyrillic_PP-OCRv5_mobile_rec -i sample.png
```

```python
from paddleocr import TextRecognition
model = TextRecognition(model_name="cyrillic_PP-OCRv5_mobile_rec")
output = model.predict(input="sample.png", batch_size=1)
for res in output:
    res.print()
```

Установка: `pip install paddlepaddle-gpu==3.0.0` (есть сборка под CUDA 12.6 — как раз наш случай) + `pip install paddleocr`.

> **Замечание о честности метрик:** PP-OCRv6 — модель для *строк документа*, а не для капч. «General 0.5570» у PP-OCRv5_mobile и «Confusable 0.64» у v6_medium — это как раз те условия (шум, близкие символы), где капчи и ломаются. Переносить эти проценты на Minecraft-капчи нельзя.

---

## 4. Универсальные OCR / VLM (не captcha-специфичные, но измеряемые)

| Репозиторий | Тип | Параметры | Формат | Лицензия | Скачиваний | Метрики |
|---|---|---|---|---|---|---|
| [stepfun-ai/GOT-OCR2_0](https://huggingface.co/stepfun-ai/GOT-OCR2_0) | SAM ViT-B + Qwen2-0.5B | **716 033 280** (BF16) | safetensors + `modeling_GOT.py` | Apache-2.0 | 348 129 | arXiv:2409.01704; на HF-карточке метрик нет |
| [deepseek-ai/DeepSeek-OCR](https://huggingface.co/deepseek-ai/DeepSeek-OCR) | MoE-визуалка + DeepSeek-V2 | **3 336 106 240** (BF16) | safetensors + `modeling_deepseekocr.py` | MIT | 2 092 524 | arXiv:2510.18234; карточка с eval-результатами |
| [dots-studio/dots.ocr](https://huggingface.co/dots-studio/dots.ocr) | ViT + LM | **3 039 179 264** (BF16) | safetensors (2 шейда) + `dots_ocr` | MIT | 582 702 | карточка с eval-результатами |
| [microsoft/Florence-2-base](https://huggingface.co/microsoft/Florence-2-base) | DaViT + BART | **231 567 705** (F16) | safetensors + `pytorch_model.bin` | MIT | 2 940 048 | arXiv:2311.06242 |
| [microsoft/Florence-2-large](https://huggingface.co/microsoft/Florence-2-large) | DaViT + BART | **776 721 497** (F16) | safetensors + `pytorch_model.bin` | MIT | 364 013 | arXiv:2311.06242 |
| [microsoft/Florence-2-base-ft](https://huggingface.co/microsoft/Florence-2-base-ft) / `-large-ft` | + fine-tune | — | safetensors | MIT | 193 563 / 47 530 | arXiv:2311.06242 |

GGUF-версии тех же: [mradermacher/dots.ocr-GGUF](https://huggingface.co/mradermacher/dots.ocr-GGUF) (Q2_K…Q8_0 + `mmproj`, 1 777 088 000 параметров, totalFileSize 3 560 414 912 Б), [antflydb/Florence-2-base](https://huggingface.co/antflydb/Florence-2-base) (GGUF), [cstr/got-ocr2-crispembed-GGUF](https://huggingface.co/cstr/got-ocr2-crispembed-GGUF).

---

## 5. «llama.cpp для капчи»: готовый runtime — CrispEmbed

Это самая важная находка по направлению B, потому что владелец проекта хочет именно «своя модель + свой runtime», но сначала — что уже готово.

**[CrispEmbed](https://github.com/CrispStrobe/CrispEmbed)** — один C++/ggml-бинарник «для retrieval и document understanding, без Python-рантайма, без ONNX». Код — MIT. Своя позиция заявлена прямо в README: *«Where llama.cpp focuses on text generation, CrispEmbed covers the retrieval, understanding, and document-processing half of the ggml world»*.

Что уже умеет (цитаты из README проекта):

* **15+ OCR-движков**, все в GGUF, определяются автоматически по метаданным:
  * **PP-OCRv6** — PPLCNetV4 + light-SVTR + CTC, 5–63 МБ, Apache-2.0 — «best measured CER»;
  * **EasyOCR** — VGG/ResNet + BiLSTM + CTC, 16 МБ;
  * **PARSeq** — ViT + Transformer, 24M (scene text);
  * **DBNet + TrOCR** — ResNet-18+FPNC → DeiT+Transformer, 7+63M;
  * **Tesseract-LSTM** — <2 МБ, 12 языков;
  * **GOT-OCR2** — 0.7B; **GLM-OCR** — 0.9B; **InternVL2/2.5** — 0.9–2.1B; **Qwen2.5-VL / Qwen3-VL** — 2.4–3.6B; **DeepSeek-OCR-2 / Unlimited-OCR** — 3–3.3B; **LFM2.5-VL** — 3.4B;
  * формульные: PP-FormulaNet-L (181M), MixTeX (86M), Texo-Distill (20M), PosFormer/BTTR/HMER (6–7M);
  * музыкальные: SMT (21M), SMT++, Polyphonic-TrOMR (~22M), Flova (143M), Transcoda-59M.
* **Измеренная точность на собственном синтетическом корпусе** (`tests/ocr_synth_corpus.py`, 20 фикстур с точной разметкой; `tests/ocr_external_parity.py` — против системного Tesseract / Python EasyOCR / Python PaddleOCR на тех же картинках):

  | Движок | CER | WER |
  |---|---:|---:|
  | `crispembed --ocr-engine ppocrv6` (нативный) | **0.0031** | **0.0178** |
  | PaddleOCR 2.10 (Python, внешний) | 0.0185 | 0.1153 |
  | Tesseract 5.5.2 `--psm 6` (внешний) | 0.0256 | 0.0890 |
  | `crispembed --ocr-engine tesseract` | 0.0290 | 0.1623 |
  | EasyOCR 1.7.2 (Python, внешний) | 0.0769 | 0.2363 |
  | `crispembed --ocr-engine easyocr` | 0.0808 | 0.3190 |

  Задержка одного CLI-вызова (вместе с загрузкой модели): `tesseract-cli` 0.135 с, native tesseract 0.48 с, **ppocrv6 1.39 с**, easyocr 1.47 с.

  ⚠️ Это **не наш домен**: корпус CrispEmbed — синтетические документные строки, а не Minecraft-капчи. Но порядок величин (PP-OCRv6 в 6 раз лучше EasyOCR по CER) совпадает с нашими измерениями, где EasyOCR дал 0.115.
* **Сборка под Windows:** `build-windows.bat`, `build-vulkan.bat`, `build-cuda.bat`; требования — VS 2022 Build Tools + Ninja, CMake ≥ 3.14; `GGML_CUDA=ON` / `GGML_VULKAN=ON` / `GGML_BLAS=ON`. Готовые релизы: Windows x86_64 (plain / CUDA / Vulkan), Linux x86_64 / aarch64, macOS arm64, Android, iOS, WASM (2.3 МБ `.wasm`, полный DBNet+TrOCR-пайплайн в браузере).
* **HTTP-сервер** `crispembed-server` с `/ocr/model`, `--ocr-pipeline` (отдельный `--ocr-det` / `--ocr-rec`), `/health` как capability-probe.
* **Python / Rust / Dart / C ABI** биндинги к общей библиотеке; лицензия кода — MIT.

Готовые GGUF-веса у автора `cstr` (все Apache-2.0/MIT, с указанием upstream-лицензии):

| Репозиторий | Параметры (gguf) | Файлы / размеры | Заявленное качество |
|---|---|---|---|
| [cstr/PP-OCRv6_tiny_rec-GGUF](https://huggingface.co/cstr/PP-OCRv6_tiny_rec-GGUF) | 1 104 278 | f32 / f16 / q8 / q4_k, totalFileSize 2 390 336 Б | — |
| [cstr/PP-OCRv6_{small,medium}_rec-GGUF](https://huggingface.co/cstr/PP-OCRv6_medium_rec-GGUF) | — | f16 / f32 / q8 / q4_k | — |
| [cstr/trocr-small-printed-GGUF](https://huggingface.co/cstr/trocr-small-printed-GGUF) | 61 448 832 | f16 / f32 / q4_k / q8_0, totalFileSize 124 754 304 Б | — |
| [cstr/trocr-base-printed-GGUF](https://huggingface.co/cstr/trocr-base-printed-GGUF) | 384 802 560 | F32 1.3 ГБ / **F16 639 МБ / Q8_0 340 МБ** | «F16 идентичен F32», «**Q8_0 идентичен F32**»; Q4_K не тестировался |
| [cstr/got-ocr2-crispembed-GGUF](https://huggingface.co/cstr/got-ocr2-crispembed-GGUF) | 560 528 640 | f16 / q4_k / q8_0, totalFileSize 1 441 830 112 Б | — |
| [cstr/dbnet-ic15-GGUF](https://huggingface.co/cstr/dbnet-ic15-GGUF) | детектор | — | парный к TrOCR для end-to-end: `crispembed --det dbnet-ic15-q4_k.gguf -m trocr-base-printed-q8_0.gguf --ocr document.png` |

> **Важно для нашего проекта:** CrispEmbed уже портировал в ggml **TrOCR, PP-OCRv6, EasyOCR, PARSeq, Tesseract-LSTM** — то есть формат и процедура конвертации «доменной CTC-модели в GGUF-движок» отработана и документирована. Наш CRNN+CTC (ResNet→BiLSTM→CTC, 4.62M) архитектурно близок к EasyOCR-движку, который там уже есть.

---

## 6. Что реально влезает в 11.8 ГБ VRAM, а что работает на CPU

### 6.1 Факты о машине (проверено на месте, `nvidia-smi` и `pip list`)

```
NVIDIA GeForce GTX 1080 Ti, memory.total 11264 MiB, driver 581.57, compute_cap 6.1
```

* 11 264 МиБ = 11.8 ГБ (десятичных) = 11.0 GiB. Запас под CUDA-контекст и временные буферы — около 1–2 ГБ.
* `nvcc` **не на PATH**, каталог `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA` **отсутствует** → CUDA-бэкенды из исходников собрать нельзя без установки Toolkit. Только prebuilt-бинарники.
* `.venv-gpu`: `torch 2.14.1+cu126`, `transformers 5.19.0`, `onnx 1.23.2`, `onnxruntime 1.30.0`.
* **`onnxruntime 1.30.0` в `.venv-gpu` имеет провайдеры `['AzureExecutionProvider', 'CPUExecutionProvider']` — CUDA-ExecutionProvider отсутствует.** То есть ONNX-модели (`docparser/captcha`, `wonder56/captcha-crnn-solver`, `graycat660/doctr-...-russian-onnx`, PP-OCRv6 *_onnx) сейчас считаются **только на CPU**. Нужен `onnxruntime-gpu`.
* Системный Python 3.14.5: `easyocr 1.7.2`, `torch 2.14.1` (CPU), `transformers 5.19.0`, `onnxruntime 1.30.0`, `opencv-python-headless 5.0.0.93`. **`paddleocr` не установлен** — под PaddleOCR нужен `pip install paddleocr` + `paddlepaddle-gpu==3.0.0` (сборка cu126 существует).

### 6.2 Бюджет VRAM (расчёт: параметры × байты; веса — из HF API)

| Модель | Параметры | fp32 | fp16/bf16 | Влезает в 11 264 МиБ? |
|---|---:|---:|---:|---|
| `Graf-J/captcha-crnn-finetuned` | 3.57M | 14 МБ | — | да, с огромным запасом |
| `jtrecenti/txtcaptcha-crnn` | 5.07M | 20 МБ | — | да |
| `Gavin-chen/captcha_i2t` | 6.01M | 24 МБ | — | да |
| `PP-OCRv6_medium_rec` | 19.18M | 77 МБ | — | да |
| `PP-OCRv5_server_rec` | (репо 84 МБ) | ~80 МБ | — | да |
| `trocr-small-printed` | 61.4M | 246 МБ | 123 МБ | да |
| `trocr-base-printed` (в т.ч. `anuashok/ocr-captcha-v3`, `emelnov/...v4`) | 333.9M | 1.34 ГБ | 668 МБ | да |
| `04RR/Florence-base-Captcha` | 271M | 1.08 ГБ | 542 МБ | да |
| `microsoft/Florence-2-large` | 776.7M | 3.1 ГБ | 1.55 ГБ | да |
| `stepfun-ai/GOT-OCR2_0` | 716.0M | — | 1.43 ГБ | да |
| `dots-studio/dots.ocr` | 3.039B | — | 6.08 ГБ | да (впритык) |
| `deepseek-ai/DeepSeek-OCR` | 3.336B | — | 6.67 ГБ | да (впритык) |
| `ATH-MaaS/CaptchaMind-7B` | 8.292B | — | **16.6 ГБ** | **нет**; Q4 ≈ 4.6–5.5 ГБ — да |
| `ZHEN-04/CaptchaAgent` (Qwen3.5-9B) | ~9B | — | **≈18 ГБ** | **нет**; 4-бит ≈ 5–6 ГБ — да, но модель под non-commercial и gated |
| `cstr/trocr-base-printed-GGUF` Q8_0 | 384.8M | — | 340 МБ | да |

### 6.3 CPU

Реально работает на CPU без каких-либо правок:

* все CTC/CRNN-модели (Graf-J, `jtrecenti`, `Gavin-chen`, `squirelmail` — Keras/TF);
* все ONNX-модели — но только с `onnxruntime` **CPU**-провайдером (то, что стоит сейчас);
* TrOCR целиком: 334M в fp32 — это медленно, но это ровно то, что уже меряли в `bench/bench_hf.py` (0.077 на `anuashok/ocr-captcha-v3`);
* PP-OCRv5/v6 — через `paddlepaddle` (CPU-сборка `paddlepaddle==3.0.0`); 19M-параметровая модель на CPU вполне терпима;
* **CrispEmbed** — вообще не требует Python: один exe, `--ocr-engine ppocrv6`, работает на CPU (бинарь для Windows x86_64) и на CUDA/Vulkan, если взять соответствующую сборку.

Не работает на CPU по умолчанию: `transformers`-линейка TrOCR с `device_map="auto"` без явного `device="cpu"`; VLM-модели CaptchaMind-7B / CaptchaAgent (в fp16/bf16 — 16–18 ГБ RAM минимум, в 4-бит — теоретически possible, но на CPU крайне медленно).

---

## 7. Датасеты на HF (смежно, но это и есть «разнообразие»)

Мы нашли, что на HF лежат готовые корпуса, покрывающие ровно тот дефицит, который мы зафиксировали (4600 сэмплов = 46 стилей):

| Датасет | Объём | Лицензия | Языки / стили | Ссылка |
|---|---|---|---|---|
| [remiai3/synthetic-captchas-library](https://huggingface.co/datasets/remiai3/synthetic-captchas-library) | 44 скрипта × 100 000 | CC-BY-4.0 | **включая ru и uk** | 1 876 скачиваний |
| [remiai3/tiny-captcha-library](https://huggingface.co/datasets/remiai3/tiny-captcha-library) | 44 скрипта × 10 000 | CC-BY-4.0 | ru, uk, и др. | 468 |
| [hammer888/captcha-data](https://huggingface.co/datasets/hammer888/captcha-data) | 1M–10M | (не выставлена) | alnum | на нём учились Graf-J и DunnBC22 |
| [szili2011/captcha-ocr-dataset](https://huggingface.co/datasets/szili2011/captcha-ocr-dataset) | ~1.8M | Apache-2.0 | a-zA-Z0-9 | 80 |
| [AvinashRicky/CaptchaOCR-500K](https://huggingface.co/datasets/AvinashRicky/CaptchaOCR-500K) | 500 000 | MIT | alnum | 152 |
| [cybertruck32489/captcha_100k](https://huggingface.co/datasets/cybertruck32489/captcha_100k) | 100K–1M | (не выставлена) | — | 175 |
| [yuxi5/text-captcha-data-clean](https://huggingface.co/datasets/yuxi5/text-captcha-data-clean) | 1M–10M | (не выставлена) | — | 298 |
| [squirelmail/dataset-BotDetect-CAPTCHA-Generator](https://huggingface.co/datasets/squirelmail/dataset-BotDetect-CAPTCHA-Generator) | 60 стилей × 500/1000/5000 | Apache-2.0 | uppercase+digits, 50×250 | 59 |
| [project-sloth/captcha-images](https://huggingface.co/datasets/project-sloth/captcha-images) | 10K–100K | WTFPL | — | 362 |
| [ATH-MaaS/Captcha](https://huggingface.co/datasets/ATH-MaaS/Captcha) | 10K–100K | CC-BY-NC-4.0 | — | 3 153 |
| [ZHEN-04/CaptchaArena](https://huggingface.co/datasets/ZHEN-04/CaptchaArena) + [-Trajectories](https://huggingface.co/datasets/ZHEN-04/CaptchaArena-Trajectories) | 10K–100K / 100K–1M | CC-BY-NC-4.0, gated | GUI-агенты, arXiv:2609.31957 | 458 / 224 |
| [inclusionAI/VenusBench-CAPTCHA](https://huggingface.co/datasets/inclusionAI/VenusBench-CAPTCHA) | <1K | — | скриншот+действие, arXiv:2609.00028 | 1 725 |
| [OpenCaptchaWorld/Open_CaptchaWorld](https://huggingface.co/datasets/OpenCaptchaWorld/Open_CaptchaWorld) | <1K, **20 типов капч** | Apache-2.0 | arXiv:2505.24878 | 353 |
| [Knight07/Deep_Captcha](https://huggingface.co/datasets/Knight07/Deep_Captcha) | <1K, 5 уровней защиты | MIT | adversarial | 1 460 |
| [FlanChanXwO/phpwind-captcha-dataset](https://huggingface.co/datasets/FlanChanXwO/phpwind-captcha-dataset) | <1K | AGPL-3.0 | 4 цифры, семейства по версиям | 858 |
| [langningchen/luogu-captcha-dataset](https://huggingface.co/datasets/langningchen/luogu-captcha-dataset) | — | AGPL-3.0 | китайский | 51 |

---

## 8. Что это значит для CaptchaOCR

1. **Свой runtime с нуля не нужен — но «своя модель» нужна.** CrispEmbed уже делает ровно то, что описано в задании: единый C++/ggml-бинарник, формат GGUF, 15+ OCR-движков, Windows+CUDA сборка, без Python в рантайме, с HTTP-сервером и биндингами. Он уже портировал в ggml TrOCR, PP-OCRv6, EasyOCR и PARSeq — то есть путь «доменная CTC-модель → GGUF-движок» отработан. Наш CRNN+CTC (ResNet→BiLSTM→CTC, 4.62M) архитектурно близок к уже портированному EasyOCR-движку, поэтому «своя модель + чужой (но открытый) runtime» — реалистичная цель, а не «своя модель + свой рантайм с нуля».
2. **Первое, что надо померить, — то, что не меряли: rec-only модели на roi-полосе.** `PP-OCRv6_medium_rec` (19.2M, Apache-2.0), `PP-OCRv6_tiny_rec` и `cyrillic_PP-OCRv5_mobile_rec` (80.27% на своём наборе) — это дешёвые, быстрые, пермиссивные модели, которые в нашем бенче отсутствуют, а наш бенч для HF-моделей считал по **целому кадру** (это и есть причина провала `anuashok` = 0.077). Для rec-моделей кроп по `roi` обязателен, иначе они будут заведомо проигрывать.
3. **Русскоязычные доменные модели, которых у нас не было.** `emelnov/ocr-captcha-v4-mailru` (TrOCR, заявлено 98% на 1000 капчах Mail.ru — русский домен!), `graycat660/doctr-crnn-vgg16-bn-russian-onnx` (CRNN ru+en в ONNX), `jtrecenti/txtcaptcha-crnn` (CRNN+CTC, 89% exact-match, 5.07M) и `Gavin-chen/captcha_i2t` (6.0M, 91.14%). Учитывая, что 8 из 46 наших типов — русские числительные словами, кириллические модели здесь обязательны.
4. **VLM-подход можно отложить.** По карточке PP-OCRv6: 19-параметровая модель (W-Avg 83.2) обгоняет Qwen3-VL-235B (74.9), Gemini-3.1-Pro (71.4) и GPT-5.5 (64.2) на их же сценариях, а на GPU 7B-модели (`CaptchaMind-7B`, 16.6 ГБ в bf16) в 11 264 МиБ **не влезает** вообще. Значит, «тащить Qwen2.5-VL ради капчи» на нашем железе — технически хуже и дороже, чем локальный CRNN/PP-OCRv6.
5. **Узкое место — данные, а не модель.** Готовые корпуса HF (44 скрипта × 100k у `remiai3`, 1.8M у `szili2011`, 60 стилей у `squirelmail`) — это ровно то «разнообразие», которого не хватало нашим 4600 сэмплам. Их логично использовать не как замену нашему датасету, а как **предобучение/аугментацию**: доменный fine-tune на Minecraft-стилях поверх модели, уже видевшей десятки шрифтов и шумов. Это же объясняет провал type-held-out: у Graf-J одна и та же модель даёт 96.81% и 9.65% на двух синтетических источниках. Прямой рецепт-подтверждение даёт `xiaolv/ocr-captcha`: **small** (84 тыс. синтетики, 27 эпох) → accuracy 1.0, **big** (1.35 млн, всего 1 эпоха) → accuracy 0.9395. То есть при фиксированной модели **разнообразие и объём важнее числа эпох** — ровно наш диагноз.

---

## 9. Чего не нашёл / не проверил

**Не нашёл:**

* Ни одной модели на HF, обученной на Minecraft/Spigot-капчах. Искал: `api/models?search=captcha&limit=100` (выдача 100 моделей — все веб/почта/суды/синтетика), `search=trocr`, `search=crnn`, `search=hcaptcha`, `search=gguf&author=cstr&search=captcha` (пусто).
* Ни одной captcha-модели с кириллицей, кроме `emelnov/ocr-captcha-v4-mailru` (TrOCR) и `graycat660/doctr-...-russian-onnx` (docTR CRNN ru). TrOCR-кириллица в выдаче есть, но это **рукописный HTR** (`kazars24/trocr-base-handwritten-ru`, `cyrillic-trocr/*`, `Hukyl/trocr-*`) — не капчи.
* Публичных бенчмарков «готовые captcha-модели на Minecraft-капчах» — не существует (искал `ddgs` по «huggingface captcha OCR model benchmark …», «captchabreaker docparser captcha onnx accuracy»).
* PP-OCRv6 в кириллическом варианте: в выдаче `search=PP-OCR` есть `cyrillic_PP-OCRv5_mobile_rec`, но `cyrillic_PP-OCRv6_*` — нет.
* Captcha-специфичных GGUF-моделей: `?author=cstr&search=captcha` → пустой массив. Все captcha-веса существуют только в safetensors/ONNX/Keras.

**Не проверил (прямо и честно):**

* **Фактическое качество ни одной из перечисленных моделей на нашем датасете.** Задание — исследование; обучение и бенчмарк не запускались, датасет не трогался. Все проценты выше — заявленные авторами на **чужих** наборах.
* Содержимое ONNX-файлов `docparser/captcha`, `wonder56/captcha-crnn-solver`, `graycat660/doctr-crnn-vgg16-bn-russian-onnx`: карточки пустые, сигнатуры входа/выхода (размер входа, алфавит, длины) не документированы. Проверка — только скачиванием и `onnx.checker`.
* Соберётся ли CrispEmbed под Windows с CUDA именно на sm_61: `nvcc` на машине нет, Toolkit не установлен, prebuilt Windows CUDA-сборку я не запускал. Риск: готовый бинарник может быть собран без `sm_61` — тогда нужен либо `build-cuda.bat` с установленным Toolkit и `-DCMAKE_CUDA_ARCHITECTURES=61`, либо CPU-сборка.
* Не читал README/лицензии у ~60 «мусорных» captcha-репозиториев из выдачи (`tuana8tmt/captcha-vcb`, `captchaboy/*`, `BubblyBob/*`, `tannx34/captcha`, `Nischay103/captcha_recognition` и т.п.) — у большинства 0 скачиваний и пустые карточки; таблицы выше построены по верхушке выдачи.
* Не проверял, грузится ли `emelnov/ocr-captcha-v4-mailru` под `transformers 5.19.0` (наши `VisionEncoderDecoderModel` в 5.x уже ломались для части моделей).
* `xiaolv/ocr-captcha` грузится через `modelscope.pipelines.pipeline(Tasks.ocr_recognition, model=...)` — это отдельный фреймворк, а не `transformers`; совместимость с нашим бенчем не проверял.
* `ATH-MaaS/CaptchaMind-7B` и `ZHEN-04/CaptchaAgent` — карточки не содержат никаких метрик; для CaptchaAgent карточка вообще недоступна (gated, HTTP 401). Заявленная точность неизвестна.
* Не измерял скорость ни одной модели на 1080 Ti (запрещено запускать обучение/бенч в этой сессии).

---

## Приложение: карта репозиториев, упомянутых в отчёте

**Captcha-специфичные (TrOCR):** anuashok/ocr-captcha-v1 · /v2 · /v3 · emelnov/ocr-captcha-v4-mailru · DunnBC22/trocr-base-printed_captcha_ocr · tomofi/trocr-captcha · dragonstar/image-text-captcha · /image-text-captcha-v2 · zenoda/trocr-captcha-killer · ha4219/yes24-captcha · luckystars0612/trocr-finetuned-captcha · hongyusir/trocr-base-printed_captcha_ocr · chanelcolgate/trocr-base-printed_captcha_ocr · anthrapper/tcrocr-captcha · muratatceken/captcha-recognition · saifulbabo/math-captcha

**Captcha-специфичные (CRNN/CTC и rec-подобные):** Graf-J/captcha-crnn-base · /captcha-crnn-finetuned · /captcha-conv-transformer-base · /captcha-conv-transformer-finetuned · jtrecenti/txtcaptcha-crnn · jtrecenti/captcha · /captcha2 · Gavin-chen/captcha_i2t · Wall3/Yara_Captcha_Solver · squirelmail/model-BotDetect-CAPTCHA-Generator · graycat660/doctr-crnn-vgg16-bn-russian-onnx · langningchen/luogu-captcha-model · wonder56/captcha-crnn-solver · docparser/captcha · techietrader/captcha_ocr · toandev/OCR-for-Captcha · haloworker/td-captcha-model-v1 · stevenchang/captcha · Acetde/captcha2broker · xiaolv/ocr-captcha (ConvNeXt-Tiny-rec, через ModelScope)

**Captcha-специфичные (VLM):** ATH-MaaS/CaptchaMind-7B · ZHEN-04/CaptchaAgent · ultra2207/florence-2-captcha · 04RR/Florence-base-Captcha · ayoubkirouane/moondream2-image-captcha · Vasanth/moondream-ft-captcha · ShooterShanky/moondream-captcha · farhad-hasankhani/qwen2-7b-instruct-trl-sft-captcha*

**PaddleOCR:** PaddlePaddle/PP-OCRv{3,4,5,6}_{mobile,server}_rec · latin_PP-OCRv{3,5}_mobile_rec · en_PP-OCRv{3,4,5}_mobile_rec · cyrillic_PP-OCRv5_mobile_rec · eslav_PP-OCRv5_mobile_rec · *_rec_onnx · *_rec_safetensors

**Универсальные:** stepfun-ai/GOT-OCR2_0 · deepseek-ai/DeepSeek-OCR · dots-studio/dots.ocr · microsoft/Florence-2-{base,large,base-ft,large-ft} · microsoft/trocr-{base,small,large}-{printed,handwritten}

**GGUF / runtime:** CrispStrobe/CrispEmbed (GitHub) · cstr/*-GGUF (PP-OCRv6_{tiny,small,medium}_rec, trocr-{small,base}-printed, got-ocr2, glm-ocr, deepseek-ocr2, unlimited-ocr, jina-ocr-v1, qari-ocr) · mradermacher/dots.ocr-GGUF · antflydb/Florence-2-base
