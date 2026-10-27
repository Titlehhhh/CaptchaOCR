
import time

from tools.publish_hf.utils import log, warn

from .plan import (DEFAULT_BATCH_FILES, MAX_RETRIES, RETRY_SLEEP, chunked,
                   create_commit_label)

DEFAULT_NUM_THREADS = 16
MIN_NUM_THREADS = 1
MAX_NUM_THREADS = 64

NUM_THREADS = DEFAULT_NUM_THREADS


def set_num_threads(value: int) -> int:
    global NUM_THREADS
    NUM_THREADS = value
    return NUM_THREADS


def current_num_threads() -> int:
    return NUM_THREADS


def clamp_num_threads(value: int) -> int:
    clamped = max(MIN_NUM_THREADS, min(MAX_NUM_THREADS, int(value)))
    if clamped != int(value):
        warn(f"--num-threads {value} вне диапазона "
             f"[{MIN_NUM_THREADS}, {MAX_NUM_THREADS}], использую {clamped}")
    return clamped


def create_commit_with_retries(api, repo_id: str, operations: list, label: str) -> None:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            api.create_commit(repo_id=repo_id, operations=operations,
                              repo_type="dataset", commit_message=label,
                              num_threads=NUM_THREADS)
            return
        except Exception as exc:  # noqa: BLE001 — сеть может упасть в любой момент
            last_error = exc
            wait = RETRY_SLEEP * attempt
            warn(f"коммит «{label}» не залился (попытка {attempt}/{MAX_RETRIES}): "
                 f"{type(exc).__name__}: {exc}; жду {wait:.0f} с")
            time.sleep(wait)
    raise RuntimeError(f"коммит «{label}» не залился после {MAX_RETRIES} попыток: "
                       f"{last_error}")


def upload_batch(api, repo_id: str, name: str,
                 items: list[tuple[str, "object"]],
                 batch_files: int = DEFAULT_BATCH_FILES) -> int:
    from huggingface_hub import CommitOperationAdd

    chunks = chunked(items, batch_files)
    total = len(chunks)
    uploaded = 0
    for index, chunk in enumerate(chunks, start=1):
        operations = [CommitOperationAdd(path_in_repo=path, path_or_fileobj=local)
                      for path, local in chunk]
        create_commit_with_retries(
            api, repo_id, operations,
            create_commit_label(name, index, total))
        uploaded += len(chunk)
        log(f"    commit {index}/{total}: {name} — {len(chunk)} files")
    return uploaded


def prune_remote(api, repo_id: str, stale: dict[str, int],
                 batch_files: int = DEFAULT_BATCH_FILES) -> tuple[int, int]:
    from huggingface_hub import CommitOperationDelete

    paths = sorted(stale)
    chunks = chunked(paths, batch_files)
    total = len(chunks)
    deleted = 0
    deleted_bytes = 0
    for index, chunk in enumerate(chunks, start=1):
        operations = [CommitOperationDelete(path_in_repo=path) for path in chunk]
        create_commit_with_retries(
            api, repo_id, operations,
            f"CaptchaOCR dataset: prune stale files ({index}/{total})")
        deleted += len(chunk)
        deleted_bytes += sum(stale[path] for path in chunk)
        log(f"    commit {index}/{total}: prune — {len(chunk)} files")
    return deleted, deleted_bytes


def upload_metadata(api, repo_id: str, files: dict[str, bytes]) -> None:
    from huggingface_hub import CommitOperationAdd

    operations = [CommitOperationAdd(path_in_repo=path, path_or_fileobj=data)
                  for path, data in files.items()]
    api.create_commit(repo_id=repo_id, operations=operations, repo_type="dataset",
                      commit_message="CaptchaOCR dataset: card, inventory, license",
                      num_threads=NUM_THREADS)
