from .auth import api_for, require_token
from .constants import EXIT_ERROR, EXIT_OK, INVENTORY_NAME
from .utils import human_bytes, log


def check_repo(args) -> int:
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
            continue
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