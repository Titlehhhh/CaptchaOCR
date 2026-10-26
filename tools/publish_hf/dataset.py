import json
import os
from pathlib import Path

from .constants import DATA_PREFIX, REPO_ROOT
from .utils import charset_kind, has_external_url, median, mode_from_source

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

