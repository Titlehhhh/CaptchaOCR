# Как выложить датасет и модель на Hugging Face

Короткая инструкция для автора. Инструмент — `tools/publish_hf.py`, он ничего не делает
интерактивно: один раз авторизуешься, потом запускаешь три команды.

---

## 1. Аккаунт и токен (один раз)

1. Зарегистрируйся на <https://huggingface.co/join> (подтверди почту по ссылке из письма).
2. Создай токен: <https://huggingface.co/settings/tokens> → **Write token** → имя,
   например `captha`. Токен — строка `hf_xxxxxxxx…`.
3. Сохрани токен в переменную окружения (PowerShell):

```powershell
$env:HF_TOKEN = "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Или один раз на машину:

```powershell
[Environment]::SetEnvironmentVariable("HF_TOKEN", "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "User")
```

4. Либо авторизуйся через CLI (он положит токен в `~/.cache/huggingface/token`):

```powershell
.venv-gpu\Scripts\hf.exe auth login
.venv-gpu\Scripts\hf.exe auth whoami
```

Проверка: `.venv-gpu\Scripts\hf.exe auth whoami` печатает твое имя пользователя.
Без токена скрипт не падает — он печатает эту же инструкцию и выходит с кодом **2**.

> Кириллица в консоли: `$env:PYTHONIOENCODING="utf-8"` (скрипт сам переводит свой вывод
> в UTF-8, но для кириллицы в *интерактивной* консоли лучше включить `chcp 65001`).

---

## 2. Посмотреть, что уйдёт на хаб (ничего не отправляя)

```powershell
.venv-gpu\Scripts\python.exe tools\publish_hf.py dataset `
    --repo-id Titlehhhh/CaptchaOCR --data-dir dataset --dry-run
```

Скрипт посчитает по `labels.jsonl` все типы, сэмплы, алфавиты, длины меток, полосы и
лицензии, соберёт карточку и `dataset_inventory.json` — и напечатает, сколько файлов и
байт уйдёт. **Сеть не трогается.**

---

## 3. Выложить датасет

```powershell
.venv-gpu\Scripts\python.exe tools\publish_hf.py dataset `
    --repo-id Titlehhhh/CaptchaOCR --data-dir dataset
```

* репозиторий создастся сам (если его ещё нет), тип — `dataset`, видимость — публичная
  (`--private` — приватная);
* раскладка в репозитории: `data/<дерево>/<...>/<тип>/NNN.png` + `labels.jsonl` рядом,
  в корне — `README.md` (карточка) и `dataset_inventory.json` (машинно-читаемая сводка);
* повторный запуск **не перезаливает** файлы, которые уже лежат в репозитории с тем же
  размером — можно спокойно перегенерировать датасет и запустить команду ещё раз;
* публикуются **только собственные рендеры наших генераторов**; чужие картинки, страницы и
  ответы API сюда не попадают. Тип исключается только если в его `source` стоит внешний URL
  (схема `http(s)://` или доменное имя) — такие **исключены по умолчанию**, флаг
  `--include-external-url` включает их осознанно;
* эталонные скриншоты (`real_shots/`) в публикацию не идут: они лежат вне каталогов типов,
  и инструмент их не берёт.

---

## 4. Выложить модель

Сначала нужен чекпоинт. Если модель уже экспортирована в формате HF-репозитория
(есть `model.safetensors` и `config.json`), дай на него каталог:

```powershell
.venv-gpu\Scripts\python.exe tools\publish_hf.py model `
    --repo-id Titlehhhh/CaptchaOCR-PPOCRv6 `
    --checkpoint train\run_ppocr\final `
    --results reports\bench_models\<замер>.json `
    --dataset-repo Titlehhhh/CaptchaOCR
```

Если чекпоинт — это `.pt` с `{"model": state_dict, ...}`, веса сами сохранятся как
`model.safetensors`, а `config.json` / `preprocessor_config.json` / `character_list.txt`
соберутся из чекпоинта (если их там нет — из форм тензоров и из флагов
`--image-height/--image-width/--mean/--std`).

`--results` — файл с честными метриками (например `train\run\<прогон>\val_report.json`).
**Если файл не передан, метрики в карточке останутся плейслолдером** — скрипт ничего не
выдумывает и предупредит об этом.

---

## 5. Проверить, что лежит на хабе

```powershell
.venv-gpu\Scripts\python.exe tools\publish_hf.py check --repo-id Titlehhhh/CaptchaOCR
.venv-gpu\Scripts\python.exe tools\publish_hf.py check `
    --repo-id Titlehhhh/CaptchaOCR-PPOCRv6 --repo-type model
```

Печатает: есть ли репозиторий, сколько файлов, суммарный размер, лицензия из карточки,
видны ли `README.md`, `labels.jsonl` и `dataset_inventory.json`.

---

## Коды выхода

| код | что означает |
|---|---|
| 0 | успех |
| 1 | ошибка (репозиторий не найден, сеть отвалилась и т. п.) |
| 2 | нет авторизации — скрипт напечатал инструкцию |
| 3 | репозиторий в чужом namespace; чтобы создать, нужен `--confirm-create` |

---

## Если что-то пошло не так

* **«Токен не найден»** — §1, шаг 3 или 4.
* **«Репозиторий … в чужом namespace»** — вы указали чужое имя пользователя. Либо
  используйте своё, либо добавьте `--confirm-create`.
* **Загрузка оборвалась на середине** — просто запустите ту же команду ещё раз: уже
  залитые файлы пропустятся.
* **Хочу поменять раскладку или состав** — они заданы в `tools/publish_hf.py`
  (`DATA_PREFIX`) и в таблице лицензий `PLUGIN_LICENCES`.
