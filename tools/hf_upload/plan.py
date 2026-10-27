
import hashlib
import os
from pathlib import Path

from tools.publish_hf.utils import log

DATA_PREFIX = "data"

INVENTORY_NAME = "dataset_inventory.json"

MAX_RETRIES = 4
RETRY_SLEEP = 8.0

DEFAULT_BATCH_FILES = 250


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha1(path: Path) -> str:
    size = path.stat().st_size
    digest = hashlib.sha1()
    digest.update(b"blob %d\0" % size)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remote_digests(api, repo_id: str) -> dict[str, str]:
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
    digest = digests.get(path_in_repo, "")
    return len(digest) == 64


class Plan:
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
        return sum(chunk_count(len(items), batch_files) for _, items in self.batches)


def chunk_count(files: int, batch_files: int) -> int:
    per = max(1, int(batch_files))
    return -(-files // per)


def create_commit_label(name: str, index: int, total: int) -> str:
    return f"CaptchaOCR dataset: {name} ({index}/{total})"


def chunked(items: list, batch_files: int) -> list[list]:
    per = max(1, int(batch_files))
    return [items[i:i + per] for i in range(0, len(items), per)]


def build_plan(types: list, digests: dict[str, str]) -> tuple[Plan, list[str]]:
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
    paths: set[str] = set()
    for t in types:
        paths.add(f"{DATA_PREFIX}/{t.type_id}/labels.jsonl")
        for png in t.pngs:
            paths.add(f"{DATA_PREFIX}/{t.type_id}/{png.name}")
    return paths


def is_protected_path(path_in_repo: str) -> bool:
    name = path_in_repo.rsplit("/", 1)[-1]
    return (name in {"README.md", INVENTORY_NAME, ".gitattributes"}
            or name.startswith("LICENSE"))


def is_remote_folder(entry) -> bool:
    if type(entry).__name__ == "RepoFolder":
        return True
    kind = getattr(entry, "type", None)
    if isinstance(kind, str) and kind.lower() in ("directory", "dir", "folder"):
        return True
    return getattr(entry, "blob_id", None) is None and not hasattr(entry, "size")


def remote_files(api, repo_id: str) -> dict[str, int]:
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
    return (path_in_repo.startswith(DATA_PREFIX + "/")
            and path_in_repo not in local
            and not is_protected_path(path_in_repo))


def stale_remote_files(remote: dict[str, int], local: set[str]) -> dict[str, int]:
    return {path: size for path, size in remote.items() if is_stale_path(path, local)}


def stale_type_ids(stale: dict[str, int], types: list) -> list[str]:
    known = {f"{DATA_PREFIX}/{t.type_id}" for t in types}
    directories = {path.rsplit("/", 1)[0] for path in stale}
    leaves = [directory for directory in directories
              if directory not in known
              and not any(other.startswith(directory + "/")
                          for other in directories)]
    return sorted(leaves)


def type_id_of_dir(directory: str) -> str:
    prefix = DATA_PREFIX + "/"
    return directory[len(prefix):] if directory.startswith(prefix) else directory


def find_types(data_dir: Path, trees: list[str] | None = None) -> list:
    from tools.publish_hf.dataset import find_type_dirs

    types = find_type_dirs(data_dir)
    if trees:
        wanted = {t.strip().lower() for t in trees if t.strip()}
        types = [t for t in types if t.tree.lower() in wanted]
    return types


def collect(types: list) -> None:
    from tools.publish_hf.dataset import collect_type

    for t in types:
        collect_type(t)


def count_real_shots(data_dir: Path) -> tuple[int, int]:
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
