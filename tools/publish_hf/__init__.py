"""Опубликовать датасет и модель CaptchaOCR на Hugging Face Hub.

Инструмент делает три вещи:

1. ``dataset`` — собирает датасет из ``dataset/out`` и ``dataset/out_ru``, считает по нему
   честную сводку (``dataset_inventory.json``), собирает карточку из шаблона
   ``tools/hf_dataset_card.md`` и загружает всё в репозиторий типа ``dataset``.
2. ``model`` — берёт чекпоинт (``train/run/.../ckpt/step_*.pt`` или уже готовый
   HF-репозиторий), приводит веса к ``model.safetensors``, собирает карточку из шаблона
   и загружает всё в репозиторий типа ``model``. Шаблон выбирается по типу модели:
   ``tools/hf_model_card.md`` — для PP-OCRv6, ``tools/hf_model_card_crn.md`` — для нашего
   CRNN+CTC (можно указать явно флагом ``--template``; по умолчанию тип определяется
   по ``model_type`` из ``config.json`` и по ключам весов, а если он не определён,
   инструмент останавливается, а не затирает карточку PP-OCRv6 шаблоном CRNN).
3. ``check`` — открывает репозиторий через API и печатает, что в нём есть.

Правила, которые инструмент держит:

* **Никакой интерактивности.** Ни одного ``input()``. Если токена нет — печатается
  пошаговая инструкция и код выхода ``2``.
* **Ничего не выдумывается.** Все числа в карточке посчитаны из ``labels.jsonl``
  или из файла результатов. Чего посчитать нельзя — остаётся плейслдером в карточке.
* **Идемпотентность.** Повторный запуск не перезаливает файлы, которые уже лежат в
  репозитории с тем же размером (сравнение по размеру файла в дереве репозитория).
* **Имена типов не зашиты.** Инструмент работает «по дереву сверху вниз»: тип — это
  каталог с ``labels.jsonl``. Переименование каталога типа ничего в нём не ломает.

Примеры вызова::

    .venv-gpu\\Scripts\\python.exe tools\\publish_hf.py --help

    # посмотреть, что уйдёт на хаб, ничего не отправляя
    .venv-gpu\\Scripts\\python.exe tools\\publish_hf.py dataset \\
        --repo-id <user>/<repo> --data-dir dataset --dry-run

    # загрузить датасет (нужен токен)
    .venv-gpu\\Scripts\\python.exe tools\\publish_hf.py dataset \\
        --repo-id <user>/<repo> --data-dir dataset

    # загрузить модель
    .venv-gpu\\Scripts\\python.exe tools\\publish_hf.py model \\
        --repo-id <user>/<model-repo> --checkpoint train\\run\\main --results <file.json>

    # проверить, что лежит в репозитории
    .venv-gpu\\Scripts\\python.exe tools\\publish_hf.py check --repo-id <user>/<repo>

Коды выхода: ``0`` — успех, ``1`` — ошибка, ``2`` — нужна авторизация,
``3`` — отказ создавать репозиторий в чужом namespace без ``--confirm-create``.
"""

from .cli import main

__all__ = ["main"]
