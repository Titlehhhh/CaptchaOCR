"""The Hugging Face Hub side of the Parquet export: upload, delete, verify."""

import os
import time
from pathlib import Path

from .common import log, warn
from .index import DatasetIndex

#: Prefix inside the Hub repository where the shards are uploaded.
DATA_PREFIX = "data"

#: Old loose-PNG locations on the Hub -- the only paths ``--upload`` deletes.
OLD_TREE_PREFIXES = ("data/out/", "data/out_ru/")

#: Delete protocol (see the task contract).
DELETE_CHUNK_PATHS = 1000
DELETE_NUM_THREADS = 24
UPLOAD_NUM_THREADS = 8
MAX_RETRIES = 5
RETRY_SLEEP = 8.0

EXIT_OK = 0
EXIT_ERROR = 1

PROTECTED_NAMES = frozenset({"README.md", "dataset_inventory.json", ".gitattributes"})


def resolve_token(explicit: str | None) -> str | None:
    """Token from --token, the environment/CLI, or the project's .hf-cache/token."""
    if explicit:
        return explicit.strip()
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    try:
        from huggingface_hub import get_token

        stored = get_token()
        if stored:
            return stored
    except Exception:  # noqa: BLE001 -- token discovery is best-effort
        pass
    root = Path(__file__).resolve().parent.parent.parent
    token_file = root / ".hf-cache" / "token"
    try:
        value = token_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    except OSError:
        pass
    return None


def api_for(token: str | None):
    from huggingface_hub import HfApi

    return HfApi(token=token)


def is_protected_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name in PROTECTED_NAMES or name.startswith("LICENSE")


def is_old_tree_path(path: str) -> bool:
    """True for deletable paths under the retired ``data/out`` / ``data/out_ru`` trees."""
    if not path.startswith(OLD_TREE_PREFIXES):
        return False
    return not is_protected_path(path)


def is_remote_folder(entry) -> bool:
    """Directory detection that works with huggingface_hub >= 1.x and older."""
    if type(entry).__name__ == "RepoFolder":
        return True
    kind = getattr(entry, "type", None)
    if isinstance(kind, str) and kind.lower() in ("directory", "dir", "folder"):
        return True
    return getattr(entry, "blob_id", None) is None and not hasattr(entry, "size")


def list_remote_files(api, repo_id: str) -> dict[str, int]:
    """Map every remote file path to its size (folders are skipped)."""
    entries = api.list_repo_tree(repo_id=repo_id, repo_type="dataset", recursive=True)
    files: dict[str, int] = {}
    for entry in entries:
        path = getattr(entry, "path", None)
        if path is None or is_remote_folder(entry):
            continue
        files[path] = getattr(entry, "size", 0) or 0
    return files


def create_commit_with_retries(api, repo_id: str, operations: list, message: str,
                               num_threads: int, what: str) -> None:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            api.create_commit(repo_id=repo_id, operations=operations,
                              repo_type="dataset", commit_message=message,
                              num_threads=num_threads)
            return
        except Exception as exc:  # noqa: BLE001 -- network failure is retryable
            last_error = exc
            wait = RETRY_SLEEP * attempt
            warn(f"{what} failed (attempt {attempt}/{MAX_RETRIES}): "
                 f"{type(exc).__name__}: {exc}; retrying in {wait:.0f} s")
            time.sleep(wait)
    raise RuntimeError(f"{what} failed after {MAX_RETRIES} attempts: {last_error}")


def upload_shards(api, repo_id: str, shards: list[tuple[Path, int]]) -> None:
    from huggingface_hub import CommitOperationAdd

    log("")
    log("=== Upload Parquet shards ===")
    total = len(shards)
    for number, (path, size) in enumerate(shards, start=1):
        operation = CommitOperationAdd(
            path_in_repo=f"{DATA_PREFIX}/{path.name}", path_or_fileobj=path)
        create_commit_with_retries(
            api, repo_id, [operation],
            f"CaptchaOCR: Parquet shard {path.name} ({number}/{total})",
            UPLOAD_NUM_THREADS, f"upload {path.name}")
        log(f"  uploaded {number}/{total}: data/{path.name} "
            f"({size:,} B, {human(size)}")


def human(size: int) -> str:
    from .common import human_bytes
    return human_bytes(size)


def upload_readme(api, repo_id: str, out_dir: Path) -> None:
    from huggingface_hub import CommitOperationAdd

    readme = out_dir / "README.md"
    if not readme.is_file():
        raise RuntimeError(f"README not found: {readme}")
    operation = CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=readme)
    create_commit_with_retries(api, repo_id, [operation],
                               "CaptchaOCR: Parquet dataset card",
                               UPLOAD_NUM_THREADS, "upload README.md")
    log(f"  uploaded README.md ({readme.stat().st_size:,} B)")


def delete_old_png_tree(api, repo_id: str, remote_files: dict[str, int]) -> int:
    """Delete every remote path under data/out and data/out_ru in 1000-path chunks."""
    from huggingface_hub import CommitOperationDelete

    old_paths = sorted(path for path in remote_files if is_old_tree_path(path))
    if not old_paths:
        log("  no old loose-PNG paths found under data/out or data/out_ru")
        return 0
    total_bytes = sum(remote_files[path] for path in old_paths)
    chunks = [old_paths[i:i + DELETE_CHUNK_PATHS]
              for i in range(0, len(old_paths), DELETE_CHUNK_PATHS)]
    log("")
    log("=== Delete old loose-PNG tree ===")
    log(f"  paths: {len(old_paths):,} ({human(total_bytes)}) in "
        f"{len(chunks)} chunks of up to {DELETE_CHUNK_PATHS} paths")
    deleted = 0
    for number, chunk in enumerate(chunks, start=1):
        operations = [CommitOperationDelete(path_in_repo=path) for path in chunk]
        create_commit_with_retries(
            api, repo_id, operations,
            f"CaptchaOCR: remove old PNG tree ({number}/{len(chunks)})",
            DELETE_NUM_THREADS,
            f"delete chunk {number}/{len(chunks)}")
        deleted += len(chunk)
        log(f"  chunk {number}/{len(chunks)}: deleted {len(chunk):,} paths "
            f"({deleted:,}/{len(old_paths):,})")
    log(f"  deleted {deleted:,} paths in {len(chunks)} commits")
    return deleted


def verify_remote(api, repo_id: str, out_dir: Path) -> int:
    """Verify the remote repository against the local shard set."""
    local_shards = sorted((out_dir / DATA_PREFIX).glob("*.parquet"))
    try:
        remote_files = list_remote_files(api, repo_id)
    except Exception as exc:  # noqa: BLE001
        log(f"MISMATCH: cannot list remote tree: {type(exc).__name__}: {exc}")
        return EXIT_ERROR

    remote_parquet = {path: size for path, size in remote_files.items()
                      if path.startswith(DATA_PREFIX + "/") and path.endswith(".parquet")}
    remote_png = {path: size for path, size in remote_files.items()
                  if path.startswith(DATA_PREFIX + "/") and path.lower().endswith(".png")}
    old_left = {path: size for path, size in remote_files.items()
                if is_old_tree_path(path)}
    parquet_bytes = sum(remote_parquet.values())

    log("=== Remote verification ===")
    log(f"repo:                     {repo_id}")
    log(f"local shards:             {len(local_shards)}")
    log(f"remote Parquet files:     {len(remote_parquet)}")
    log(f"remote Parquet bytes:     {parquet_bytes:,} B ({human(parquet_bytes)})")
    log(f"remote PNG under data/:   {len(remote_png)}")
    log(f"remote files in old tree: {len(old_left)}")
    log(f"README.md present:        {'README.md' in remote_files}")

    problems: list[str] = []
    if len(remote_parquet) != len(local_shards):
        problems.append(f"Parquet count: remote {len(remote_parquet)} != "
                        f"local {len(local_shards)}")
    if remote_png:
        problems.append(f"{len(remote_png)} PNG still under data/")
    missing = [path.name for path in local_shards
               if f"{DATA_PREFIX}/{path.name}" not in remote_parquet]
    if missing:
        problems.append(f"{len(missing)} local shard(s) missing remotely: {missing[:5]}")
    if "README.md" not in remote_files:
        warn("README.md is missing at the repository root")
    if old_left:
        problems.append(f"{len(old_left)} old-tree file(s) remain under data/out or "
                        f"data/out_ru")

    if problems:
        log("MISMATCH")
        for problem in problems:
            log(f"  - {problem}")
        return EXIT_ERROR
    log("OK")
    return EXIT_OK


def upload(api, repo_id: str, out_dir: Path, default_data_dir: Path,
           default_target_bytes: int, export_fn) -> int:
    data_dir = out_dir / DATA_PREFIX
    local_shards = sorted(data_dir.glob("*.parquet"))
    if not local_shards:
        log("no local Parquet shards, exporting first")
        result = export_fn(default_data_dir, out_dir, default_target_bytes)
        shards = result.shards
    else:
        shards = [(path, path.stat().st_size) for path in local_shards]
        log(f"using {len(shards)} existing local shards in {data_dir}")
    upload_shards(api, repo_id, shards)
    upload_readme(api, repo_id, out_dir)

    # Re-list right before deleting: only the old PNG tree is touched.
    remote_files = list_remote_files(api, repo_id)
    delete_old_png_tree(api, repo_id, remote_files)

    # Final state (also the body of --verify).
    log("")
    return verify_remote(api, repo_id, out_dir)
