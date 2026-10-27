import os
import re
import sys
from pathlib import Path


def log(message: str = "") -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print(f"ВНИМАНИЕ: {message}", file=sys.stderr, flush=True)


def human_bytes(n: int) -> str:
    value = float(n)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if value < 1024 or unit == "ТБ":
            return f"{value:.1f} {unit}".replace(".0 ", " ")
        value /= 1024
    return f"{value:.1f} ТБ"


def median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def repo_path_of(path: Path, base: Path) -> str:
    return Path(os.path.relpath(path, base)).as_posix()


DOMAIN_PATH_RE = re.compile(r"\b[a-z0-9][a-z0-9-]*\.[a-z]{2,}/", re.IGNORECASE)


def has_external_url(source: str) -> bool:
    text = source or ""
    lowered = text.lower()
    if "http://" in lowered or "https://" in lowered:
        return True
    return bool(DOMAIN_PATH_RE.search(text))


def mode_from_source(source: str) -> str:
    text = (source or "").lower()
    if "reconstruct" in text:
        return "reconstructed"
    if "clean-room" in text or "clean room" in text:
        return "clean-room"
    return ""


def charset_kind(chars: set[str]) -> str:
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
