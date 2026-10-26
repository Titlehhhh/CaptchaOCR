import os
import re
import sys
from pathlib import Path

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


