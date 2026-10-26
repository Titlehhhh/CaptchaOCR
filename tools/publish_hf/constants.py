import sys
from pathlib import Path

# Кириллица в консоли Windows ломается без UTF-8 (консоль по умолчанию cp1251/cp866),
# поэтомуstdout/stderr переводим в UTF-8 с заменой непечатаемых символов.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - экзотические потоки
        pass

HERE = Path(__file__).resolve().parent.parent
REPO_ROOT = HERE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NO_AUTH = 2
EXIT_NO_CONFIRM = 3

#: Куда внутри репозитория ложится датасет. Одно дерево, зеркало локального.
DATA_PREFIX = "data"

#: Имя машинно-читаемой сводки в корне репозитория датасета.
INVENTORY_NAME = "dataset_inventory.json"

#: Шаблоны карточек (лежат рядом со скриптом).
DATASET_CARD_TEMPLATE = HERE / "hf_dataset_card.md"
#: Шаблон файла лицензии датасета (грузится в корень репозитория как ``LICENSE``).
DATASET_LICENSE_TEMPLATE = HERE / "hf_dataset_license.md"
#: Шаблон карточки модели для PP-OCRv6 (текущий, опубликованный).
MODEL_CARD_TEMPLATE = HERE / "hf_model_card.md"
#: Шаблон карточки модели для нашего CRNN+CTC (обучен с нуля, лицензия MIT).
MODEL_CARD_TEMPLATE_CRNN = HERE / "hf_model_card_crn.md"
#: Шаблоны карточек модели по ключу: какой шаблон для какой модели.
MODEL_CARD_TEMPLATES = {
    "ppocrv6": MODEL_CARD_TEMPLATE,
    "crnn": MODEL_CARD_TEMPLATE_CRNN,
}

#: Отчёт об обучении PP-OCRv6 — первоисточник чисел карточки модели.
TRAINING_REPORT_JSON = REPO_ROOT / "reports" / "TRAINING_PPOCR_V6.json"
#: Архивный бенчмарк базовой модели — второй первоисточник чисел карточки модели.
BENCH_JSON = REPO_ROOT / "reports" / "bench_models" / "ppocrv6-medium.json"
