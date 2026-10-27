"""The plan of the upload: what is already there, what has to go up, what is stale.

A file counts as uploaded only if its **content** matches (sha256 for the LFS files,
git-sha1 for the plain ones) - not merely its size.  The dataset was re-rendered, so the
pictures 001-100 differ from the published ones and have to be overwritten.
"""

import hashlib
import os
from pathlib import Path

from tools.publish_hf.utils import log

#: Куда внутри репозитория ложится датасет — та же раскладка, что и раньше.
DATA_PREFIX = "data"

#: Имя машинно-читаемой сводки в корне репозитория.
INVENTORY_NAME = "dataset_inventory.json"

#: Ретраи на один батч (коммит).
MAX_RETRIES = 4
RETRY_SLEEP = 8.0

#: Сколько файлов кладётся в ОДИН коммит (по умолчанию); переопределяется
#: флагом ``--batch-files``. 250 файлов — это единицы мегабайт на коммит.
DEFAULT_BATCH_FILES = 250


# =====================================================================================
# Дайджесты: что уже залито, а что надо перезаписать
# =====================================================================================

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha1(path: Path) -> str:
    """sha1 объекта git для обычного (не-LFS) файла: ``sha1("blob <size>\\0" + data)``."""
    size = path.stat().st_size
    digest = hashlib.sha1()
    digest.update(b"blob %d\0" % size)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remote_digests(api, repo_id: str) -> dict[str, str]:
    """Карта «путь в репозитории -> дайджест содержимого» для уже залитого.

    Для LFS-файлов дайджест — sha256 из ``lfs.sha256``, для обычных — git-sha1 из
    ``blob_id``. Сравнение по **содержимому**, а не по размеру: картинки
    перерисованы, и старые 001–100 надо перезаписать, а не пропустить.
    """
    digests: dict[str, str] = {}
    try:
        entries = list(api.list_repo_tree(repo_id=repo_id, repo_type="dataset",
                                          recursive=True))
    except Exception as exc:  # noqa: BLE001 — репозитория ещё нет
        log(f"  (репозиторий недоступен: {type(exc).__name__})")
        return digests
    for entry in entries:
        path = getattr(entry, "path", None)
        if path is None:
            continue
        lfs = getattr(entry, "lfs", None)
        if lfs is not None and getattr(lfs, "sha256", None):
            digests[path] = str(lfs.sha256)
        else:
            blob_id = getattr(entry, "blob_id", None)
            if blob_id:
                digests[path] = str(blob_id)
    return digests


def local_digest(path: Path, is_lfs: bool) -> str:
    return sha256_file(path) if is_lfs else git_blob_sha1(path)


def is_lfs_remote(path_in_repo: str, digests: dict[str, str], sizes: dict[str, int]) -> bool:
    """Файл на сервере лежит в LFS? Определяем по тому, есть ли у него lfs-дайджест."""
    # lfs-файлы дают 64-символьный sha256, обычные — 40-символьный git-sha1.
    digest = digests.get(path_in_repo, "")
    return len(digest) == 64


# =====================================================================================
# План
# =====================================================================================

class Plan:
    """План загрузки: список батчей (имя -> [(путь в репозитории, локальный файл)])."""

    def __init__(self) -> None:
        self.batches: list[tuple[str, list[tuple[str, Path]]]] = []

    def add_batch(self, name: str, items: list[tuple[str, Path]]) -> None:
        if items:
            self.batches.append((name, items))

    def total_files(self) -> int:
        return sum(len(items) for _, items in self.batches)

    def total_bytes(self) -> int:
        return sum(p.stat().st_size for _, items in self.batches for _, p in items)

    def chunk_count(self, batch_files: int) -> int:
        """Сколько коммитов получится, если резать каждый батч по N файлов."""
        return sum(chunk_count(len(items), batch_files) for _, items in self.batches)


def chunk_count(files: int, batch_files: int) -> int:
    """Число кусков по ``batch_files`` файлов (0 файлов — 0 коммитов)."""
    per = max(1, int(batch_files))
    return -(-files // per)


def create_commit_label(name: str, index: int, total: int) -> str:
    """Сообщение коммита: имя батча и номер куска (``... (1/40)``)."""
    return f"CaptchaOCR dataset: {name} ({index}/{total})"


def chunked(items: list, batch_files: int) -> list[list]:
    """Разрезать список на куски не длиннее ``batch_files``."""
    per = max(1, int(batch_files))
    return [items[i:i + per] for i in range(0, len(items), per)]


def build_plan(types: list, digests: dict[str, str]) -> tuple[Plan, list[str]]:
    """План: сначала все ``labels.jsonl`` (аудит-тропа), потом PNG по типам.

    Файл считается уже залитым только если его **содержимое** совпадает с
    локальным; иначе он в плане (перезапись).
    """
    plan = Plan()
    replaced: list[str] = []

    labels_items: list[tuple[str, Path]] = []
    for t in types:
        path_in_repo = f"{DATA_PREFIX}/{t.type_id}/labels.jsonl"
        remote = digests.get(path_in_repo)
        if remote is None or remote != git_blob_sha1(t.labels_path):
            labels_items.append((path_in_repo, t.labels_path))
        else:
            replaced.append(path_in_repo)
    plan.add_batch("labels.jsonl (all types)", labels_items)

    for t in types:
        items: list[tuple[str, Path]] = []
        for png in t.pngs:
            path_in_repo = f"{DATA_PREFIX}/{t.type_id}/{png.name}"
            remote = digests.get(path_in_repo)
            if remote is None or remote != sha256_file(png):
                items.append((path_in_repo, png))
        plan.add_batch(f"png: {t.type_id}", items)
    return plan, replaced


def local_target_paths(types: list) -> set[str]:
    """Полный набор путей, которые ДОЛЖНЫ быть в репозитории для локального дерева.

    Это все ``labels.jsonl`` и все PNG всех типов — не только изменённые файлы
    плана, а весь целевой набор: по нему считается устаревшее (stale).
    """
    paths: set[str] = set()
    for t in types:
        paths.add(f"{DATA_PREFIX}/{t.type_id}/labels.jsonl")
        for png in t.pngs:
            paths.add(f"{DATA_PREFIX}/{t.type_id}/{png.name}")
    return paths


# =====================================================================================
# Устаревшие файлы (--prune)
# =====================================================================================

def is_protected_path(path_in_repo: str) -> bool:
    """Файл, который ``--prune`` не удаляет никогда (где бы он ни лежал)."""
    name = path_in_repo.rsplit("/", 1)[-1]
    return (name in {"README.md", INVENTORY_NAME, ".gitattributes"}
            or name.startswith("LICENSE"))


def is_remote_folder(entry) -> bool:
    """Каталог ли это в ``list_repo_tree``.

    В ``huggingface_hub`` >= 1.x у записей нет поля ``type``: каталог приходит
    объектом ``RepoFolder``, у файла есть ``blob_id``/``size``. Старые версии
    отдавали ``type == "directory"`` — поддерживаем оба вида.
    """
    if type(entry).__name__ == "RepoFolder":
        return True
    kind = getattr(entry, "type", None)
    if isinstance(kind, str) and kind.lower() in ("directory", "dir", "folder"):
        return True
    return getattr(entry, "blob_id", None) is None and not hasattr(entry, "size")


def remote_files(api, repo_id: str) -> dict[str, int]:
    """Карта «путь в репозитории -> размер» для всех ФАЙЛОВ удалённого дерева."""
    files: dict[str, int] = {}
    try:
        entries = list(api.list_repo_tree(repo_id=repo_id, repo_type="dataset",
                                          recursive=True))
    except Exception as exc:  # noqa: BLE001 — репозитория ещё нет
        log(f"  (репозиторий недоступен: {type(exc).__name__})")
        return files
    for entry in entries:
        path = getattr(entry, "path", None)
        if path is None or is_remote_folder(entry):
            continue
        files[path] = getattr(entry, "size", 0) or 0
    return files


def is_stale_path(path_in_repo: str, local: set[str]) -> bool:
    """Путь под ``data/``, которого нет локально и который не защищён."""
    return (path_in_repo.startswith(DATA_PREFIX + "/")
            and path_in_repo not in local
            and not is_protected_path(path_in_repo))


def stale_remote_files(remote: dict[str, int], local: set[str]) -> dict[str, int]:
    """Удалённые файлы под ``data/``, которых нет в локальном целевом наборе."""
    return {path: size for path, size in remote.items() if is_stale_path(path, local)}


def stale_type_ids(stale: dict[str, int], types: list) -> list[str]:
    """Каталоги типов, которые есть на сервере, но которых нет локально.

    Берутся только листовые каталоги устаревших файлов: промежуточные
    (``data``, ``data/out``, ``data/out/<owner>``) — не типы и в лог не идут.
    """
    known = {f"{DATA_PREFIX}/{t.type_id}" for t in types}
    directories = {path.rsplit("/", 1)[0] for path in stale}
    leaves = [directory for directory in directories
              if directory not in known
              and not any(other.startswith(directory + "/")
                          for other in directories)]
    return sorted(leaves)


def type_id_of_dir(directory: str) -> str:
    """``data/out/x/y`` -> ``out/x/y`` (для читаемого лога)."""
    prefix = DATA_PREFIX + "/"
    return directory[len(prefix):] if directory.startswith(prefix) else directory


# =====================================================================================
# Сбор данных
# =====================================================================================

def find_types(data_dir: Path, trees: list[str] | None = None) -> list:
    """Все типы капчи (каталоги с ``labels.jsonl``) — без ``real_shots``.

    ``trees`` — если задан, берутся только эти деревья (``out``, ``out_ru``).
    """
    from tools.publish_hf.dataset import find_type_dirs

    types = find_type_dirs(data_dir)
    if trees:
        wanted = {t.strip().lower() for t in trees if t.strip()}
        types = [t for t in types if t.tree.lower() in wanted]
    return types


def collect(types: list) -> None:
    """Заполнить сводку по каждому типу (числа берутся из ``labels.jsonl``)."""
    from tools.publish_hf.dataset import collect_type

    for t in types:
        collect_type(t)


def count_real_shots(data_dir: Path) -> tuple[int, int]:
    """Сколько в папках ``real_shots`` референсных скриншотов и файлов всего.

    Их НЕ публикуем. Скриншоты — это PNG; рядом лежат ещё и заметки (.md/.txt),
    поэтому для карточки важны оба числа.
    """
    shots = 0
    files = 0
    for dirpath, dirnames, filenames in os.walk(data_dir):
        if "real_shots" in Path(dirpath).parts:
            for name in filenames:
                files += 1
                if name.lower().endswith(".png"):
                    shots += 1
            dirnames[:] = []
    return shots, files
