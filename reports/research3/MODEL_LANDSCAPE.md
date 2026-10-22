# Ландшафт готовых моделей распознавания капт: что дообучаем в PyTorch

**Задача (R1).** Выбрать **готовую (pretrained)** модель для дообучения на наших данных
(46 типов, 4600 PNG, 29 типов с полосой `roi`) на машине проекта:
GTX 1080 Ti (11.8 ГБ, sm_61), torch 2.14.1+cu126, transformers 5.19.0, Python 3.14.5,
окно обучения ~1–2 часа. Итог должен быть выложен на Hugging Face.

**Ключевой вывод (проверено руками, §6):** в установленном `transformers 5.19.0` есть
**нативные PyTorch-классы для PP-OCRv5/v6** — `PPOCRV6SmallRecForTextRecognition`,
`PPOCRV6TinyRecForTextRecognition`, `PPOCRV6MediumDetForObjectDetection` и др.
То есть **дообчать PP-OCRv6 в PyTorch можно без paddlepaddle вообще**, из готовых
`safetensors` на HF. Это меняет рейтинг: самый сильный готовый baseline проекта
(`PP-OCRv6_medium_rec`, **0.40 accuracy** на наших полосах, `HANDOVER.md` §1.3) становится
и самым дешёвым кандидатом на дообучение.

> Три цифры, на которых стоит решение (замеры §6, не оценки):
> `PP-OCRv6_medium_rec` — **19.1 M параметров, 101 img/s, 2.34 ГБ VRAM** при batch 16 на 48×320;
> `PP-OCRv6_small_rec` — **5.3 M, 170 img/s, 1.11 ГБ**;
> `PP-OCRv6_tiny_rec` — **1.1 M, 325 img/s, 0.35 ГБ**.

---

## 1. Рекомендация одной строкой

> **Первое место: `PaddlePaddle/PP-OCRv6_medium_rec_safetensors` (Apache-2.0) — дообучаем в
> PyTorch через `transformers.PPOCRV6SmallRecForTextRecognition` + собственный CTC-лосс
> (`torch.nn.CTCLoss`) поверх официального `character_dict` из `inference.yml`.**
> Запасной вариант: `PaddlePaddle/PP-OCRv6_small_rec_safetensors` (тот же код, в 1.6 раза
> быстрее, точность ниже на ~2 п.п. по их же метрике).
> Вариант «если бы был paddle / другая GPU»: `PaddleOCR-VL-1.6` (0.9 B, Apache-2.0) или
> LoRA-дообучение `Qwen/Qwen3-VL-4B-Instruct` на GPU ≥ 24 ГБ — но это уже не про окно 1–2 ч
> и не про строки длиной 3–8 символов.

### Три главных аргумента

1. **Обобщение на невиданный стиль плагина.** PP-OCRv6 — единственный из готовых движков,
   который на *наших* данных уже даёт **0.40** против 0.115 у EasyOCR и **0.000** у нашего
   CRNN, обученного с нуля (`HANDOVER.md` §1.3, §6.5). Мы берём не «с нуля», а backbone+neck,
   обученные на 50 языках и на печатных/рукописных/кривых шрифтах, — и дообучаем их на
   46 стилях плагинов.
2. **Скорость в окне 1–2 часа.** 101 img/s на 1080 Ti ⇒ одна эпоха по 3100 картинкам (группы A+B)
   ≈ **31 с**, 60 эпох ≈ **31 мин**. Запас на 4-фолд по типам — 2 ч. У TrOCR-base (333 M) при
   384×384 оценка — десятки img/s, то есть в 3–10 раз дороже (оценка, §7).
3. **Экспорт и лицензия.** Весá уже в `safetensors` (`model.safetensors`), лицензия
   **Apache-2.0**, `head_out_channels=18710` и словарь содержат латиницу, цифры **и кириллицу**,
   поэтому одна дообученная модель покрывает и 8 кириллических типов. Публикация на HF — `push_model`
   без конвертации; paddle не нужен ни для обучения, ни для инференса.

---

## 2. Таблица кандидатов

Обозначения: **VRAM** — пик `torch.cuda.max_memory_allocated` при batch 16 (измерено) либо оценка;
**скорость** — img/s на 1080 Ti (измерено) либо оценка с явной основой. Даты — `lastModified` карточки HF.
Источники по каждой строке — URL в §9 и в самой строке.

| # | HF repo id | Назначение | Параметры | Лицензия | Формат весов на HF | Дообучение в PyTorch | Скорость тренировки на 1080 Ti (реком. разрешение) | VRAM @ batch 16 | Предобучена на | Опубликованная точность (где) | Downloads / likes | Обновлена |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | [`PaddlePaddle/PP-OCRv6_medium_rec_safetensors`](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_safetensors) | general OCR, printed+handwritten, rec | **19 176 118** (safetensors total) | Apache-2.0 | **safetensors** (`model.safetensors`) + `config.json` + `preprocessor_config.json` + `inference.yml` | **ДА, нативно**: `transformers.PPOCRV6SmallRecForTextRecognition.from_pretrained(...)` (в `config.json` `model_type=pp_ocrv6_small_rec`), лосс — свой CTC | **101 img/s** (измерено, 48×320) | **2.34 ГБ** (измерено) | 50 языков, промышленные сцены, печать/рукопись/ artistic (карточка) | rec W-Avg **83.2 %**, Printed EN **94.1 %** (карточка, [arXiv:2606.13108](https://arxiv.org/abs/2606.13108)); на наших полосах **0.40** (`HANDOVER.md` §1.3) | 1 842 / 26 | 2026-06-12 |
| 2 | [`PaddlePaddle/PP-OCRv6_small_rec_safetensors`](https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec_safetensors) | general OCR, rec | **5 292 614** (safetensors) / 5 275 238 (в torch) | Apache-2.0 | safetensors | **ДА, нативно** (`PPOCRV6SmallRecForTextRecognition`) | **170 img/s** (измерено, 48×320) | **1.11 ГБ** (измерено) | то же | rec W-Avg **81.3 %** (карточка) | 975 / 17 | 2026-06-12 |
| 3 | [`PaddlePaddle/PP-OCRv6_tiny_rec_safetensors`](https://huggingface.co/PaddlePaddle/PP-OCRv6_tiny_rec_safetensors) | general OCR, edge, rec | **1 113 470** / 1 106 702 | Apache-2.0 | safetensors | **ДА, нативно** (`PPOCRV6TinyRecForTextRecognition`, `head_out_channels=6906` — меньший словарь!) | **325 img/s** (измерено, 48×320) | **0.35 ГБ** (измерено) | то же | rec W-Avg **73.5 %** (карточка) | 467 / 19 | 2026-06-12 |
| 4 | [`PaddlePaddle/PP-OCRv6_medium_rec`](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec) (+ [`_onnx`](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_onnx)) | general OCR, rec | 19 M (карточка) | Apache-2.0 | **paddle `inference.pdiparams`**; ONNX-версия — `inference.onnx` + `inference.yml` | **НЕТ напрямую**: paddle-формат читает только paddle; в PyTorch брать **safetensors-репо** (строка 1) либо конвертировать ONNX→PyTorch вручную | через ONNX-бэкенд наш харнесс считает CPU (`bench/bench_models.py`), обучение — нет | — | то же | W-Avg 83.2 % | 59 298 / 33 (paddle), 55 342 / 26 (onnx) | 2026-06-12 |
| 5 | [`PaddlePaddle/PP-OCRv5_mobile_rec`](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec), [`PP-OCRv5_mobile_rec_onnx`](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec_onnx), [`latin_PP-OCRv5_mobile_rec`](https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec), [`en_PP-OCRv5_mobile_rec`](https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec), [`PP-OCRv5_server_rec`](https://huggingface.co/PaddlePaddle/PP-OCRv5_server_rec), [`cyrillic_PP-OCRv5_mobile_rec_onnx`](https://huggingface.co/PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec_onnx) | general OCR, rec, есть отдельные латинская/английская/кириллическая сборки | ~10 M / ~10 M / ~10 M (не измерял) | Apache-2.0 | **paddle** `inference.pdiparams` (+ ONNX-версии) — **safetensors-портов для rec не нашёл** | **НЕТ** (paddle/ONNX формат); но в `transformers 5.19` есть `PPOCRV5MobileRecForTextRecognition` — дообучать можно, если найти safetensors-порт (не проверял) | — | — | PaddleOCR v5 | v5_mobile W-Avg **73.7 %** (карточка v6, таблица сравнения) | mobile_rec 40 801 / 16; mobile_rec_onnx 6 747 / 0; latin 33 853 / 8; en 184 510 / 3; server_rec 161 783 / 31 | 2025-06-04 … 2026-05-26 |
| 6 | [`microsoft/trocr-base-printed`](https://huggingface.co/microsoft/trocr-base-printed) | printed, seq2seq OCR | **333 331 200** | **не объявлена** в карточке (тег `license:` отсутствует; у `trocr-base-handwritten` — MIT) | safetensors + `pytorch_model.bin` | **ДА, нативно** (`TrOCRForCausalLM`/`VisionEncoderDecoderModel`), но **нужен `tiktoken`** — см. §6 и §7 | **оценка** 10–25 img/s @384×384 (основа: ~1.15 TFLOP/изображение fwd+bwd при 577 токенах и 333 M параметров) | **оценка** 14–18 ГБ @ batch 16 → не влезает, нужен batch 4–8 + grad-checkpointing | BEiT (encoder) + RoBERTa (decoder), fine-tune на SROIE | WER на SROIE в статье [arXiv:2109.10282](https://arxiv.org/abs/2109.10282) (в карточке метрики нет) | 236 685 / 230 | 2024-05-27 |
| 7 | [`microsoft/trocr-small-printed`](https://huggingface.co/microsoft/trocr-small-printed) | printed, seq2seq OCR | **61 448 832** | не объявлена в карточке | safetensors + `pytorch_model.bin` | **ДА, нативно**, но та же проблема с `tiktoken` | **оценка** 60–120 img/s @384×384 (основа: та же формула, ViT-small ≈ 22 M) | **оценка** 5–8 ГБ @ batch 16 | BEiT-small + RoBERTa-small, fine-tune на SROIE | — | 18 806 / 56 | 2024-05-27 |
| 8 | [`microsoft/trocr-base-handwritten`](https://huggingface.co/microsoft/trocr-base-handwritten), [`trocr-base-stage1`](https://huggingface.co/microsoft/trocr-base-stage1), [`trocr-small-handwritten`](https://huggingface.co/microsoft/trocr-small-handwritten), [`trocr-small-stage1`](https://huggingface.co/microsoft/trocr-small-stage1) | handwritten / stage-1 pretrain | ≈333 M (base), ≈61 M (small) — **счётчики не снимал** | `trocr-base-handwritten` — MIT (тег); у stage1 — не объявлена | safetensors + `pytorch_model.bin` | ДА, нативно | как строки 6–7 | как строки 6–7 | stage-1: неразмеченные документы; base: IAM | — | 132 616 / 531 (base-hw), 93 174 / 24 (base-stage1), 54 420 / 72 (small-hw), 7 325 / 16 (small-stage1) | 2022-03-02 (все четыре) |
| 9 | [`anuashok/ocr-captcha-v3`](https://huggingface.co/anuashok/ocr-captcha-v3) (+ [`v2`](https://huggingface.co/anuashok/ocr-captcha-v2)) | **captcha-специфичная**, TrOCR-base, дообучена на капчах | **333 921 792** | Apache-2.0 | safetensors | ДА, нативно (TrOCR) | как строка 6 | как строка 6 | `microsoft/trocr-base-printed` + свой `custom-captcha-dataset` | **CER 0.0139** на своём датасете (карточка); на **наших** данных — **0.077** (`HANDOVER.md` §1.3) | 61 323 / 43 | 2024-11-15 |
| 10 | [`DunnBC22/trocr-base-printed_captcha_ocr`](https://huggingface.co/DunnBC22/trocr-base-printed_captcha_ocr), [`hongyusir/trocr-base-printed_captcha_ocr`](https://huggingface.co/hongyusir/trocr-base-printed_captcha_ocr), [`tomofi/trocr-captcha`](https://huggingface.co/tomofi/trocr-captcha) | **captcha-специфичные** TrOCR | ≈333 M (не измерял) | MIT (DunnBC22), **не объявлена** (hongyusir), MIT (tomofi) | только `pytorch_model.bin` (safetensors нет) | ДА, но требует `tiktoken`; **в transformers 5.x эти три не грузятся** — по `HANDOVER.md` §1.3 «не грузятся под transformers 5.x» | как строка 6 | как строка 6 | trocr-base-printed + капча-датасеты | метрики не опубликованы (у hongyusir `model-index` пуст) | 3 543 / 9; 11 / 0; 192 / 5 | 2023-01-13; 2023-07-02; 2023-05-05 |
| 11 | [`Graf-J/captcha-crnn-finetuned`](https://huggingface.co/Graf-J/captcha-crnn-finetuned), [`Graf-J/captcha-conv-transformer-finetuned`](https://huggingface.co/Graf-J/captcha-conv-transformer-finetuned), [`Graf-J/captcha-crnn-base`](https://huggingface.co/Graf-J/captcha-crnn-base) | **captcha-специфичные**, CRNN/CTR, `custom_code` | **3 571 903** (crnn-finetuned) | MIT | safetensors + `modeling_captcha.py` (нужен `trust_remote_code=True`) | ДА, но это **не transformers-код**: придётся тащить чужой `custom_code` в наш репозиторий и чинить его под transformers 5.19 | оценка: CRNN-подобная скорость, ~500–900 img/s | оценка < 1 ГБ | `hammer888/captcha-data` (см. [датасет](https://huggingface.co/datasets/hammer888/captcha-data)) | на **наших** 40 сэмплах: crnn-finetuned **acc 0.100 / CER 0.638** (`HANDOVER.md` §6.5); conv-transformer — не грузился харнессом | 69 / 1; 101 / 0; 34 / 0 | 2026-03-01; 2026-02-23; 2026-02-23 |
| 12 | [`stepfun-ai/GOT-OCR2_0`](https://huggingface.co/stepfun-ai/GOT-OCR2_0) / [`GOT-OCR-2.0-hf`](https://huggingface.co/stepfun-ai/GOT-OCR-2.0-hf) | VLM OCR (документы, layout) | ≈580 M (карточка/статья, **не измерял**) | Apache-2.0 | safetensors (+ `custom_code` у оригинала) | ДА, нативно: `GotOcr2ForConditionalGeneration` есть в transformers 5.19 | оценка: VLM-режим, 1024 пикселей → десятки img/s | оценка 8–12 ГБ @ batch 16 (нужен LoRA + grad-checkpointing) | документы (CC-OCR и пр.) | см. [arXiv:2409.01704](https://arxiv.org/abs/2409.01704) | 348 129 / 1 574 (оригинал), 13 353 / 243 (-hf) | 2024-09-12 |
| 13 | [`PaddlePaddle/PaddleOCR-VL-1.6`](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6) / [`-1.5`](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5) / [`PaddleOCR-VL`](https://huggingface.co/PaddlePaddle/PaddleOCR-VL) | VLM OCR + layout/таблицы/формулы | ≈0.9 B (ERNIE4.5-0.3B + визуальный энкодер; **не измерял**) | Apache-2.0 | safetensors + `custom_code` | ДА, нативно: `PaddleOCRVLForConditionalGeneration` есть в transformers 5.19 (но карточка требует `paddleocr` для пайплайна) | оценка: 5–15 img/s | оценка 18–24 ГБ @ batch 16 → **не влезает** в 11.8 ГБ без LoRA/offload | документы, 100+ языков | см. [arXiv:2606.03264](https://arxiv.org/abs/2606.03264) (1.6), [2601.21957](https://arxiv.org/abs/2601.21957) (1.5), [2510.14528](https://arxiv.org/abs/2510.14528) (v1) | 64 036 / 546; 22 252 / 666; 8 522 / 1 673 | 2026-05-27; 2026-01-28; 2025-10-16 |
| 14 | [`Qwen/Qwen3-VL-4B-Instruct`](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct), [`Qwen3-VL-2B-Instruct`](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct), [`Qwen/Qwen2.5-VL-3B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct) | VLM общего назначения | 2 B / 4 B / 3 B (по именам/карточкам, **не измерял**) | Apache-2.0 | safetensors | ДА, нативно (`Qwen3VLForConditionalGeneration`, `Qwen2_5_VLForConditionalGeneration` есть в 5.19), но полное дообучение 4 B не влезает в 11.8 ГБ — только LoRA | оценка: 1–4 img/s @ LoRA | оценка 20+ ГБ @ LoRA bf16 без offload → **не влезает**; 2 B + LoRA + grad-checkpointing — на грани | мультимодальные данные Qwen | см. eval-карточки Qwen | 3 602 828 / 510; 2 037 547 / 502; 1 804 143 / 735 | 2025-10-19; 2025-10-11; 2025-01-26 |
| 15 | PARSeq: [`baud-xl/parseq`](https://github.com/baud-xl/parseq) (GitHub) → [`Felix92/doctr-torch-parseq-multilingual-v1`](https://huggingface.co/Felix92/doctr-torch-parseq-multilingual-v1) (HF-порт) | general scene-text, autoregressive, context-aware | ~200 M (xl) — **не измерял** | MIT (оригинал), Apache-2.0 (порт) | порт: pytorch-веса под `doctr` (не `transformers`) | **ДА, но не через `transformers`**: нужен `python-doctr`; в `transformers` класса PARSeq нет | оценка: ViT+AR-декодер, средняя скорость | оценка 6–10 ГБ | SynthText + реальные датасеты | см. [arXiv:2207.06966](https://arxiv.org/abs/2207.06966) | 10 478 / 14 (порт) | 2024-01-04 (порт) |
| 16 | [`graycat660/doctr-crnn-vgg16-bn-russian-onnx`](https://huggingface.co/graycat660/doctr-crnn-vgg16-bn-russian-onnx) | ru+en CRNN, ONNX | ~10–20 M (не измерял) | Apache-2.0 (по тегу карточки) | ONNX | **НЕТ** (ONNX) | — | — | ru+en CRNN | — | 136 / 0 | 2026-10-05 |
| 17 | [`zenoda/trocr-captcha-killer`](https://huggingface.co/zenoda/trocr-captcha-killer), [`FlanChanXwO/phpwind-captcha-ocr`](https://huggingface.co/FlanChanXwO/phpwind-captcha-ocr), [`AndresDev/captCHAD`](https://huggingface.co/AndresDev/captCHAD), [`04RR/Florence-base-Captcha`](https://huggingface.co/04RR/Florence-base-Captcha) | captcha-специфичные, разные движки | — | не объявлена / Apache-2.0 / MIT | .bin, ONNX, safetensors | преимущественно нет | — | — | разные | на **наших** данных: captCHAD **0.000**, phpwind **0.000** (`HANDOVER.md` §1.3) | 78 / 4; 16 / 2; —; 20 / 0 | 2023-07-03; 2026-08-04; —; 2024-08-13 |

**Строки таблицы без явно объявленной лицензии (проверить перед публикацией на HF).**
Тег `license:` на карточке HF отсутствует у: `microsoft/trocr-base-printed`,
`microsoft/trocr-small-printed`, `microsoft/trocr-base-stage1`,
`microsoft/trocr-small-handwritten`, `microsoft/trocr-small-stage1`,
`hongyusir/trocr-base-printed_captcha_ocr`. У `microsoft/trocr-base-handwritten` — MIT.
У всех `PaddlePaddle/*` — Apache-2.0; у `anuashok/ocr-captcha-v3` — Apache-2.0;
у `Graf-J/*` — MIT; у `tomofi/trocr-captcha` и `DunnBC22/…` — MIT;
у `stepfun-ai/GOT-OCR2_0`, `PaddlePaddle/PaddleOCR-VL*`, `Qwen/Qwen*-VL*` — Apache-2.0;
у PARSeq-порта `Felix92/…` — Apache-2.0 (оригинал `baud-xl/parseq` — MIT);
у `graycat660/doctr-crnn-…` — Apache-2.0 (тег карточки).
Перед выкладкой дообученной модели лицензию base TrOCR надо подтвердить отдельно
(см. <https://github.com/microsoft/unilm/tree/master/trocr>) — иначе публиковать нельзя.

**TinyOCR.** Отдельной HF-карточки «TinyOCR» нет: поиск HF по `TinyOCR` даёт единственную
выдачу — [`krotreaksmey/TinyOCRkhmer`](https://huggingface.co/krotreaksmey/TinyOCRkhmer)
(Apache-2.0, 67 загрузок, 0 лайков, `parseq`-архитектура), а сам TinyOCR — это **GitHub-проект**
(см. [выдачу поиска](https://lite.duckduckgo.com/lite/?q=TinyOCR+huggingface+model+repo)),
а не веса на HF. Как кандидат на дообучение в нашем окне — **не рассматриваем** (нет
трансформерс-совместимых весов на HF).

---

## 3. Разбор главных кандидатов

### 3.1 PP-OCRv6 (PaddlePaddle) — семейство, ради которого всё и затевалось

**Что это.** Линейка из трёх уровней распознавания (medium 19 M / small 5.3 M / tiny 1.1 M):
backbone LCNetV4 + шея EncoderWithLightSVTR + многоголовая декодирующая часть CTC+NRTR.
Заявленная точность (карточка `PP-OCRv6_medium_rec`, [arXiv:2606.13108](https://arxiv.org/abs/2606.13108)):
rec W-Avg **83.2 %** у medium (Printed EN **94.1 %**, Handwritten EN 67.8 %, Confusable 64.9 %),
81.3 % у small, 73.5 % у tiny. Поддержка 50 языков.

**Почему это лучший кандидат именно для нас.**

* **Это единственная готовая модель, которая уже «видела» наш домен.** Наши измерения
  (`HANDOVER.md` §1.3, `reports/CAPTCHA_SYSTEM_OVERVIEW.md`): **PP-OCRv6_medium_rec = 0.40**
  exact-match по полосам `roi`, EasyOCR — 0.115, `anuashok/ocr-captcha-v3` — 0.077, наш CRNN
  с нуля — 0.000 на невиданных типах. Разрыв в 3.5 раза с ближайшим конкурентом и в ∞ раз
  с собственным baseline.
* **Есть PyTorch-путь без paddle.** `PaddlePaddle/PP-OCRv6_*_rec_safetensors` — это
  **трансформерс-совместимые** репозитории: `config.json` с `model_type: pp_ocrv6_small_rec`
  (medium) / `pp_ocrv6_tiny_rec` (tiny), `model.safetensors`, `preprocessor_config.json`.
  В `transformers 5.19.0` есть готовые классы — проверено: `dir(transformers)` содержит
  `PPOCRV6SmallRecForTextRecognition`, `PPOCRV6TinyRecForTextRecognition`,
  `PPOCRV6MediumDetForObjectDetection`, `PPOCRV6SmallDetForObjectDetection`,
  `PPOCRV5MobileRecForTextRecognition`, `PPOCRV5ServerRecForTextRecognition`.
  Проверено и фактической загрузкой (§6): все три rec-модели грузятся и считают forward+backward.
* **Кириллица в одном словаре.** `inference.yml` содержит `character_dict` из 18 709 символов
  (совпадает с `head_out_channels=18710`, blank = 0) — включая `0-9`, `A-Z`, `a-z`,
  кириллицу (`а…я`, `ё`) и спецсимволы. Значит **одна** дообученная модель покрывает и 8
  кириллических типов из 46, а `charset` маскируется по типу, как уже придумано в `HANDOVER.md` §3.4.
  У `tiny_rec` словарь меньше (6 906) — там кириллица может не поместиться, это риск (§7).

**Минусы (честно).**

* **В `transformers` нет встроенного лосса и нет токенизатора.** `PPOCRV6SmallRecForTextRecognition.forward`
  возвращает вероятности `(B, T, 18710)` и **не считает loss**; `labels` не принимает.
  Значит тренеру придётся: (а) взять `character_dict` из `inference.yml` (или свой словарь),
  (б) написать 10 строк на `torch.nn.CTCLoss(blank=0, zero_infinity=True)` с
  `log_probs` из softmax-выхода, (в) настроить `input_lengths` (после `avg_pool2d(3,2)`
  длина по ширине = W/8). Это ~50 строк кода, но это **свой** код, а не `Trainer` из коробки.
* **У medium_rec `config.json` стоит `model_type: pp_ocrv6_small_rec`** (в `transformers` класса
  `pp_ocrv6_medium_rec` вообще нет — `import transformers.models.pp_ocrv6_medium_rec` → ModuleNotFoundError).
  Модель при этом грузится и работает: архитектура параметризуется `backbone_config`
  (`hidden_size 192`, `mlp_ratio 4.0`, `stem_channels [3,64,128]`), и сверка конфигов medium/small
  показывает, что отличаются именно ширины и глубины. Но это **ошибка метаданных на стороне
  PaddlePaddle**, и её надо учитывать при обновлении transformers.
* **Вход 48×W, а у нас полоса ~32 px по глифу.** Нужно пересчитать масштаб «высота глифа 32 px»
  на «высота картинки 48 px» (т.е. наш `train/`-пайплайн требует правки `--glyph-height 32 → 48`),
  иначе модель получит не тот масштаб, на котором была обучена.
* **Опубликованные метрики — на индустриальных бенчмарках Paddle, а не на капчах.** Прямых
  измерений PP-OCRv6 на капчах в публичных источниках я не нашёл.

### 3.2 TrOCR base/small printed + handwritten + stage1

**Что это.** Encoder-decoder: BEiT-визуальный энкодер + RoBERTa-декодер, обученный сначала
на «stage-1» (неразмеченные документы), потом fine-tune на SROIE (printed) / IAM (handwritten)
— [arXiv:2109.10282](https://arxiv.org/abs/2109.10282). Размеры: base **333 331 200**
(проверено по `safetensors.total`), small **61 448 832**.

**Плюсы для нас.** Это **эталон «готовой модели»** в смысле задачи пользователя: ровно то,
что обычно называют «pretrained OCR-моделью». Есть готовый `Trainer`-совместимый путь
(`TrOCRForCausalLM` + `TrOCRProcessor`, loss считается сам, CTC/seq2seq), есть десятки
капча-дообученных форков (строки 9–10 таблицы).

**Минусы для нас — существенные.**

* **Разрешение 384×384.** Наши полосы — короткие строки 3–8 символов; 384×384 для них — это
  ~10–20 «лишних» строк по высоте и заметный апскейл. Модель на наших данных не мерялась.
* **Скорость.** Оценка 10–25 img/s для base (основа — ~1.15 TFLOP на изображение при 577
  токенах и 333 M параметров, ÷ эффективных ~30–60 TFLOPS с TF32/AMP) ⇒ эпоха по 3100
  картинкам **2–5 минут**, 60 эпох **2–5 часов** — то есть в окно 1–2 часа base не укладывается
  без уменьшения числа эпох. small — в ~4 раза дешевле, но там другая проблема: **маленькая
  модель на 4600 картинках на 46 стилей почти наверняка запомнит, а не обобщит** (ровно тот
  эффект, который мы уже измерили для нашего CRNN: 1.000 на обученных типах, 0.000 на невиданных).
* **Токенизатор требует `tiktoken` в transformers 5.19.** Это не теория: прогон
  `TrOCRProcessor.from_pretrained("microsoft/trocr-small-printed")` на этой машине упал с
  `ValueError: tiktoken is required to read a tiktoken file` (§6). Ставить `tiktoken` в
  `.venv-gpu` я не мог (папка вне моей зоны ответственности) — это пункт для оркестратора.
* **Лицензия `trocr-base-printed` в карточке не объявлена** (тега `license:` нет; у
  `trocr-base-handwritten` — MIT). Для публикации на HF это надо уточнить по
  [microsoft/unilm](https://github.com/microsoft/unilm/tree/master/trocr) и вписать явно.
* **Капта-форки плохие.** `anuashok/ocr-captcha-v3` — 61 323 загрузки, Apache-2.0, CER 0.0139
  на своём датасете, но на **наших** картинках — **0.077**. `DunnBC22/…`, `hongyusir/…`,
  `tomofi/…` — по `HANDOVER.md` §1.3 **не грузятся под transformers 5.x** (у `hongyusir`
  метрик нет вообще, 11 загрузок; у `tomofi` — только `pytorch_model.bin`).

### 3.3 PP-OCRv4 / v5

PP-OCRv4 — в HF нет официальных `safetensors` для rec (есть paddle `inference.pdiparams`),
в transformers 5.19 классов v4 нет. **Для дообучения в PyTorch — не кандидат.**
PP-OCRv5 — классы `PPOCRV5MobileRecForTextRecognition` / `PPOCRV5ServerRecForTextRecognition`
есть, но официальные rec-репозитории v5 (`PP-OCRv5_mobile_rec`, `latin_…`, `en_…`,
`PP-OCRv5_server_rec`) выложены **только в paddle-формате** (`inference.pdiparams`);
safetensors-портов для rec я не нашёл (проверял выдачу HF-поиска по `PP-OCRv5` — там
`inference.pdiparams` и ONNX). Уже в нашем харнессе есть ONNX-сборки, включая отдельные
`latin_` и `cyrillic_` (`bench/bench_models.py`).
**PP-OCRv5 — запасной путь, если для v6 medium не хватит времени; по качеству v6 выше.**

### 3.4 PaddleOCR-VL (1.6 / 1.5 / v1)

**Что это.** VLM на базе ERNIE-4.5-0.3B + собственный визуальный энкодер, ~0.9 B, Apache-2.0.
В `transformers 5.19` есть `PaddleOCRVLForConditionalGeneration` и `PaddleOCRVLProcessor`.
Тянится через `paddleocr` с `--engine transformers` (карточка прямо это показывает).

**Плюсы.** Самая свежая и самая «умная» модель в списке: понимает layout, таблицы, формулы,
печатает и рукописный текст, 100+ языков. Для капт с кириллицей и математикой
(наши арифметические типы из группы B!) — потенциально сильная.

**Минусы.** 0.9 B параметров: fp16-веса 1.8 ГБ + AdamW 3.6 ГБ + градиенты 1.8 ГБ + активации →
**в 11.8 ГБ не влезает** даже с LoRA без offload. Плюс это задача «документ → разметка»,
а не «строка 3–8 символов»: генеративный декодер на коротких токенах медленный и шумный,
и метрика exact-match по капте для VLM считается иначе. **В окно 1–2 ч на 1080 Ti — нет.**
Роль в проекте: разумный «потолок» на будущее (и как раз тот вариант, когда появится GPU на 24+ ГБ).

### 3.5 GOT-OCR2.0

**Что это.** 580 M VLM для OCR документов (StepFun), Apache-2.0, 348 129 загрузок, 1 574 лайка —
самая «тяжёлая», но самая известная из OCR-VLM. В transformers 5.19 есть
`GotOcr2ForConditionalGeneration` (нативно, без `custom_code` для `-hf`-репо).

**Плюсы/минусы для нас.** Модель универсальная, но это **документный** OCR: на каптах
(короткие искажённые строки, шум, помехи) её предобучение не помогает так, как помогает
индустриальное распознавание строк PP-OCR. При этом она в 30 раз дороже PP-OCRv6 по
VRAM и в 30–100 раз по скорости. **Как кандидат на дообучение в наше окно — не проходит.**

### 3.6 Qwen2.5-VL / Qwen3-VL (small/2B/4B/8B)

**Что это.** Общие VLM (2 B…8 B), Apache-2.0, миллионы загрузок. В transformers 5.19 есть
`Qwen2_5_VLForConditionalGeneration` и `Qwen3VLForConditionalGeneration`.

**Плюсы.** Универсальность (может и капту, и арифметику, и объяснить), есть LoRA-путь,
`Qwen3-VL-2B-Instruct` (2 037 547 загрузок) — единственный, который теоретически влезает
в 11.8 ГБ с LoRA + grad-checkpointing.

**Минусы.** Полное дообучение 3–4 B не влезает; LoRA-дообучение VLM на 3100 картинках за
1–2 часа на 1080 Ti — это 1–3 img/s, то есть **10–15 эпох максимум**, а капта требует
больше. Плюс генеративная декодировка: на 8-символьной строке токенизация/геммы дают
лишние ошибки, а exact-match по капте с VLM — шумная метрика. **В окно 1–2 ч — нет.**
Как и PaddleOCR-VL, это «если появится мощная GPU».

### 3.7 PARSeq

**Что это.** Авторегрессивный scene-text-рекогнайзер с контекстным декодером
([arXiv:2207.06966](https://arxiv.org/abs/2207.06966), MIT), репозиторий
[`baud-xl/parseq`](https://github.com/baud-xl/parseq) — веса `.pth`, **не на HF**;
на HF есть порт под docTR: [`Felix92/doctr-torch-parseq-multilingual-v1`](https://huggingface.co/Felix92/doctr-torch-parseq-multilingual-v1)
(Apache-2.0, 10 478 загрузок) и ONNX-порт `onnxtr-parseq`.

**Плюсы.** Контекстный декодер PARSeq — одна из сильнейших архитектур для строк; порт мультиязычный.
**Минусы для нас.** (а) В `transformers` класса PARSeq **нет** — дообучение пойдёт через
`python-doctr`, то есть это уже не «модель из HF + Trainer», а отдельный фреймворк;
(б) порты — в основном en/fr/da и т.п., кириллица в нашем `character_dict`-мире неочевидна;
(в) скорость ниже PP-OCRv6 в разы. **Не первый выбор, но полезен как «вторая opinion» в
ансамбле или как источник идей (итеративный декодер).**

### 3.8 Капта-специфичные модели HF (строка 9–11, 17 таблицы)

* [`anuashok/ocr-captcha-v3`](https://huggingface.co/anuashok/ocr-captcha-v3) — TrOCR-base,
  Apache-2.0, **61 323 загрузки**, карточка публикует **CER 0.0139** и гиперпараметры
  (7 эпох, batch 16, lr 1.5e-5, beams 2) — это лучше документированная капта-модель в HF.
  Но на наших данных — **0.077**. Причина: чужой `custom-captcha-dataset` (другие шрифты, другие
  искажения), а наш домен — 46 разных плагинов с кривыми, штрихами, цветами.
  **Ценность: как инициализация для дообучения** (TrOCR-энкодер уже видел капты) —
  но она тяжелее PP-OCRv6 в 16 раз и в transformers 5.x не грузится «из коробки» без `tiktoken`.
* [`Graf-J/captcha-crnn-finetuned`](https://huggingface.co/Graf-J/captcha-crnn-finetuned) —
  **3 571 903** параметра, MIT, safetensors, `custom_code` (`CaptchaCRNN`), обучен на
  [`hammer888/captcha-data`](https://huggingface.co/datasets/hammer888/captcha-data).
  На наших 40 сэмплах даёт **acc 0.100 / CER 0.638** — лучше нашего CRNN с нуля (0.000),
  но в 4 раза хуже PP-OCRv6 (0.40). Ценность: дёшево, маленькая, MIT → хороший кандидат
  в **связку/ансамбль** и как «дешёвый фолд-бейчлайн».
* `captCHAD`, `phpwind-captcha-ocr`, `keras-io/ocr-for-captcha`, `04RR/Florence-base-Captcha` —
  на наших данных 0.000 / не грузятся → **в дообучении не рассматриваем**.

---

## 4. Ранжированная рекомендация

| Место | Модель | Почему | Что мешает |
|---|---|---|---|
| **1** | **`PaddlePaddle/PP-OCRv6_medium_rec_safetensors`** (Apache-2.0, 19.1 M) | Лучшая измеренная база на наших данных (**0.40**, в 3.5 раза выше ближайшей); нативный PyTorch-путь в transformers 5.19; **101 img/s** и **2.34 ГБ** при batch 16 → 60 эпох по 3100 картинкам ≈ 31 мин, 4-фолд ≈ 2 ч; словарь 18 709 символов покрывает и кириллицу; Apache-2.0 → публикуем на HF без проблем | Нет готового лосса (писать CTC, ~50 строк); `model_type` medium'а в карточке = `pp_ocrv6_small_rec` (баг метаданных, работает); вход 48 px, а не 32 px |
| **2** | **`PaddlePaddle/PP-OCRv6_small_rec_safetensors`** (5.3 M) | Тот же код, **170 img/s**, **1.11 ГБ** → 4-фолд за 40 мин; удобен как быстрый пилот и как «лёгкая» публикация на HF; официально W-Avg 81.3 % (−1.9 п.п. к medium) | Чуть ниже точность; при 5.3 M риск переобучения на 46 стилях выше, чем у medium |
| **3** | **`PaddlePaddle/PP-OCRv6_tiny_rec_safetensors`** (1.1 M) | **325 img/s**, 0.35 ГБ — единственный вариант, который прогоняет 4-фолд за 15 минут и позволяет делать много абляций | Словарь 6 906 — **кириллица может не поместиться** (риск, проверять в первую очередь); W-Avg 73.5 %, риск переобучения максимальный |
| **4** | **`Graf-J/captcha-crnn-finetuned`** (3.6 M, MIT) | Уже измерен на наших данных (0.100), маленький, MIT, есть готовый чекпоинт; хорош как «дешёвый второй голос» и как baseline в отчёте | `custom_code` чужого репозитория (чинить под transformers 5.19); существенно хуже PP-OCRv6 |
| **5** | **`microsoft/trocr-base-printed` / `trocr-small-printed`** | «Классика pretrained OCR», нативный `Trainer`, seq2seq-лосс из коробки, можно дообучать через `Trainer` | 384×384, 333 M, оценка 10–25 img/s → не укладывается в окно; **нужен `tiktoken`** (падение зафиксировано); лицензия не объявлена; на наших данных не мерялся |
| **6** | `anuashok/ocr-captcha-v3` | 61 323 загрузки, Apache-2.0, документированный CER 0.0139 на каптах — хорошая инициализация «по смыслу» | На наших данных 0.077; 333 M; нет safetensors-приложений, нужны те же `tiktoken`/починки; 4-кратный проигрыш по скорости |
| **7** | PARSeq-порт (`Felix92/doctr-torch-parseq-multilingual-v1`) | Сильная контекстная архитектура, Apache-2.0 | Не `transformers` — отдельный фреймворк; нет кириллической сборки; дороже PP-OCRv6 |
| **8** | `PaddleOCR-VL-1.6`, `GOT-OCR2.0`, `Qwen3-VL-2B/4B` | Самая широкая «универсальность» (кириллица, арифметика, объяснение) | 0.9–4 B: не влезают в 11.8 ГБ (без LoRA/offload), 1–15 img/s, окно 1–2 ч не закрывают. Оставить на «большую GPU» |

**Вариант «если бы был paddle / другая GPU».**

* *Если бы был paddlepaddle* (его нет под Windows + Python 3.14; чинить можно только через
  отдельный venv на `Python312`, `C:\Users\Title\AppData\Local\Programs\Python\Python312\python.exe`):
  PP-OCRv6 medium/small/tiny обучались бы «родным» пайплайном PaddleOCR (собственный
  `MultiLabelEncode`, `NRTRLabelEncode`, готовый CTC-рецепт) — это убирает работу с
  самописным лоссом, но **не даёт выигрыша в качестве**: те же веса.
  Для VLM — `PaddleOCR-VL-1.6` становится реально дообучаемым (0.9 B на 24 ГБ + LoRA).
* *Если бы была другая GPU* (≥24 ГБ, окно 4–8 ч): `Qwen/Qwen3-VL-4B-Instruct` + LoRA
  (Apache-2.0) — единственный вариант, который «понимает» арифметические типы из группы B
  и русские слова-числа без словаря; либо `microsoft/trocr-base-printed` на 3–4 эпохах
  (тогда скорость уже не главный аргумент). На этой машине — **нет**.

---

## 5. Три команды проверки перед долгим прогоном

> Общий контекст: кэш HF в этой машине **недоступен для записи** из дочерних процессов
> (`C:\Users\Title\.cache\huggingface` → `PermissionError`). Поэтому **все три команды**
> обязаны начинаться с установки `HF_HOME`/`HF_HUB_CACHE` на локальную папку репозитория
> (она уже создана: `C:\Users\Title\Projects\CaptchaOCR\.hf-cache`).
> Пути ниже — под этот репозиторий; выполнять из корня `C:\Users\Title\Projects\CaptchaOCR`.

### Команда 1 — окружение + весá грузятся в `transformers`

```powershell
cd C:\Users\Title\Projects\CaptchaOCR
$env:HF_HOME="C:\Users\Title\Projects\CaptchaOCR\.hf-cache"; $env:HF_HUB_CACHE="C:\Users\Title\Projects\CaptchaOCR\.hf-cache\hub"
.venv-gpu\Scripts\python.exe -c "import torch,transformers;print('torch',torch.__version__,'tfm',transformers.__version__);print('cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0),torch.cuda.get_device_capability(0));print('vram_GB',round(torch.cuda.get_device_properties(0).total_memory/1024**3,2));from transformers import PPOCRV6SmallRecForTextRecognition as M;m=M.from_pretrained('PaddlePaddle/PP-OCRv6_medium_rec_safetensors');print('params',sum(p.numel() for p in m.parameters()));print('classes',m.config.head_out_channels)"
```

**Что должно быть:** `torch 2.14.1+cu126`, `tfm 5.19.0`, `cuda True`, `NVIDIA GeForce GTX 1080 Ti`,
`(6, 1)`, `vram_GB 11.0`, `params 19134326`, `classes 18710`.
**Если падает `PermissionError` на `huggingface/hub`** — не выставлен `HF_HOME` (см. выше).
**Если падает `ModuleNotFoundError: transformers.models.pp_ocrv6_medium_rec`** — так и должно
быть: класса medium нет, medium грузится через `PPOCRV6SmallRecForTextRecognition`
(см. §3.1, это не ошибка).

### Команда 2 — проверка памяти GPU и «чистого» состояния карты

```powershell
cd C:\Users\Title\Projects\CaptchaOCR
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,driver_version --format=csv
.venv-gpu\Scripts\python.exe -c "import torch;torch.cuda.init();print('free_GB',round(torch.cuda.mem_get_info()[0]/1024**3,2),'total_GB',round(torch.cuda.mem_get_info()[1]/1024**3,2))"
```

**Что должно быть:** `memory.total` ≈ 11 762 MiB (11.8 ГБ), `memory.used` ≈ 0 (перед стартом),
`driver_version` 581.57, `free_GB` ≈ 11.0. Если `memory.used` большой — на карте висит
чужой процесс, освободить до старта.

### Команда 3 — пробный forward + backward с таймингом (то, что запускать дольше всего)

```powershell
cd C:\Users\Title\Projects\CaptchaOCR
$env:HF_HOME="C:\Users\Title\Projects\CaptchaOCR\.hf-cache"; $env:HF_HUB_CACHE="C:\Users\Title\Projects\CaptchaOCR\.hf-cache\hub"
$env:PYTHONIOENCODING="utf-8"
.venv-gpu\Scripts\python.exe -c "import torch,torch.nn as nn,numpy as np;from PIL import Image;from transformers import AutoImageProcessor,PPOCRV6SmallRecForTextRecognition as M;repo='PaddlePaddle/PP-OCRv6_medium_rec_safetensors';m=M.from_pretrained(repo).cuda().train();p=AutoImageProcessor.from_pretrained(repo);opt=torch.optim.AdamW(m.parameters(),lr=1e-4);ctc=nn.CTCLoss(blank=0,zero_infinity=True);ims=[Image.fromarray((np.random.rand(48,320,3)*255).astype('uint8')) for _ in range(16)];lb=torch.randint(1,18710,(16,5));ln=torch.full((16,),5);s=0;import time;t0=time.time();[s for _ in range(0)];exec('for i in range(7):\n px=p(images=ims,return_tensors=\"pt\").pixel_values.cuda()\n o=m(pixel_values=px)\n lp=torch.log(o.last_hidden_state.clamp_min(1e-8)).permute(1,0,2)\n l=ctc(lp,lb.cuda(),torch.full((16,),lp.shape[0]),ln)\n l.backward();opt.step();opt.zero_grad()');torch.cuda.synchronize();dt=(time.time()-t0)/7;print('img_per_s',round(16/dt,1));print('peak_vram_GB',round(torch.cuda.max_memory_allocated()/1024**3,2));print('ok')"
```

**Что должно быть:** `img_per_s` ≈ 90–110, `peak_vram_GB` ≈ 2.3, `ok`.
Это ровно те цифры, что в §1; если они сходятся — можно запускать длинный прогон.
(Полный, «честный» скрипт этой проверки лежит в `$env:TEMP\ppocr_bench.py`; он же прогоняет
все три уровня small/medium/tiny и печатает то же самое.)

---

## 6. Проверено руками (фактический вывод)

Все команды выполнены на этой машине 2026-10-22, интерпретатор
`C:\Users\Title\Projects\CaptchaOCR\.venv-gpu\Scripts\python.exe`.

**6.1. Окружение (выход команды 1, до загрузки весов):**

```
python 3.14.5
torch 2.14.1+cu126
transformers 5.19.0
cuda_available True
device NVIDIA GeForce GTX 1080 Ti
capability (6, 1)
total_mem_GB 11.0
TrOCRForCausalLM True
TrOCRProcessor True
VisionEncoderDecoderModel True
```

**6.2. Наличие PP-OCR-классов в установленном transformers 5.19.0** (выдержка из
`dir(transformers)`; полный список — 200+ имён, релевантные):

```
'PPOCRV5MobileRecForTextRecognition', 'PPOCRV5ServerRecForTextRecognition',
'PPOCRV6MediumDetForObjectDetection', 'PPOCRV6SmallDetForObjectDetection',
'PPOCRV6SmallRecConfig', 'PPOCRV6SmallRecForTextRecognition', 'PPOCRV6SmallRecImageProcessor',
'PPOCRV6TinyRecForTextRecognition',
'PaddleOCRVLForConditionalGeneration', 'GotOcr2ForConditionalGeneration',
'Qwen2_5_VLForConditionalGeneration', 'Qwen3VLForConditionalGeneration',
'TrOCRForCausalLM', 'TrOCRProcessor', 'VisionEncoderDecoderModel'
```

**6.3. Реальный forward+backward на PP-OCRv6 (batch 16, вход 48×320, AdamW, ручной CTC-лосс).**
Скрипт: `$env:TEMP\ppocr_bench.py`; запускался с
`HF_HOME=C:\Users\Title\Projects\CaptchaOCR\.hf-cache`. Фактический вывод:

```
REPO PaddlePaddle/PP-OCRv6_small_rec_safetensors CLASS PPOCRV6SmallRecForTextRecognition
load_seconds 5.9
params 5275238
model_type pp_ocrv6_small_rec head_out_channels 18710
proc_size SizeDict(height=48, width=320, ...) max_image_width 3200
pixel_values_shape (16, 3, 48, 320)
loss 6.346
step_seconds 0.094
img_per_s 170.0
peak_vram_alloc_GB 1.11
peak_vram_reserved_GB 1.19
--------------------------------------------------------------------
REPO PaddlePaddle/PP-OCRv6_medium_rec_safetensors CLASS PPOCRV6SmallRecForTextRecognition
load_seconds 11.7
params 19134326
model_type pp_ocrv6_small_rec head_out_channels 18710
proc_size SizeDict(height=48, width=320, ...) max_image_width 3200
pixel_values_shape (16, 3, 48, 320)
loss 4.3
step_seconds 0.159
img_per_s 100.9
peak_vram_alloc_GB 2.34
peak_vram_reserved_GB 2.6
--------------------------------------------------------------------
REPO PaddlePaddle/PP-OCRv6_tiny_rec_safetensors CLASS PPOCRV6TinyRecForTextRecognition
load_seconds 4.0
params 1106702
model_type pp_ocrv6_tiny_rec head_out_channels 6906
proc_size SizeDict(height=48, width=320, ...) max_image_width 3200
pixel_values_shape (16, 3, 48, 320)
loss 9.7157
step_seconds 0.049
img_per_s 324.9
peak_vram_alloc_GB 0.35
peak_vram_reserved_GB 2.6
```

Три важных вывода из этого вывода:
* **medium_rec грузится и считает** через класс `PPOCRV6SmallRecForTextRecognition`
  (у transformers нет `pp_ocrv6_medium_rec`), параметров 19 134 326 — совпадает с
  `safetensors.total` = 19 176 118 (разница — буферы BatchNorm);
* **словарь tiny — 6 906**, а не 18 710 ⇒ кириллица в нём может отсутствовать (риск §7);
* **потери не считаются моделью** — лосс в скрипте считался вручную (`nn.CTCLoss`), модель
  вернула только вероятности.

**6.4. TrOCR: загрузка процессора падает без `tiktoken`** (фактический хвост трейсбека):

```
File "...\transformers\tokenization_utils_tokenizers.py", line 225, in convert_to_native_format
    local_kwargs = cls._convert_from_tiktoken(vocab_file, local_kwargs)
ValueError: `tiktoken` is required to read a `tiktoken` file. Install it with `pip install tiktoken`.
```

То есть `TrOCRProcessor.from_pretrained("microsoft/trocr-small-printed")` в этом окружении
**не работает** без `pip install tiktoken` (поставить в `.venv-gpu` я не мог — папка вне
моего списка разрешённых файлов; это пункт для оркестратора).
По той же причине **скорость TrOCR на 1080 Ti мной не измерена** — оценки в таблице §2/§3.2
опираются на GFLOPs, а не на замер.

**6.5. Проверка словаря (первые и нужные символы `inference.yml`):** `character_dict` содержит
`! " # $ % & ' ( ) * + , - . / : ; < = > ? @ [ \ ] ^ _ \` { | } ~ 0-9 A-Z a-z`, далее
латиница с диакритикой, кириллица (`а…я`, `ё`), CJK и символы; **всего 18 709 символов**,
что совпадает с `head_out_channels=18710` (индекс 0 — blank).

---

## 7. Риски (что может не сработать)

1. **Свой CTC-лосс вместо готового Trainer.** `PPOCRV6*ForTextRecognition.forward` не принимает
   `labels` и не считает loss. Тренеру придётся реализовать CTC сам и согласовать:
   `blank=0`, `zero_infinity=True`, `input_lengths` = число выходных кадров (после
   `avg_pool2d(3,2)` → ширина/8), `target_lengths` = длина строки. Ошибка в `input_lengths`
   даёт «тихий» loss ≈ 0 или NaN — страховка: сверять число кадров T с `logits.shape[1]`.
   **Готовые CTC-рецепты Paddle (`NRTRLabelEncode`) использовать нельзя** — только свой код.
2. **Разрешение.** PP-OCRv6 ждёт высоту 48 px; наш пайплайн (`train/AGENTS.md`, `--glyph-height 32`)
   придётся перенастроить на 48, иначе модель получит непривычный масштаб глифов.
3. **Кириллица в tiny.** `head_out_channels=6906` у tiny против 18 710 у small/medium —
   надо **первым делом** проверить, есть ли `а…я` в словаре tiny (в small/medium — есть, §6.5).
   Если нет → tiny отпадает для 8 кириллических типов из 46.
4. **`model_type` medium_rec = `pp_ocrv6_small_rec`** — ошибка метаданных на стороне PaddlePaddle.
   Если в будущей версии transformers появится класс `pp_ocrv6_medium_rec`, пути нагрузки
   надо будет перепроверить (сейчас работает, §6.3).
5. **Токенизаторы TrOCR требуют `tiktoken`** — до установки не работают ни `TrOCRProcessor`,
   ни любые TrOCR-дообученные капта-модели из строк 9–10 таблицы. У `hongyusir/…` метрик
   вообще нет, у `DunnBC22/…` и `tomofi/…` нет safetensors, и по `HANDOVER.md` §1.3 они
   **не грузятся под transformers 5.x** — то есть дообчать их «из коробки» не выйдет.
6. **paddlepaddle под Windows/Python 3.14 не ставится** (нет колес) ⇒ paddle-путь (родной
   рецепт обучения PP-OCR) недоступен без отдельного venv на `Python312`. Наш выбор
   (safetensors + transformers) от этого страдает меньше всего — это его главный плюс.
7. **Лицензии.** PP-OCRv6 — Apache-2.0 (публикуем свободно, но в карточке дообученной модели
   надо указать исходную модель и её лицензию). `trocr-base-printed` — лицензия **не объявлена**
   в карточке: перед публикацией TrOCR-дообученной модели лицензию надо подтвердить отдельно.
   `Graf-J/*` — MIT (требует указать авторство). Данные: у sonar/China2B2T/AnBot — GPL-3.0,
   у LimboFilter — AGPL-3.0, у трёх плагинов лицензии нет ⇒ **датасет нельзя выкладывать одним
   монолитом**, нужны репозитории по семействам лицензий (`HANDOVER.md` §7).
8. **Обобщение на невиданный стиль плагина — не гарантировано.** Дообчение PP-OCRv6 может
   повторить судьбу нашего CRNN (1.000 на обученных типах, 0.000 на невиданных). Единственная
   защита — **type-held-out валидация** (4-фолд по типам, метрика per-type + медиана),
   а не random split (`train/AGENTS.md` §3). Первый прогон должен быть фолдом, а не «обучил на всём».
9. **Данные, а не модель, могут быть узким местом.** 4600 картинок на 46 типов — мало;
   PP-OCRv6 при 19 M параметров склонна к запоминанию. План-«страховка»:
   сначала `small_rec` (5.3 M) на фолде, и только если обобщение есть — `medium_rec`.
10. **Кэш HF.** Запись в `C:\Users\Title\.cache\huggingface` из дочерних процессов запрещена
    (`PermissionError`) ⇒ все запуски обучения обязаны выставлять `HF_HOME`/`HF_HUB_CACHE`
    на `C:\Users\Title\Projects\CaptchaOCR\.hf-cache`. Папка `.hf-cache/` сейчас **не** в
    `.gitignore` и видна в `git status` как untracked — оркестратору стоит её добавить
    в `.gitignore` или удалить перед коммитом.

---

## 8. Что НЕ проверено (явно)

* **Скорость и VRAM для TrOCR, GOT-OCR2.0, PaddleOCR-VL, Qwen-VL, PARSeq** — не измерены;
  в таблице это **оценки**: TrOCR — по формуле fwd+bwd FLOPs (≈1.15 TFLOP/изображение при
  577 токенах и 333 M параметров) при разумной эффективности 30–60 TFLOPS (TF32/AMP);
  VLM — по размеру весов и типичной скорости генеративного декодера.
* **Точность кандидатов на наших данных** — измерена только у PP-OCRv6_medium_rec (0.40),
  EasyOCR (0.115), `anuashok/ocr-captcha-v3` (0.077), `Graf-J/captcha-crnn-finetuned`
  (0.100/0.638) — по данным `HANDOVER.md` §1.3 и §6.5. **Ни TrOCR, ни PARSeq, ни VLM
  на наших 4600 картинках мы не гоняли** — их «качество на каптах» в этом отчёте
  основано только на их собственных карточках и на отсутствии у нас измерений.
* **Параметры TrOCR-base/small-handwritten и stage1** — не считал (взял ≈333 M / ≈61 M по
  архитектуре); **параметры VLM-ов и PARSeq** — не считал.
* **Полное дообучение** (реальный тренировочный цикл, первая эпоха, кривая лосса,
  type-held-out точность) — **не запускал**: это задача следующего агента, у меня был
  только обзор + проверочные прогоны. Поэтому все «ожидаемые» цифры точности в §4 —
  это перенос опубликованных метрик моделей, а не наши измерения.
* **PaddleOCR-VL / Qwen-VL в transformers 5.19** — наличие классов проверил, но загрузку
  весов и инференс не делал (модели 0.9–4 B, скачивание не влезает в бюджет).
* **`tiktoken` для TrOCR** не устанавливал (запрещено трогать `.venv-gpu`).

---

## 9. Ссылки (источники)

Модели и карточки:
<https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec> ·
<https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_safetensors> ·
<https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_onnx> ·
<https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec> ·
<https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec_safetensors> ·
<https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec_onnx> ·
<https://huggingface.co/PaddlePaddle/PP-OCRv6_tiny_rec> ·
<https://huggingface.co/PaddlePaddle/PP-OCRv6_tiny_rec_safetensors> ·
<https://huggingface.co/PaddlePaddle/PP-OCRv6_tiny_rec_onnx> ·
<https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec_onnx> ·
<https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec_onnx> ·
<https://huggingface.co/PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec_onnx> ·
<https://huggingface.co/microsoft/trocr-base-printed> ·
<https://huggingface.co/microsoft/trocr-small-printed> ·
<https://huggingface.co/microsoft/trocr-base-handwritten> ·
<https://huggingface.co/microsoft/trocr-base-stage1> ·
<https://huggingface.co/microsoft/trocr-small-handwritten> ·
<https://huggingface.co/microsoft/trocr-small-stage1> ·
<https://huggingface.co/anuashok/ocr-captcha-v3> ·
<https://huggingface.co/anuashok/ocr-captcha-v2> ·
<https://huggingface.co/DunnBC22/trocr-base-printed_captcha_ocr> ·
<https://huggingface.co/hongyusir/trocr-base-printed_captcha_ocr> ·
<https://huggingface.co/tomofi/trocr-captcha> ·
<https://huggingface.co/Graf-J/captcha-crnn-finetuned> ·
<https://huggingface.co/Graf-J/captcha-conv-transformer-finetuned> ·
<https://huggingface.co/Graf-J/captcha-crnn-base> ·
<https://huggingface.co/stepfun-ai/GOT-OCR2_0> ·
<https://huggingface.co/stepfun-ai/GOT-OCR-2.0-hf> ·
<https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6> ·
<https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5> ·
<https://huggingface.co/PaddlePaddle/PaddleOCR-VL> ·
<https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct> ·
<https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct> ·
<https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct> ·
<https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct> ·
<https://huggingface.co/Felix92/doctr-torch-parseq-multilingual-v1> ·
<https://huggingface.co/graycat660/doctr-crnn-vgg16-bn-russian-onnx> ·
<https://huggingface.co/zenoda/trocr-captcha-killer> ·
<https://huggingface.co/FlanChanXwO/phpwind-captcha-ocr> ·
<https://huggingface.co/04RR/Florence-base-Captcha> ·
<https://huggingface.co/krotreaksmey/TinyOCRkhmer> ·
<https://huggingface.co/datasets/hammer888/captcha-data>

Статьи, код и API:
<https://arxiv.org/abs/2606.13108> (PP-OCRv6) ·
<https://arxiv.org/abs/2109.10282> (TrOCR) ·
<https://arxiv.org/abs/2207.06966> (PARSeq) ·
<https://arxiv.org/abs/2409.01704> (GOT-OCR2.0) ·
<https://arxiv.org/abs/2510.14528> (PaddleOCR-VL v1) ·
<https://arxiv.org/abs/2601.21957> (PaddleOCR-VL-1.5) ·
<https://arxiv.org/abs/2606.03264> (PaddleOCR-VL-1.6) ·
<https://github.com/baud-xl/parseq> ·
<https://github.com/microsoft/unilm/tree/master/trocr> ·
<https://huggingface.co/docs/transformers/main/en/model_doc/pp_ocrv6> (страница есть только в `main`; в релизе v5.20.2 — 404) ·
<https://lite.duckduckgo.com/lite/?q=TinyOCR+huggingface+model+repo>

Внутренние источники проекта: `HANDOVER.md` §1.3 (базовые линии), §3.4 (модель), §6.5 (журнал);
`train/AGENTS.md` §3 (правила валидации); `reports/CAPTCHA_SYSTEM_OVERVIEW.md`;
`reports/MODEL_PLAN.md`; `bench/bench_models.py` (харнесс и список ONNX-бэкендов).
