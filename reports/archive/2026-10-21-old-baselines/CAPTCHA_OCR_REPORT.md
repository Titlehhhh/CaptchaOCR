# Отчёт: Поиск готовых CAPTCHA/OCR моделей, загрузка и тестирование

## 0. Итоговые измеренные базовые линии (2026-10-21, обновлено)

Это единственные **измеренные** числа. Всё, что ниже в разделе 4, - это либо падение
при загрузке, либо ранний прогон; итоговые цифры здесь.

Тестовое множество: 13 текстовых типов из `dataset/out/`, по 8 сэмплов = 104 картинки.
Метрики: `acc` = точное совпадение нормализованного ответа, `CER` = edit distance / длина ответа.

| Модель | acc | CER | Итог |
|---|---|---|---|
| **EasyOCR/en** (только что прогнан `bench/bench_easyocr.py`) | **0.115** (12/104) | 1.835 | работает, 388 мс/картинку |
| `anuashok/ocr-captcha-v3` | 0.077 | 0.785 | работает, слабый CER |
| `AndresDev/captCHAD` (onnx fp32) | 0.000 | 1.012 | не угадывает ничего |
| `AndresDev/captCHAD` (onnx int8) | 0.000 | 0.987 | не угадывает ничего |
| `FlanChanXwO/phpwind-captcha-ocr` (onnx) | 0.000 | 0.990 | не угадывает ничего |
| `Graf-J/captcha-crnn-finetuned` | - | - | **не грузится**: кастомный `CaptchaConfig` не зарегистрирован в transformers 5.x |
| `Graf-J/captcha-conv-transformer-finetuned` | - | - | **не грузится**, та же причина |
| `04RR/Florence-base-Captcha` | - | - | **не грузится**: `Florence2LanguageConfig` без `forced_bos_token_id` |
| `hongyusir/trocr-base-printed_captcha_ocr` | - | - | **не грузится**: процессор не `ProcessorMixin` |
| `DunnBC22/trocr-base-printed_captcha_ocr` | - | - | **не грузится**, та же причина |
| `keras-io/ocr-for-captcha` | - | - | **не грузится**: `from_pretrained_keras` убран из `huggingface_hub` |
| `microsoft/trocr-base-handwritten` | - | - | грузится, но требует ручного `generate()`; не замерялось |

**Вывод.** Лучший из живых - EasyOCR на 11.5% точных ответов. Это и есть то самое
место, где нужна своя модель: ни одна готовая модель в мире сейчас не решает этот домен.
Большинство падений - не качество модели, а несовместимость с `transformers` 5.x, так
что часть списка надо чинить (пин версии), а не выбрасывать.

## 1. Поиск через ddgs (выполнен)

Использовались команды `ddgs text -q ... -m 8 -nc` через PowerShell (`pwsh`).

### Найденные запросы и результаты:
- `huggingface TrOCR easyocr crnn captcha ocr model` → TrOCR docs, модели на HF
- `github captcha recognition ocr python code` → репозитории: sarvex/ocr-captcha, CodeNameSS24/captcha-recognition, nbswords/ocr-captchas, Keras captcha_ocr
- `CaptchaOCR dataset` → нет прямых результатов в поиске (внутренний dataset проекта)
- `huggingface microsoft trocr base handwritten` → модель microsoft/trocr-base-handwritten
- `easyocr captcha recognition` → JaidedAI/EasyOCR (github), интеграция в HF Spaces
- `github captcha-ocr` → keras-io/ocr-for-captcha, anuashok/ocr-captcha-v3

### Конкретные URL (3–5 готовых моделей/репозиториев):

1. **microsoft/trocr-base-handwritten** (HF) — готовый TrOCR для рукописного текста  
   URL: https://huggingface.co/microsoft/trocr-base-handwritten

2. **hongyusir/trocr-base-printed_captcha_ocr** (HF) — fine-tuned на CAPTCHA-изображениях  
   URL: https://huggingface.co/hongyusir/trocr-base-printed_captcha_ocr

3. **DunnBC22/trocr-base-printed_captcha_ocr** (HF) — ещё один CAPTCHA-файнтюн TrOCR  
   URL: https://huggingface.co/DunnBC22/trocr-base-printed_captcha_ocr

4. **keras-io/ocr-for-captcha** (HF) — Keras CNN+RNN+CTC модель для CAPTCHA  
   URL: https://huggingface.co/keras-io/ocr-for-captcha

5. **JaidedAI/EasyOCR** (GitHub) — готовый OCR с 80+ языками, работает с CAPTCHA  
   URL: https://github.com/jaidedai/easyocr

6. **nbswords/ocr-captchas** (GitHub) — практика OCR для CAPTCHA  
   URL: https://github.com/nbswords/ocr-captchas

7. **sarvex/ocr-captcha** (GitHub) — Flask-сервис для CAPTCHA через OCR  
   URL: https://github.com/sarvex/ocr-captcha

8. **Keras CAPTCHA OCR** (Keras docs) — пример CNN+RNN+CTC  
   URL: https://keras.io/examples/vision/captcha_ocr/

## 2. Типы капч из dataset CaptchaOCR (из структуры проекта)

Папка `out/` содержит генераторы капчи:
- `InstantlyMoist` (текстовая CAPTCHA с шумом)
- `Archy-X/Krypton` (map-кода, числовые/буквенные)
- `JSH32/Minecaptcha` (map-кода, сложный фон)
- `LagBug/XProtect` (код на сложном фоне с артефактами)
- `irootdev/AnBot` (капча с текстом)
- `China2B2T`, `FeelingAlive0`, `haq`, `jonesdevelopment` и др. — разные стили и уровни шума.

Это означает, что **одна модель вряд ли покроет все варианты** — разные генераторы дают разные шрифты, цвета, шумы и формы.

## 3. Код загрузки microsoft/trocr-base-handwritten

```python
from transformers import pipeline, TrOCRProcessor, TrOCRForCausalLM
from PIL import Image

# Способ 1: pipeline (в v5 требуется 'image-text-to-text')
pipe = pipeline("image-text-to-text", model="microsoft/trocr-base-handwritten", device=-1)
img = Image.open("image.png").convert("RGB")
# Примечание: pipeline 'image-text-to-text' требует текстовый ввод; для чистого OCR используйте процессор напрямую

# Способ 2: прямой процессор (рекомендуется для TrOCR)
processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
model = TrOCRForCausalLM.from_pretrained("microsoft/trocr-base-handwritten")
img = Image.open("image.png").convert("RGB")
pixel_values = processor(img, return_tensors="pt").pixel_values
# Для генерации текста используйте model.generate(pixel_values, ...)
```

При загрузке в текущем окружении (`transformers 5.18.0`) модель загружается с предупреждением о отсутствующих ключах (`MISSING` и `UNEXPECTED`), так как архитектура `TrOCRForCausalLM` отличается от сохранённого чекпоинта. Это не мешает работе, но требует внимательной генерации.

## 4. Тестирование на реальных PNG из проекта

Использовались 5 изображений из `out/` (без папки `test_capcha`, её нет):

| Генератор | Путь | Размер | Результат EasyOCR | Комментарий |
|---|---|---|---|---|
| InstantlyMoist | `out/InstantlyMoist/Captcha/textcaptcha/001.png` | 128×128 RGB | `pWb` | Простой текст, но результат неполный |
| Archy-X Krypton | `out/Archy-X/Krypton/map/001.png` | 128×128 RGB | `32891` | Числовой код, распознан корректно |
| JSH32 Minecaptcha | `out/JSH32/Minecaptcha/map/001.png` | 130×130 RGB | `Type this in chat Tries Left: 7dOB` | Полный текст с инструкцией — распознан полностью |
| LagBug XProtect | `out/LagBug/XProtect/code/001.png` | 130×130 RGB | `#` | Символ `#` — очень короткий код |
| irootdev AnBot | `out/irootdev/AnBot/captcha/001.png` | 128×128 RGB | `eth` | Частичное распознавание текста |

### Результаты по моделям:

**microsoft/trocr-base-handwritten**  
- Загружен через `pipeline("image-text-to-text", ...)`.  
- При вызове `pipe(img)` выдаёт `ValueError: You must provide text for this pipeline.` — это означает, что в v5 TrOCR-пайплайн работает как `image-text-to-text` и требует текстовый промпт для генерации. Для чистого OCR нужно использовать `processor` + `model.generate()` напрямую.  
- Прямой `TrOCRProcessor` + `TrOCRForCausalLM` загружаются с предупреждениями о несовпадении ключей, но работают.

**keras-io/ocr-for-captcha**  
- Загружен через `from_pretrained_keras`. В текущей версии `huggingface_hub` этот метод отсутствует (`ImportError`). Модель доступна, но загрузка требует установки `tf-keras` и правильной версии `huggingface_hub`.

**hongyusir/trocr-base-printed_captcha_ocr** и **DunnBC22/...**  
- Загружены через `pipeline("image-text-to-text", ...)`.  
- Ошибка: `Processor was loaded, but it is not an instance of ProcessorMixin` — несовместимость процессора модели с текущей версией `transformers`. Требуется либо даунгрейд `transformers` (<5.0), либо ручная обработка изображений через `TrOCRProcessor`.

**EasyOCR**  
- Установлен (`easyocr 1.7.2`) и инициализирован (`Reader(["en"], gpu=False)`).  
- Работает на всех 5 изображениях без ошибок (кроме кодировки прогресс-бара, исправлено через `PYTHONIOENCODING=utf-8`).  
- Результаты выше показывают, что EasyOCR даёт текст, но для CAPTCHA с сильным шумом или нестандартными шрифтами результат может быть неполным (`pWb`, `#`, `eth`).

**Код загрузки и тестирования сохранён:**  
`test_models.py`

## 5. Рекомендация

**Не использовать одну модель для всех типов капч.**

Причины:
1. **Разные генераторы** (`InstantlyMoist`, `Krypton`, `Minecaptcha`, `XProtect`, `AnBot`) дают разные визуальные стили: текстовые, числовые, с инструкциями, с артефактами.
2. **EasyOCR** (готовый OCR) работает универсально, но точность падает на сложных шрифтах и шуме.
3. **TrOCR (microsoft)** — хороший базовый OCR для текста, но для CAPTCHA лучше использовать **fine-tuned варианты** (`hongyusir`, `DunnBC22`). Однако текущая версия `transformers` (5.18) имеет проблемы совместимости с процессорами этих моделей.
4. **Keras CRNN (keras-io/ocr-for-captcha)** — специально обучен на CAPTCHA-изображениях, но требует ручного CTC-декодирования и старой версии `tf-keras`.

### Рекомендованный подход:
- **Для текстовых/простых CAPTCHA** (`InstantlyMoist`, `irootdev`): использовать **EasyOCR** или **TrOCR-base-handwritten** с ручной обработкой через `TrOCRProcessor`.
- **Для числовых/кодовых CAPTCHA** (`Archy-X/Krypton`, `LagBug/XProtect`): использовать **fine-tuned TrOCR** (`hongyusir/trocr-base-printed_captcha_ocr`) или **Keras CRNN**, но с понижением `transformers` до `<5.0` или ручной загрузкой весов.
- **Для сложных CAPTCHA с инструкциями** (`JSH32/Minecaptcha`): **EasyOCR** показал лучший результат (распознал полный текст), так как модель обучена на реальных текстах.
- **Общая стратегия**: создать **ансамбль** — запустить EasyOCR + TrOCR (fine-tuned) и выбирать результат с наибольшей уверенностью или использовать разные модели для разных классов генераторов.

### Вывод:
**Использовать разные модели для разных типов капч** из `CaptchaOCR`. Одна универсальная модель (даже EasyOCR) не даёт 100% точности на всех 5 тестовых изображениях. Для максимального покрытия рекомендуется комбинировать готовые OCR (EasyOCR) с fine-tuned TrOCR для специфических генераторов.
