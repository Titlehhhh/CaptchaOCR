import json
import os
import tempfile
from pathlib import Path

from .auth import api_for, require_token, whoami_name
from .constants import EXIT_NO_CONFIRM, INVENTORY_NAME
from .dataset import TypeDir
from .utils import human_bytes, log, warn


def remote_file_sizes(api, repo_id: str, repo_type: str) -> dict[str, int]:
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


def upload_dataset(args, inventory: dict, card: str, types: list[TypeDir],
                   license_text: str = "") -> int:
    token = require_token(args.token)
    api = api_for(token)
    user = whoami_name(api)
    ensure_repo(api, args.repo_id, "dataset", token, args.private,
                args.confirm_create, user)

    remote = remote_file_sizes(api, args.repo_id, "dataset")
    log(f"В репозитории уже есть {len(remote)} файлов.")

    inventory_bytes = json.dumps(inventory, ensure_ascii=False, indent=2).encode("utf-8")
    card_bytes = card.encode("utf-8")
    license_bytes = license_text.encode("utf-8")

    plan: list[tuple[str, Path | None, bytes | None, int]] = []
    for t in types:
        for png in t.pngs:
            path_in_repo = f"{t.repo_dir()}/{png.name}"
            plan.append((path_in_repo, png, None, png.stat().st_size))
        plan.append((f"{t.repo_dir()}/labels.jsonl", t.labels_path, None,
                     t.labels_path.stat().st_size))
    plan.append(("README.md", None, card_bytes, len(card_bytes)))
    if license_bytes:
        plan.append(("LICENSE", None, license_bytes, len(license_bytes)))
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