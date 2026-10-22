"""Опубликовать датасет и модель CaptchaOCR на Hugging Face Hub.

Инструмент делает три вещи:

1. ``dataset`` — собирает датасет из ``dataset/out`` и ``dataset/out_ru``, считает по нему
   честную сводку (``dataset_inventory.json``), собирает карточку из шаблона
   ``tools/hf_dataset_card.md`` и загружает всё в репозиторий типа ``dataset``.
2. ``model`` — берёт чекпоинт (``train/run/.../ckpt/step_*.pt`` или уже готовый
   HF-репозиторий), приводит веса к ``model.safetensors``, собирает карточку из
   ``tools/hf_model_card.md`` и загружает всё в репозиторий типа ``model``.
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

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from fnmatch import fnmatch
from pathlib import Path

# Кириллица в консоли Windows ломается без UTF-8 (консоль по умолчанию cp1251/cp866),
# поэтомуstdout/stderr переводим в UTF-8 с заменой непечатаемых символов.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - экзотические потоки
        pass

HERE = Path(__file__).resolve().parent
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
MODEL_CARD_TEMPLATE = HERE / "hf_model_card.md"


# =====================================================================================
# Лицензии плагинов
# =====================================================================================
#
# Ключ — значение поля ``plugin`` в ``labels.jsonl`` (для дерева ``out/`` это
# ``owner/repo``, для дерева ``out_ru/`` — плоское имя плагина).
#
# Значение — (лицензия апстрима, режим реконструкции): faithful / clean-room /
# reconstructed. Это данные проекта (аудит апстримов), а не выдумка: если плагина
# нет в таблице, лицензия помечается как «не установлена», и в сводку попадает
# поле ``source`` — по нему всегда видно, откуда взялась строка.
PLUGIN_LICENCES: dict[str, tuple[str, str]] = {
    "Archy-X/Krypton": ("no licence (all rights reserved)", "clean-room"),
    "China2B2T/Captcha": ("GPL-3.0", "clean-room"),
    "FeelingAlive0/AdvancedCaptcha": ("MIT", "faithful"),
    "haq/mapcha": ("MIT", "faithful"),
    "InstantlyMoist/Captcha": ("MIT", "faithful"),
    "irootdev/AnBot": ("GPL-3.0", "clean-room"),
    "Joey61021/captcha": ("MIT", "faithful"),
    "jonesdevelopment/sonar": ("GPL-3.0", "clean-room"),
    "jSdCool/minecaptcha": ("CC0-1.0", "faithful"),
    "JSH32/Minecaptcha": ("MIT", "faithful"),
    "just-captcha/ProstoCaptcha": ("MIT", "faithful"),
    "laforetbrut/are-you-sure": ("MIT", "faithful"),
    "LagBug/XProtect": ("MIT", "faithful"),
    "Mrbysco/Captcha": ("MIT", "faithful"),
    "n1zamu/NCaptcha": ("MIT", "faithful"),
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA": (
        "no licence file (all rights reserved)", "clean-room"),
    "Yukun99/Captchas": ("no licence (all rights reserved)", "clean-room"),
    "Z4OLLIEZ4/reCaptcha": ("MIT", "faithful"),
    "BotFilter": ("BSD-2-Clause + запрет на коммерческий хостинг", "clean-room"),
    "CaptchaGUI": ("no licence file (all rights reserved)", "clean-room"),
    "CaptchaVerifyZ": ("all rights reserved (Modrinth)", "clean-room"),
    "LimboFilter": ("AGPL-3.0", "clean-room"),
}

#: Пометка для плагина, которого нет в таблице выше.
LICENCE_UNKNOWN = "не установлена (см. source в labels.jsonl)"
MODE_UNKNOWN = "unknown"

#: Что считать «прочим файлом» в каталоге типа — такие файлы не загружаются.
IGNORED_SUFFIXES = (".html", ".htm")


# =====================================================================================
# Мелкие утилиты
# =====================================================================================

def log(message: str = "") -> None:
    """Напечатать строку (flush — чтобы вывод не потерялся при падении)."""
    print(message, flush=True)


def warn(message: str) -> None:
    """Напечатать предупреждение в stderr."""
    print(f"ВНИМАНИЕ: {message}", file=sys.stderr, flush=True)


def human_bytes(n: int) -> str:
    """Человекочитаемый размер: ``12.3 МБ``."""
    value = float(n)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if value < 1024 or unit == "ТБ":
            return f"{value:.1f} {unit}".replace(".0 ", " ")
        value /= 1024
    return f"{value:.1f} ТБ"


def median(values: list[int]) -> float:
    """Медиана списка чисел."""
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def repo_path_of(path: Path, base: Path) -> str:
    """Путь файла относительно базы, через прямой слэш (как в репозитории)."""
    return Path(os.path.relpath(path, base)).as_posix()


#: Доменное имя в строке `source` — признак материала, взятого с чужого сайта.
#: Требуется именно «домен + /»: у Java-пакетов точки стоят внутри класса
#: (``dev.affan.mapcha.player.CaptchaPlayer#generateCaptcha``), и такой путь не должен
#: считаться внешней ссылкой.
DOMAIN_PATH_RE = re.compile(r"\b[a-z0-9][a-z0-9-]*\.[a-z]{2,}/", re.IGNORECASE)


def has_external_url(source: str) -> bool:
    """Указывает ли `source` на внешний URL (схема или доменное имя).

    Такой тип — это материал, взятый с чужого сайта, и по правилам проекта он не
    публикуется. Собственные рендеры наших генераторов (в том числе чисто-румные
    реконструкции, собранные по референсным скриншотам) внешнего URL не содержат и
    публикуются.

    Имена плагинов в скрипте не зашиты: проверка идёт по самим данным, поэтому
    переименование каталога типа её не ломает.
    """
    text = source or ""
    lowered = text.lower()
    if "http://" in lowered or "https://" in lowered:
        return True
    return bool(DOMAIN_PATH_RE.search(text))


def mode_from_source(source: str) -> str:
    """Режим реконструкции, если он прямо назван в самом `source`.

    Порядок важен: строка «clean-room reconstruction … measured from reference
    screenshots» — это реконструкция по референсам, а не faithful-порт, поэтому
    «reconstruct» проверяется первым.
    """
    text = (source or "").lower()
    if "reconstruct" in text:
        return "reconstructed"
    if "clean-room" in text or "clean room" in text:
        return "clean-room"
    return ""


def charset_kind(chars: set[str]) -> str:
    """Короткое имя класса алфавита — вычисляется из самих символов."""
    has_cyr = any("Ѐ" <= c <= "ӿ" for c in chars)
    has_lat = any("A" <= c <= "Z" or "a" <= c <= "z" for c in chars)
    has_digit = any(c.isdigit() for c in chars)
    has_space = " " in chars
    other = chars - set(" ")

    def _is_lat(c: str) -> bool:
        return "A" <= c <= "Z" or "a" <= c <= "z"

    def _is_cyr(c: str) -> bool:
        return "Ѐ" <= c <= "ӿ"

    other = {c for c in other if not _is_lat(c) and not _is_cyr(c) and not c.isdigit()}
    parts: list[str] = []
    if has_cyr and has_lat:
        parts.append("латиница+кириллица")
    elif has_cyr:
        parts.append("кириллица")
    elif has_lat:
        parts.append("латиница")
    elif has_digit:
        parts.append("цифры")
    else:
        parts.append("символы")
    if has_space:
        parts.append("пробел")
    if other:
        parts.append("знаки")
    return "+".join(parts)


# =====================================================================================
# Авторизация
# =====================================================================================

AUTH_INSTRUCTIONS = """\
=== Нужен токен Hugging Face =========================================

Скрипту нужен токен с правом WRITE. Сделайте это (один раз):

  1. Зарегистрируйтесь на https://huggingface.co/join
     (аккаунт привязан к почте, подтверждение по ссылке из письма).

  2. Откройте https://huggingface.co/settings/tokens
     -> "Write token" (или "Read & Write") -> задайте имя, например "captha".
     Токен — это строка вида hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.

  3. Сохраните токен в переменную окружения (PowerShell, текущая сессия):

       $env:HF_TOKEN = "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

     Или один раз на машину:

       [Environment]::SetEnvironmentVariable("HF_TOKEN", "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "User")

  4. Либо авторизуйтесь через CLI (он тоже кладёт токен в ~/.cache/huggingface/token):

       .venv-gpu\\Scripts\\hf.exe auth login
       .venv-gpu\\Scripts\\hf.exe auth whoami

Проверить, что токен виден:

  $env:HF_TOKEN | Measure-Object -Character
  .venv-gpu\\Scripts\\hf.exe auth whoami

После этого запустите ту же команду снова.
====================================================================="""


def resolve_token(explicit: str | None) -> str | None:
    """Найти токен: флаг --token, переменная HF_TOKEN, сохранённый токен CLI."""
    if explicit:
        return explicit
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN"):
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    try:
        from huggingface_hub import get_token

        stored = get_token()
        if stored:
            return stored
    except Exception:  # noqa: BLE001 - токена просто нет, это не ошибка
        return None
    return None


def require_token(explicit: str | None) -> str:
    """Токен или инструкция + выход с кодом 2. Интерактивного ввода не будет."""
    token = resolve_token(explicit)
    if token:
        return token
    log(AUTH_INSTRUCTIONS)
    log("Токен не найден: ни HF_TOKEN, ни сохранённый токен CLI. Выход с кодом 2.")
    raise SystemExit(EXIT_NO_AUTH)


def api_for(token: str):
    """Создать HfApi с токеном."""
    from huggingface_hub import HfApi

    return HfApi(token=token)


def whoami_name(api) -> str:
    """Имя пользователя, которому принадлежит токен (пустая строка — не вышло)."""
    try:
        info = api.whoami()
    except Exception:  # noqa: BLE001 - токен может быть без прав на профиль
        return ""
    if isinstance(info, dict):
        return str(info.get("name") or info.get("fullname") or "")
    return ""


# =====================================================================================
# Сбор датасета
# =====================================================================================

class TypeDir:
    """Один тип капт: каталог с ``labels.jsonl`` и картинками рядом."""

    def __init__(self, directory: Path, data_dir: Path):
        self.directory = directory
        rel = Path(os.path.relpath(directory, data_dir))
        parts = rel.parts
        self.tree = parts[0] if len(parts) > 1 else data_dir.name
        self.type_id = rel.as_posix()          # например out/LagBug/XProtect/code
        self.short_id = "/".join(parts[1:]) if len(parts) > 1 else rel.as_posix()
        self.labels_path = directory / "labels.jsonl"
        self.rows: list[dict] = []
        self.pngs: list[Path] = []
        self.other_files: list[str] = []
        self.inventory: dict = {}

    def repo_dir(self) -> str:
        """Путь каталога типа внутри репозитория."""
        return f"{DATA_PREFIX}/{self.type_id}"


def find_type_dirs(data_dir: Path) -> list[TypeDir]:
    """Найти все каталоги с ``labels.jsonl`` под ``data_dir`` (дерево сверху вниз)."""
    found: list[TypeDir] = []
    for dirpath, dirs, files in os.walk(data_dir):
        # real_shots — эталонные скриншоты, они не обучающие и в типы не входят.
        dirs[:] = [d for d in dirs if d != "real_shots"]
        if "labels.jsonl" not in files:
            continue
        found.append(TypeDir(Path(dirpath), data_dir))
    return sorted(found, key=lambda t: t.type_id)


def read_labels(path: Path) -> list[dict]:
    """Прочитать ``labels.jsonl``."""
    rows: list[dict] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def collect_type(type_dir: TypeDir) -> None:
    """Заполнить ``type_dir.rows``, ``pngs`` и посчитать сводку по типу."""
    type_dir.rows = read_labels(type_dir.labels_path)
    pngs = sorted(p for p in type_dir.directory.glob("*.png") if p.is_file())
    type_dir.pngs = pngs
    type_dir.other_files = sorted(
        p.name for p in type_dir.directory.iterdir()
        if p.is_file() and p.suffix.lower() not in IGNORED_SUFFIXES
        and p.name != "labels.jsonl" and p.suffix.lower() != ".png"
    )

    rows = type_dir.rows
    texts = [str(r.get("text") or "") for r in rows]
    answers = [str(r.get("answer") or "") for r in rows]
    chars: set[str] = set()
    for t in texts:
        chars.update(t)

    plugins = sorted({str(r.get("plugin") or "") for r in rows})
    plugin = plugins[0] if len(plugins) == 1 else "|".join(plugins)
    licence, mode = PLUGIN_LICENCES.get(plugin, (LICENCE_UNKNOWN, MODE_UNKNOWN))

    text_lengths = [len(t) for t in texts]
    answer_lengths = [len(a) for a in answers]
    widths = [int(r["width"]) for r in rows if r.get("width")]
    heights = [int(r["height"]) for r in rows if r.get("height")]
    sources = sorted({str(r.get("source") or "") for r in rows})

    # Если плагина нет в таблице лицензий, режим реконструкции берём из самого `source`:
    # там прямо написано, faithful это или clean-room. Ничего не додумываем.
    if mode == MODE_UNKNOWN:
        mode = mode_from_source(sources[0]) or MODE_UNKNOWN

    type_dir.inventory = {
        "type_id": type_dir.type_id,
        "tree": type_dir.tree,
        "plugin": plugin,
        "samples": len(rows),
        "png_files": len(pngs),
        "bytes": sum(p.stat().st_size for p in pngs),
        "alphabet": "".join(sorted(chars)),
        "alphabet_size": len(chars),
        "alphabet_kind": charset_kind(chars),
        "text_length": {
            "min": min(text_lengths) if text_lengths else 0,
            "median": median(text_lengths),
            "max": max(text_lengths) if text_lengths else 0,
        },
        "answer_length": {
            "min": min(answer_lengths) if answer_lengths else 0,
            "median": median(answer_lengths),
            "max": max(answer_lengths) if answer_lengths else 0,
        },
        "rows_with_roi": sum(1 for r in rows if r.get("roi")),
        "rows_without_roi": sum(1 for r in rows if not r.get("roi")),
        "rows_text_ne_answer": sum(1 for r in rows
                                   if str(r.get("text")) != str(r.get("answer"))),
        "unique_answers": len(set(answers)),
        "unique_texts": len(set(texts)),
        "image_width": {"min": min(widths) if widths else 0,
                        "max": max(widths) if widths else 0},
        "image_height": {"min": min(heights) if heights else 0,
                         "max": max(heights) if heights else 0},
        "licence": licence,
        "mode": mode,
        "external_url": any(has_external_url(s) for s in sources),
        "source": sources[0] if len(sources) == 1 else " | ".join(sources),
        "source_variants": len(sources),
    }


def build_inventory(types: list[TypeDir], data_dir: Path) -> dict:
    """Машинно-читаемая сводка по всему датасету."""
    per_type = [t.inventory for t in types]
    plugin_map: dict[str, dict] = {}
    for t in types:
        key = t.inventory["plugin"]
        entry = plugin_map.setdefault(key, {
            "plugin": key,
            "types": [],
            "samples": 0,
            "png_files": 0,
            "licence": t.inventory["licence"],
            "mode": t.inventory["mode"],
        })
        entry["types"].append(t.inventory["type_id"])
        entry["samples"] += t.inventory["samples"]
        entry["png_files"] += t.inventory["png_files"]

    trees: dict[str, dict] = {}
    for t in types:
        entry = trees.setdefault(t.tree, {"tree": t.tree, "types": 0,
                                           "samples": 0, "png_files": 0, "bytes": 0})
        entry["types"] += 1
        entry["samples"] += t.inventory["samples"]
        entry["png_files"] += t.inventory["png_files"]
        entry["bytes"] += t.inventory["bytes"]

    all_chars: set[str] = set()
    for t in types:
        all_chars.update(t.inventory["alphabet"])

    total_png = sum(t["png_files"] for t in per_type)
    total_bytes = sum(t["bytes"] for t in per_type)
    return {
        "schema": "captha-dataset-inventory/1",
        "data_dir": Path(os.path.relpath(data_dir, REPO_ROOT)).as_posix(),
        "layout": f"{DATA_PREFIX}/<tree>/<...>/<type>/<file>",
        "totals": {
            "types": len(per_type),
            "samples": sum(t["samples"] for t in per_type),
            "png_files": total_png,
            "bytes": total_bytes,
            "plugins": len(plugin_map),
            "trees": len(trees),
            "types_with_roi": sum(1 for t in per_type if t["rows_with_roi"]),
            "rows_with_roi": sum(t["rows_with_roi"] for t in per_type),
            "rows_without_roi": sum(t["rows_without_roi"] for t in per_type),
            "types_text_ne_answer": sum(1 for t in per_type if t["rows_text_ne_answer"]),
            "alphabet_size": len(all_chars),
            "types_faithful": sum(1 for t in per_type if t["mode"] == "faithful"),
            "types_clean_room": sum(1 for t in per_type if t["mode"] == "clean-room"),
            "types_reconstructed": sum(1 for t in per_type if t["mode"] == "reconstructed"),
            "types_mode_unknown": sum(1 for t in per_type if t["mode"] == MODE_UNKNOWN),
        },
        "alphabet": "".join(sorted(all_chars)),
        "trees": sorted(trees.values(), key=lambda e: e["tree"]),
        "plugins": sorted(plugin_map.values(), key=lambda e: e["plugin"]),
        "types": per_type,
    }


# =====================================================================================
# Карточки
# =====================================================================================

def render_template(template: str, values: dict[str, str]) -> tuple[str, list[str]]:
    """Подставить ``{КЛЮЧ}`` в шаблон. Возвращает (текст, оставшиеся плейсхолдеры)."""
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", str(value))
    leftovers: list[str] = []
    rest = out
    while "{" in rest and "}" in rest:
        start = rest.index("{")
        end = rest.index("}", start)
        token = rest[start:end + 1]
        if token not in leftovers:
            leftovers.append(token)
        rest = rest[end + 1:]
    return out, leftovers


def type_table(inventory: dict) -> str:
    """Таблица типов для карточки датасета."""
    lines = ["| тип | дерево | PNG | с полосой | алфавит | длина text (мин/мед/макс) "
             "| уник. ответов | лицензия |",
             "|---|---|---|---|---|---|---|---|"]
    for t in inventory["types"]:
        tl = t["text_length"]
        lines.append(
            f"| `{t['type_id']}` | {t['tree']} | {t['png_files']} | "
            f"{t['rows_with_roi']}/{t['samples']} | {t['alphabet_kind']} "
            f"({t['alphabet_size']}) | {tl['min']}/{tl['median']:.0f}/{tl['max']} | "
            f"{t['unique_answers']} | {t['licence']} |")
    return "\n".join(lines)


def plugin_table(inventory: dict) -> str:
    """Таблица плагинов для карточки датасета."""
    lines = ["| плагин | типов | PNG | лицензия | режим |", "|---|---|---|---|---|"]
    for p in inventory["plugins"]:
        lines.append(f"| `{p['plugin']}` | {len(p['types'])} | {p['png_files']} | "
                     f"{p['licence']} | {p['mode']} |")
    return "\n".join(lines)


def tree_table(inventory: dict) -> str:
    """Таблица деревьев для карточки датасета."""
    lines = ["| дерево | типов | PNG | байт |", "|---|---|---|---|"]
    for t in inventory["trees"]:
        lines.append(f"| `{t['tree']}` | {t['types']} | {t['png_files']} | "
                     f"{human_bytes(t['bytes'])} |")
    return "\n".join(lines)


def alphabet_block(inventory: dict) -> str:
    """Полный список алфавитов по типам (таблица обрезает символы)."""
    lines = []
    for t in inventory["types"]:
        alphabet = t["alphabet"] or "(пусто)"
        lines.append(f"* `{t['type_id']}` — алфавит ({t['alphabet_size']} символов): "
                     f"`{alphabet}`")
    return "\n".join(lines)


def reconstructed_block(inventory: dict) -> str:
    """Список типов, которые не являются faithful-портами (реконструкции)."""
    lines = []
    for t in inventory["types"]:
        if t["mode"] == "faithful":
            continue
        lines.append(f"* `{t['type_id']}` — режим **{t['mode']}**, плагин `{t['plugin']}`; "
                     f"происхождение: {t['source']}")
    if not lines:
        return "_Все типы — faithful-порты апстримных алгоритмов._"
    return "\n".join(lines)


def dataset_card_values(inventory: dict, repo_id: str) -> dict[str, str]:
    """Значения для подстановки в шаблон карточки датасета."""
    totals = inventory["totals"]
    return {
        "REPO_ID": repo_id,
        "N_TYPES": str(totals["types"]),
        "N_SAMPLES": str(totals["samples"]),
        "N_PNG_FILES": str(totals["png_files"]),
        "N_PLUGINS": str(totals["plugins"]),
        "N_TREES": str(totals["trees"]),
        "N_TYPES_WITH_ROI": str(totals["types_with_roi"]),
        "N_ROWS_WITH_ROI": str(totals["rows_with_roi"]),
        "N_ROWS_WITHOUT_ROI": str(totals["rows_without_roi"]),
        "N_TYPES_TEXT_NE_ANSWER": str(totals["types_text_ne_answer"]),
        "N_FAITHFUL_TYPES": str(totals["types_faithful"]),
        "N_CLEAN_ROOM_TYPES": str(totals["types_clean_room"]),
        "N_RECONSTRUCTED_TYPES": str(totals["types_reconstructed"]),
        "ALPHABET_SIZE": str(totals["alphabet_size"]),
        "TOTAL_BYTES": str(totals["bytes"]),
        "TOTAL_BYTES_HUMAN": human_bytes(totals["bytes"]),
        "DATA_DIR": inventory["data_dir"],
        "LAYOUT": inventory["layout"],
        "TREE_TABLE": tree_table(inventory),
        "TYPE_TABLE": type_table(inventory),
        "PLUGIN_TABLE": plugin_table(inventory),
        "ALPHABET_LIST": alphabet_block(inventory),
        "RECONSTRUCTED_LIST": reconstructed_block(inventory),
    }


# =====================================================================================
# Загрузка датасета
# =====================================================================================

def remote_file_sizes(api, repo_id: str, repo_type: str) -> dict[str, int]:
    """Карта «путь в репозитории -> размер файла» для уже залитого."""
    sizes: dict[str, int] = {}
    try:
        entries = api.list_repo_tree(repo_id=repo_id, repo_type=repo_type, recursive=True)
    except Exception:  # noqa: BLE001 - репозитория ещё нет, значит заливать всё
        return sizes
    for entry in entries:
        path = getattr(entry, "path", None)
        if path is None:
            continue
        size = getattr(entry, "size", None)
        if size is None:
            continue
        sizes[path] = int(size)
    return sizes


def ensure_repo(api, repo_id: str, repo_type: str, token: str,
                private: bool, confirm_create: bool, user: str) -> None:
    """Создать репозиторий, если его нет. Чужой namespace — только с --confirm-create."""
    namespace = repo_id.split("/")[0]
    if user and namespace.lower() != user.lower():
        message = (f"Репозиторий {repo_id} находится в чужом namespace "
                   f"({namespace!r}), а токен принадлежит {user!r}.")
        if not confirm_create:
            log("ВНИМАНИЕ: " + message)
            log("Скрипт не будет создавать репозиторий в чужом namespace.")
            log("Если это действительно нужно — повторите с флагом --confirm-create.")
            raise SystemExit(EXIT_NO_CONFIRM)
        warn(message + " Создаю из-за --confirm-create.")

    from huggingface_hub import errors

    try:
        api.repo_info(repo_id=repo_id, repo_type=repo_type)
        log(f"Репозиторий {repo_id} ({repo_type}) уже существует — использую его.")
        return
    except errors.RepositoryNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001
        warn(f"Не удалось проверить репозиторий {repo_id}: {type(exc).__name__}: {exc}")

    log(f"Создаю репозиторий {repo_id} (тип {repo_type}, "
        f"{'private' if private else 'public'})...")
    api.create_repo(repo_id=repo_id, repo_type=repo_type, private=private,
                    exist_ok=True)


def upload_dataset(args, inventory: dict, card: str, types: list[TypeDir]) -> int:
    """Залить датасет в репозиторий. Возвращает число загруженных файлов."""
    token = require_token(args.token)
    api = api_for(token)
    user = whoami_name(api)
    ensure_repo(api, args.repo_id, "dataset", token, args.private,
                args.confirm_create, user)

    remote = remote_file_sizes(api, args.repo_id, "dataset")
    log(f"В репозитории уже есть {len(remote)} файлов.")

    inventory_bytes = json.dumps(inventory, ensure_ascii=False, indent=2).encode("utf-8")
    card_bytes = card.encode("utf-8")

    # План: (путь в репозитории, локальный путь или None для bytes, размер)
    plan: list[tuple[str, Path | None, bytes | None, int]] = []
    for t in types:
        for png in t.pngs:
            path_in_repo = f"{t.repo_dir()}/{png.name}"
            plan.append((path_in_repo, png, None, png.stat().st_size))
        plan.append((f"{t.repo_dir()}/labels.jsonl", t.labels_path, None,
                     t.labels_path.stat().st_size))
    plan.append(("README.md", None, card_bytes, len(card_bytes)))
    plan.append((INVENTORY_NAME, None, inventory_bytes, len(inventory_bytes)))

    todo = [item for item in plan
            if remote.get(item[0]) != item[3]]
    skipped = len(plan) - len(todo)
    total_bytes = sum(item[3] for item in todo)
    log(f"К загрузке: {len(todo)} файлов, {human_bytes(total_bytes)}; "
        f"пропущено (уже есть, размер совпал): {skipped}.")
    if not todo:
        log("Все файлы уже загружены — нечего отправлять.")
        return 0

    from huggingface_hub import CommitOperationAdd

    uploaded = 0
    batch: list[tuple[str, Path | None, bytes | None, int]] = []
    batch_bytes = 0
    batch_limit = 200
    byte_limit = 20 * 1024 * 1024

    def flush(items):
        nonlocal uploaded
        if not items:
            return
        operations = []
        for path_in_repo, local, data, _size in items:
            source = local if local is not None else data
            operations.append(CommitOperationAdd(path_in_repo=path_in_repo,
                                                 path_or_fileobj=source))
        api.create_commit(repo_id=args.repo_id, operations=operations,
                          repo_type="dataset",
                          commit_message=f"CaptchaOCR dataset: {len(items)} files")
        uploaded += len(items)
        log(f"  загружено {uploaded}/{len(todo)} "
            f"({human_bytes(sum(i[3] for i in items))} за коммит)")

    for item in todo:
        batch.append(item)
        batch_bytes += item[3]
        if len(batch) >= batch_limit or batch_bytes >= byte_limit:
            flush(batch)
            batch = []
            batch_bytes = 0
    flush(batch)
    return uploaded


# =====================================================================================
# Модель
# =====================================================================================

#: Файлы чекпоинта, которые копируются в репозиторий модели как есть.
#: Список явный: результаты замера (`val_report.json`) в репозиторий модели не попадают.
MODEL_EXTRA_PATTERNS = ("*.py", "onnx/*", "vocab.json", "processor_config.json",
                        "tokenizer_config.json", "special_tokens_map.json",
                        "added_tokens.json", "generation_config.json",
                        "LICENSE", "LICENSE.txt", "LICENSE.md")


def load_checkpoint_state(path: Path) -> tuple[dict, dict]:
    """Прочитать чекпоинт: вернуть (state_dict, прочие поля верхнего уровня)."""
    import torch

    obj = torch.load(path, map_location="cpu", weights_only=False)
    extra: dict = {}
    state = None
    if isinstance(obj, dict):
        for key in ("model", "state_dict", "model_state_dict", "weights", "net"):
            if key in obj and isinstance(obj[key], dict):
                state = obj[key]
                break
        if state is None:
            # возможно, это и есть state_dict: все значения — тензоры
            if obj and all(hasattr(v, "shape") for v in obj.values()):
                state = obj
            else:
                state = obj.get("model", {})
        extra = {k: v for k, v in obj.items() if k not in
                 ("model", "state_dict", "model_state_dict", "weights", "net", "optim",
                  "sched", "optimizer", "rng", "cuda_rng", "aug_rng")}
    elif hasattr(obj, "state_dict"):
        state = obj.state_dict()
    if not state:
        raise SystemExit(f"Не удалось найти state_dict в чекпоинте {path}")
    return state, extra


def derive_geometry(state: dict) -> dict:
    """Вывести параметры архитектуры из форм тензоров (это измерение, не догадка)."""
    out: dict = {}
    fc = state.get("fc.weight")
    if fc is not None and getattr(fc, "ndim", 0) == 2:
        out["num_classes"] = int(fc.shape[0])
        out["hidden"] = int(fc.shape[1]) // 2
    rnn = state.get("rnn.weight_ih_l0")
    if rnn is not None and getattr(rnn, "ndim", 0) == 2:
        out["rows"] = int(rnn.shape[1]) // 256
        out["glyph_height"] = out["rows"] * 8
    return out


def write_safetensors(state: dict, path: Path) -> None:
    """Сохранить state_dict в формате safetensors."""
    from safetensors.torch import save_file

    tensors = {k: v.detach().cpu().contiguous() for k, v in state.items()
               if hasattr(v, "detach")}
    save_file(tensors, str(path), metadata={"format": "pt"})


def preprocessor_config(height: int, width: int, mean: float, std: float,
                        charset: str, extra: dict) -> dict:
    """Описание препроцессора: размер входа, mean/std, charset."""
    cfg = {
        "image_processor_type": "CaptchaProcessor",
        "do_resize": True,
        "size": {"height": height, "width": width},
        "do_normalize": True,
        "image_mean": [mean],
        "image_std": [std],
        "resample": 2,
        "do_convert_rgb": False,
        "charset": charset,
    }
    cfg.update(extra)
    return cfg


def model_card_values(args, info: dict) -> dict[str, str]:
    """Значения для подстановки в шаблон карточки модели."""
    values = {
        "REPO_ID": args.repo_id,
        "CHECKPOINT": info.get("checkpoint", "не указан"),
        "N_CLASSES": info.get("num_classes", "не выведено"),
        "HIDDEN": info.get("hidden", "не выведено"),
        "GLYPH_HEIGHT": info.get("glyph_height", "не выведено"),
        "CHARSET": info.get("charset", "не указан"),
        "N_CHARS": str(len(info.get("charset", ""))) if info.get("charset") else "не указан",
        "IMAGE_HEIGHT": str(info.get("image_height", args.image_height)),
        "IMAGE_WIDTH": str(info.get("image_width", args.image_width)),
        "IMAGE_MEAN": str(info.get("image_mean", args.mean)),
        "IMAGE_STD": str(info.get("image_std", args.std)),
        "DATASET_REPO": args.dataset_repo or "не указан",
        "N_TRAIN_TYPES": info.get("n_train_types", "не указано"),
        "N_TRAIN_SAMPLES": info.get("n_train_samples", "не указано"),
        "RESULTS_BLOCK": info.get("results_block", "не указано"),
        "RESULTS_WARNING": info.get("results_warning", ""),
        "PENDING": "<!-- ЗАПОЛНИТЬ ВРУЧНУЮ -->",
    }
    return values


def _round(value) -> str:
    """Число в карточке: округлить до 4 знаков, если это float."""
    if isinstance(value, float):
        return f"{round(value, 4)}"
    return str(value)


def extract_results(path: Path | None) -> tuple[str, str]:
    """Достать честные метрики из файла результатов.

    Возвращает (блок markdown, предупреждение). Если файла нет или в нём нет
    знакомых ключей — возвращается явный плейсхолдер, а не выдуманные числа.
    """
    placeholder = (
        "**Метрики не указаны.** Файл результатов не передан (`--results`) или в нём "
        "нет знакомых полей. Числа ниже **не выдуманы** — их нужно вписать вручную "
        "после замера.\n\n"
        "| метрика | значение |\n|---|---|\n"
        "| exact match | — |\n| CER | — |\n| число сэмплов | — |"
    )
    if path is None:
        return placeholder, ("Файл результатов не передан (--results): метрики в карточке "
                             "оставлены плейслдером.")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        return placeholder, (f"Не удалось прочитать файл результатов {path}: "
                             f"{type(exc).__name__}: {exc}")

    overall = data.get("overall") if isinstance(data, dict) else None
    per_type = data.get("per_type") if isinstance(data, dict) else None
    if not isinstance(overall, dict):
        overall = data if isinstance(data, dict) else {}

    def _pick(*names):
        for name in names:
            if name in overall and overall[name] is not None:
                return overall[name]
        return None

    exact = _pick("exact", "exact_match", "accuracy", "acc")
    cer = _pick("cer", "mean_cer", "CER")
    n = _pick("n", "n_samples", "count", "total")

    if exact is None and cer is None:
        return placeholder, (f"В файле результатов {path} не найдено полей exact/cer — "
                             f"метрики оставлены плейслдером.")

    lines = ["| метрика | значение |", "|---|---|"]
    if n is not None:
        lines.append(f"| число сэмплов | {n} |")
    if exact is not None:
        lines.append(f"| exact match | {_round(exact)} |")
    if cer is not None:
        lines.append(f"| CER | {_round(cer)} |")
    if isinstance(per_type, dict) and per_type:
        lines.append(f"| типов в отчёте | {len(per_type)} |")
    block = "\n".join(lines) + f"\n\nИсточник: `{path.name}` (файл передан через `--results`)."
    return block, ""


def collect_model(args) -> tuple[dict, list[tuple[str, Path]], dict]:
    """Собрать файлы модели. Возвращает (info, список (путь в репозитории, локальный
    файл), временный каталог)."""
    ckpt = Path(args.checkpoint)
    if not ckpt.exists():
        raise SystemExit(f"Чекпоинт не найден: {ckpt}")

    staging = Path(tempfile.mkdtemp(prefix="hf_publish_", dir=str(REPO_ROOT)))
    info: dict = {"checkpoint": str(ckpt)}
    files: list[tuple[str, Path]] = []

    charset = ""
    if ckpt.is_file():
        ckpt_dir = ckpt.parent
        state, extra = load_checkpoint_state(ckpt)
        info.update(derive_geometry(state))
        charset = str(extra.get("charset") or "")
        info["step"] = extra.get("step")
        info["epoch"] = extra.get("epoch")
        weights = staging / "model.safetensors"
        write_safetensors(state, weights)
        files.append(("model.safetensors", weights))
    else:
        ckpt_dir = ckpt
        safes = sorted(ckpt.rglob("*.safetensors"))
        if safes:
            best = max(safes, key=lambda p: p.stat().st_mtime)
            files.append((best.name, best))
            info["weights_source"] = str(best.relative_to(ckpt))
        else:
            pts = sorted([p for p in ckpt.rglob("*")
                          if p.is_file() and p.suffix.lower() in (".pt", ".pth", ".ckpt")])
            if not pts:
                raise SystemExit(
                    f"В {ckpt} нет ни model.safetensors, ни *.pt — нечего публиковать.")
            best = max(pts, key=lambda p: p.stat().st_mtime)
            state, extra = load_checkpoint_state(best)
            info.update(derive_geometry(state))
            charset = str(extra.get("charset") or "")
            info["step"] = extra.get("step")
            info["epoch"] = extra.get("epoch")
            weights = staging / "model.safetensors"
            write_safetensors(state, weights)
            files.append(("model.safetensors", weights))
            info["weights_source"] = str(best.relative_to(ckpt))

    # config.json: из чекпоинта, иначе — синтезировать из форм тензоров.
    config_path = ckpt_dir / "config.json"
    if config_path.is_file():
        try:
            with open(config_path, encoding="utf-8") as handle:
                config = json.load(handle)
        except ValueError as exc:
            warn(f"config.json не читается ({exc}) — будет создан заново.")
            config = {}
        info["num_classes"] = config.get("num_classes", info.get("num_classes"))
        info["hidden"] = config.get("hidden", info.get("hidden"))
        info["glyph_height"] = config.get("glyph_height", info.get("glyph_height"))
        charset = config.get("charset") or charset
        info["config_source"] = "config.json из чекпоинта"
    else:
        config = {
            "architectures": ["CaptchaModel"],
            "model_type": "captha",
            "num_classes": info.get("num_classes"),
            "hidden": info.get("hidden"),
            "glyph_height": info.get("glyph_height"),
            "charset": charset,
            "blank_index": 0,
        }
        config = {k: v for k, v in config.items() if v is not None}
        info["config_source"] = ("синтезирован из state_dict "
                                  "(архитектура выведена из форм тензоров)")
        warn("В чекпоинте нет config.json — он собран из форм тензоров. "
             "Проверьте его перед публикацией.")
    info["charset"] = charset
    config_bytes = json.dumps(config, ensure_ascii=False, indent=2).encode("utf-8")

    # preprocessor_config.json: из чекпоинта, иначе — по флагам.
    pre_path = ckpt_dir / "preprocessor_config.json"
    if pre_path.is_file():
        pre_bytes = pre_path.read_bytes()
        try:
            pre = json.loads(pre_bytes.decode("utf-8"))
        except ValueError:
            pre = {}
        size = pre.get("size") or {}
        info["image_height"] = size.get("height", args.image_height)
        info["image_width"] = size.get("width", args.image_width)
        mean = pre.get("image_mean") or [args.mean]
        std = pre.get("image_std") or [args.std]
        info["image_mean"] = mean[0] if isinstance(mean, list) and mean else args.mean
        info["image_std"] = std[0] if isinstance(std, list) and std else args.std
        info["preprocessor_source"] = "preprocessor_config.json из чекпоинта"
    else:
        pre = preprocessor_config(args.image_height, args.image_width, args.mean,
                                  args.std, charset, {})
        pre_bytes = json.dumps(pre, ensure_ascii=False, indent=2).encode("utf-8")
        info["image_height"] = args.image_height
        info["image_width"] = args.image_width
        info["image_mean"] = args.mean
        info["image_std"] = args.std
        info["preprocessor_source"] = "собран по флагам --image-height/--image-width/--mean/--std"

    # character_list.txt: из чекпоинта, иначе — из charset.
    char_path = ckpt_dir / "character_list.txt"
    if char_path.is_file():
        char_bytes = char_path.read_bytes()
        info["character_list_source"] = "character_list.txt из чекпоинта"
        if not charset:
            charset = char_path.read_text(encoding="utf-8").split()
    elif charset:
        char_bytes = ("\n".join(charset) + "\n").encode("utf-8")
        info["character_list_source"] = "собран из charset чекпоинта"
    else:
        char_bytes = b""
        info["character_list_source"] = "не найден (модель, возможно, его не использует)"

    # Прочие файлы экспорта (код модели, vocab.json, LICENSE, onnx/...).
    extra_files: list[tuple[str, Path]] = []
    if ckpt_dir.is_dir():
        for item in sorted(ckpt_dir.rglob("*")):
            if not item.is_file():
                continue
            if item.name in ("README.md", "labels.jsonl"):
                continue
            rel = item.relative_to(ckpt_dir).as_posix()
            if rel in ("model.safetensors", "config.json",
                       "preprocessor_config.json", "character_list.txt"):
                continue
            if not any(fnmatch(rel, pattern) for pattern in MODEL_EXTRA_PATTERNS):
                continue
            extra_files.append((rel, item))

    info["extra_files"] = [rel for rel, _ in extra_files]
    return {"info": info, "config_bytes": config_bytes, "pre_bytes": pre_bytes,
            "char_bytes": char_bytes}, files + extra_files, staging


def upload_model(args, meta: dict, files: list[tuple[str, Path]], card: str) -> int:
    """Залить модель в репозиторий."""
    token = require_token(args.token)
    api = api_for(token)
    user = whoami_name(api)
    ensure_repo(api, args.repo_id, "model", token, args.private,
                args.confirm_create, user)

    remote = remote_file_sizes(api, args.repo_id, "model")
    log(f"В репозитории уже есть {len(remote)} файлов.")

    from huggingface_hub import CommitOperationAdd

    operations = []
    plan: list[tuple[str, int]] = []
    for path_in_repo, local in files:
        size = local.stat().st_size
        if remote.get(path_in_repo) == size:
            log(f"  пропускаю {path_in_repo} (размер совпал)")
            continue
        operations.append(CommitOperationAdd(path_in_repo=path_in_repo,
                                             path_or_fileobj=str(local)))
        plan.append((path_in_repo, size))
    for path_in_repo, data in (("config.json", meta["config_bytes"]),
                               ("preprocessor_config.json", meta["pre_bytes"]),
                               ("README.md", card.encode("utf-8"))):
        if not data:
            continue
        if remote.get(path_in_repo) == len(data):
            log(f"  пропускаю {path_in_repo} (размер совпал)")
            continue
        operations.append(CommitOperationAdd(path_in_repo=path_in_repo,
                                             path_or_fileobj=data))
        plan.append((path_in_repo, len(data)))
    if meta["char_bytes"]:
        if remote.get("character_list.txt") != len(meta["char_bytes"]):
            operations.append(CommitOperationAdd(path_in_repo="character_list.txt",
                                                 path_or_fileobj=meta["char_bytes"]))
            plan.append(("character_list.txt", len(meta["char_bytes"])))

    if not operations:
        log("Все файлы уже загружены — нечего отправлять.")
        return 0

    total = sum(size for _, size in plan)
    log(f"К загрузке: {len(plan)} файлов, {human_bytes(total)}.")
    for path_in_repo, size in plan:
        log(f"  {path_in_repo} — {human_bytes(size)}")

    api.create_commit(repo_id=args.repo_id, operations=operations, repo_type="model",
                      commit_message="CaptchaOCR model export")
    return len(plan)


# =====================================================================================
# Команда check
# =====================================================================================

def check_repo(args) -> int:
    """Проверить, что лежит в репозитории."""
    token = require_token(args.token)
    api = api_for(token)
    repo_type = args.repo_type

    from huggingface_hub import errors

    try:
        info = api.repo_info(repo_id=args.repo_id, repo_type=repo_type)
    except errors.RepositoryNotFoundError:
        log(f"Репозиторий {args.repo_id} (тип {repo_type}) НЕ НАЙДЕН на хабе.")
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001
        log(f"Не удалось открыть {args.repo_id}: {type(exc).__name__}: {exc}")
        return EXIT_ERROR

    log(f"Репозиторий: {args.repo_id} (тип {repo_type})")
    log(f"  существует:      да")
    log(f"  приватный:       {'да' if getattr(info, 'private', False) else 'нет'}")
    licence = getattr(info, "card_data", None)
    licence_value = None
    if isinstance(licence, dict):
        licence_value = licence.get("license")
    log(f"  лицензия (карточка): {licence_value or 'не указана'}")
    downloads = getattr(info, "downloads", None)
    if downloads is not None:
        log(f"  загрузок:        {downloads}")

    files = 0
    total = 0
    labels = 0
    pngs = 0
    readme = False
    inventory = False
    for entry in api.list_repo_tree(repo_id=args.repo_id, repo_type=repo_type,
                                    recursive=True):
        path = getattr(entry, "path", "")
        if getattr(entry, "size", None) is None:
            continue  # это папка
        files += 1
        total += int(entry.size)
        if path == "README.md":
            readme = True
        elif path.endswith("labels.jsonl"):
            labels += 1
        elif path.lower().endswith(".png"):
            pngs += 1
        elif path == INVENTORY_NAME:
            inventory = True

    log(f"  файлов:          {files}")
    log(f"  суммарный размер: {human_bytes(total)}")
    log(f"  README.md:       {'есть' if readme else 'НЕТ'}")
    log(f"  labels.jsonl:    {labels} шт.")
    log(f"  PNG:             {pngs} шт.")
    log(f"  {INVENTORY_NAME}: {'есть' if inventory else 'нет'}")
    return EXIT_OK


# =====================================================================================
# CLI
# =====================================================================================

def build_parser() -> argparse.ArgumentParser:
    """Разобрать аргументы командной строки."""
    parser = argparse.ArgumentParser(
        prog="publish_hf.py",
        description="Публикация датасета и модели CaptchaOCR на Hugging Face Hub.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Примеры:\n"
            "  publish_hf.py dataset --repo-id user/repo --data-dir dataset --dry-run\n"
            "  publish_hf.py dataset --repo-id user/repo --data-dir dataset\n"
            "  publish_hf.py model --repo-id user/model --checkpoint train/run/main\n"
            "  publish_hf.py check --repo-id user/repo\n"
        ),
    )
    parser.add_argument("--token", default=None,
                        help="токен Hugging Face (по умолчанию $HF_TOKEN или токен CLI)")
    sub = parser.add_subparsers(dest="command", required=True)

    ds = sub.add_parser("dataset", help="выложить датасет")
    ds.add_argument("--repo-id", required=True, help="id репозитория, напр. user/repo")
    ds.add_argument("--data-dir", default=str(REPO_ROOT / "dataset"),
                    help="каталог с деревьями датасета (по умолчанию dataset)")
    ds.add_argument("--dry-run", action="store_true",
                    help="только показать план, ничего не отправляя")
    ds.add_argument("--private", action="store_true", help="создать приватный репозиторий")
    ds.add_argument("--confirm-create", action="store_true",
                    help="разрешить создание репозитория в чужом namespace")
    ds.add_argument("--include-external-url", action="store_true",
                    help="включить типы, у которых source указывает на внешний URL "
                         "(по умолчанию они исключены — правила проекта их не публикуют)")

    md = sub.add_parser("model", help="выложить модель")
    md.add_argument("--repo-id", required=True, help="id репозитория модели")
    md.add_argument("--checkpoint", required=True,
                    help="каталог с чекпоинтом или сам файл .pt")
    md.add_argument("--results", default=None,
                    help="JSON с результатами замера для карточки")
    md.add_argument("--dataset-repo", default=None,
                    help="id репозитория датасета (для ссылки в карточке)")
    md.add_argument("--data-dir", default=None,
                    help="каталог датасета — из него берётся размер обучающей выборки")
    md.add_argument("--image-height", type=int, default=48, help="высота входа модели")
    md.add_argument("--image-width", type=int, default=320, help="ширина входа модели")
    md.add_argument("--mean", type=float, default=0.5, help="mean препроцессора")
    md.add_argument("--std", type=float, default=0.5, help="std препроцессора")
    md.add_argument("--dry-run", action="store_true",
                    help="только показать план, ничего не отправляя")
    md.add_argument("--private", action="store_true", help="создать приватный репозиторий")
    md.add_argument("--confirm-create", action="store_true",
                    help="разрешить создание репозитория в чужом namespace")

    ck = sub.add_parser("check", help="проверить содержимое репозитория")
    ck.add_argument("--repo-id", required=True, help="id репозитория")
    ck.add_argument("--repo-type", default="dataset", choices=["dataset", "model"],
                    help="тип репозитория")
    return parser


def cmd_dataset(args) -> int:
    """Команда dataset."""
    data_dir = Path(args.data_dir).resolve()
    if not data_dir.is_dir():
        raise SystemExit(f"Каталог с данными не найден: {data_dir}")

    types = find_type_dirs(data_dir)
    if not types:
        raise SystemExit(f"В {data_dir} не найдено ни одного labels.jsonl — "
                         f"данные не собраны.")
    for t in types:
        collect_type(t)

    # По правилам проекта (AGENTS.md §8) материалы сторонних коммерческих сервисов
    # не публикуются. Признак такого происхождения выводится из самих `labels.jsonl`:
    # тип исключается, только если его `source` указывает на внешний URL (схема
    # http(s):// или доменное имя). Собственные рендеры наших генераторов — в том числе
    # чисто-румные реконструкции, собранные по референсным скриншотам, — внешнего URL
    # не содержат и публикуются. Имён типов в скрипте нет: переименование каталога
    # ничего в этом правиле не ломает.
    external = [t for t in types if t.inventory["external_url"]]
    if external:
        log(f"Типы с внешним URL в source: {len(external)} — "
            + ", ".join(t.type_id for t in external))
        if args.include_external_url:
            warn("Флаг --include-external-url: эти типы попадут в публикацию. "
                 "Убедитесь, что это допустимо по правилам проекта.")
        else:
            log("По правилам проекта материалы, взятые с чужого сайта, "
                "не публикуются — эти типы ИСКЛЮЧЕНЫ из загрузки.")
            log("Чтобы всё же включить их (осознанно), добавьте --include-external-url.")
            types = [t for t in types if not t.inventory["external_url"]]

    inventory = build_inventory(types, data_dir)

    template = DATASET_CARD_TEMPLATE.read_text(encoding="utf-8")
    card, leftovers = render_template(template, dataset_card_values(inventory, args.repo_id))
    if leftovers:
        warn("В шаблоне карточки остались неподставленные плейсхолдеры: "
             + ", ".join(leftovers))

    totals = inventory["totals"]
    log("=== План загрузки датасета ===")
    log(f"  репозиторий:      {args.repo_id} (dataset)")
    log(f"  каталог данных:   {inventory['data_dir']}")
    log(f"  раскладка в репо: {inventory['layout']}")
    log(f"  деревьев:         {totals['trees']}  ({', '.join(t['tree'] for t in inventory['trees'])})")
    log(f"  типов:            {totals['types']}")
    log(f"  плагинов:         {totals['plugins']}")
    log(f"  сэмплов (строк):  {totals['samples']}")
    log(f"  PNG-файлов:       {totals['png_files']}")
    log(f"  меток labels.jsonl: {totals['types']}")
    log(f"  суммарный размер: {human_bytes(totals['bytes'])} ({totals['bytes']} Б)")
    log(f"  типов с полосой:  {totals['types_with_roi']} "
        f"(строк с roi: {totals['rows_with_roi']}, без: {totals['rows_without_roi']})")
    log(f"  типов text != answer: {totals['types_text_ne_answer']}")
    log(f"  режимы: faithful {totals['types_faithful']}, clean-room "
        f"{totals['types_clean_room']}, reconstructed {totals['types_reconstructed']}, "
        f"не определён {totals['types_mode_unknown']}")
    log(f"  размер карточки:  {len(card.encode('utf-8'))} Б")
    log(f"  размер инвентаря: {len(json.dumps(inventory, ensure_ascii=False).encode('utf-8'))} Б")
    log("  первые файлы:")
    shown = 0
    for t in types:
        for png in t.pngs[:1]:
            log(f"    {t.repo_dir()}/{png.name}")
            shown += 1
            break
        if shown >= 8:
            break
    log(f"    ... и ещё {max(0, totals['png_files'] + totals['types'] + 2 - shown)} файлов")

    if args.dry_run:
        log("")
        log("--dry-run: ничего не отправлял, сеть не трогал.")
        token = resolve_token(args.token)
        if not token:
            log("")
            log("Токен не найден — для реальной загрузки понадобится:")
            log("  $env:HF_TOKEN = \"hf_...\"   или   .venv-gpu\\Scripts\\hf.exe auth login")
        return EXIT_OK

    uploaded = upload_dataset(args, inventory, card, types)
    log(f"Готово: загружено {uploaded} файлов в {args.repo_id}.")
    return EXIT_OK


def cmd_model(args) -> int:
    """Команда model."""
    meta, files, staging = collect_model(args)
    info = meta["info"]
    try:
        results_block, results_warning = extract_results(
            Path(args.results) if args.results else None)
        info["results_block"] = results_block
        info["results_warning"] = results_warning

        if args.data_dir:
            data_dir = Path(args.data_dir).resolve()
            if data_dir.is_dir():
                types = find_type_dirs(data_dir)
                for t in types:
                    collect_type(t)
                inv = build_inventory(types, data_dir)
                info["n_train_types"] = str(inv["totals"]["types"])
                info["n_train_samples"] = str(inv["totals"]["samples"])
            else:
                warn(f"Каталог {data_dir} не найден — размер обучающей выборки не указан.")

        template = MODEL_CARD_TEMPLATE.read_text(encoding="utf-8")
        card, leftovers = render_template(template, model_card_values(args, info))
        if leftovers:
            warn("В шаблоне карточки остались неподставленные плейсхолдеры: "
                 + ", ".join(leftovers))
        if results_warning:
            warn(results_warning)

        log("=== План загрузки модели ===")
        log(f"  репозиторий:      {args.repo_id} (model)")
        log(f"  чекпоинт:         {info.get('checkpoint')}")
        log(f"  веса:             {info.get('weights_source', 'model.safetensors')}")
        log(f"  config.json:      {info.get('config_source')}")
        log(f"  preprocessor:      {info.get('preprocessor_source')}")
        log(f"  character_list:   {info.get('character_list_source')}")
        log(f"  классов:          {info.get('num_classes', 'не выведено')}")
        log(f"  charset:          {info.get('charset') or 'не указан'}")
        log(f"  вход:             {info.get('image_height')}x{info.get('image_width')}, "
            f"mean={info.get('image_mean')}, std={info.get('image_std')}")
        for rel in info.get("extra_files", []):
            log(f"  дополнительно:    {rel}")
        total = sum(p.stat().st_size for _, p in files)
        log(f"  файлов к загрузке: {len(files) + 3}")
        log(f"  суммарный размер: {human_bytes(total)}")

        if args.dry_run:
            log("")
            log("--dry-run: ничего не отправлял, сеть не трогал.")
            token = resolve_token(args.token)
            if not token:
                log("")
                log("Токен не найден — для реальной загрузки понадобится:")
                log("  $env:HF_TOKEN = \"hf_...\"   или   .venv-gpu\\Scripts\\hf.exe auth login")
            return EXIT_OK

        uploaded = upload_model(args, meta, files, card)
        log(f"Готово: загружено {uploaded} файлов в {args.repo_id}.")
        return EXIT_OK
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    """Точка входа."""
    args = build_parser().parse_args(argv)
    if args.command == "dataset":
        return cmd_dataset(args)
    if args.command == "model":
        return cmd_model(args)
    if args.command == "check":
        return check_repo(args)
    return EXIT_ERROR


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:  # pragma: no cover
        log("Прервано пользователем.")
        raise SystemExit(EXIT_ERROR)
    except Exception as exc:  # noqa: BLE001
        log(f"ОШИБКА: {type(exc).__name__}: {exc}")
        raise SystemExit(EXIT_ERROR)
