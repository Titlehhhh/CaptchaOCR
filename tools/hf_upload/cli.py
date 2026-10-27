
import argparse
import json
import sys
from pathlib import Path

from tools.publish_hf.auth import api_for, resolve_token, whoami_name
from tools.publish_hf.cards import render_dataset_license
from tools.publish_hf.dataset import build_inventory
from tools.publish_hf.upload import ensure_repo
from tools.publish_hf.utils import human_bytes, log, warn

from .card import build_card
from . import DEFAULT_REPO_ID
from .plan import (DATA_PREFIX, DEFAULT_BATCH_FILES, INVENTORY_NAME, build_plan,
                   chunk_count, collect, count_real_shots, find_types,
                   local_target_paths, remote_digests, remote_files,
                   stale_remote_files, stale_type_ids, type_id_of_dir)
from .transfer import (DEFAULT_NUM_THREADS, MAX_NUM_THREADS, MIN_NUM_THREADS,
                        clamp_num_threads, create_commit_with_retries, current_num_threads,
                        prune_remote, set_num_threads, upload_batch, upload_metadata)
from .verify import EXIT_ERROR, EXIT_OK, verify

EXIT_NO_AUTH = 2

REGENERATION_DATE = "2026-10-22"

GITATTRIBUTES_FALLBACK = (
    "*.png filter=lfs diff=lfs merge=lfs -text\n"
    "*.jsonl text eol=lf\n"
    "*.json text eol=lf\n"
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

TOKEN_FILE = REPO_ROOT / ".hf-cache" / "token"


def require_token(explicit: str | None) -> str:
    token = resolve_token(explicit)
    if token:
        return token
    try:
        value = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        value = ""
    if value:
        return value
    from tools.publish_hf.auth import AUTH_INSTRUCTIONS
    from tools.publish_hf.constants import EXIT_NO_AUTH
    log(AUTH_INSTRUCTIONS)
    log("Токен не найден: ни HF_TOKEN, ни сохранённый токен CLI, ни .hf-cache/token. "
        "Выход с кодом 2.")
    raise SystemExit(EXIT_NO_AUTH)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Опубликовать датасет CaptchaOCR на HF Hub (существующий репозиторий).")
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID,
                        help="репозиторий назначения (dataset)")
    parser.add_argument("--data-dir", default=str(REPO_ROOT / "dataset"),
                        help="корень дерева датасета (по умолчанию <repo>/dataset)")
    parser.add_argument("--dry-run", action="store_true",
                        help="напечатать план и выйти, ничего не грузя")
    parser.add_argument("--verify", action="store_true",
                        help="проверить удалённое дерево и выйти")
    parser.add_argument("--prune", action="store_true",
                        help="после заливки удалить из data/ файлы, которых больше нет "
                             "в локальном дереве (устар. типы и лишние PNG)")
    parser.add_argument("--batch-files", type=int, default=DEFAULT_BATCH_FILES,
                        metavar="N",
                        help=f"файлов в одном коммите и в одном куске prune-а "
                             f"(по умолчанию {DEFAULT_BATCH_FILES})")
    parser.add_argument("--num-threads", type=int, default=DEFAULT_NUM_THREADS,
                        metavar="N",
                        help=f"потоков на один коммит (num_threads у create_commit; "
                             f"это же размер пула загрузки LFS). Допустимо "
                             f"{MIN_NUM_THREADS}..{MAX_NUM_THREADS}, по умолчанию "
                             f"{DEFAULT_NUM_THREADS} (у хаба 5)")
    parser.add_argument("--token", default=None, help="HF-токен (иначе из окружения/кэша)")
    parser.add_argument("--private", action="store_true",
                        help="создать репозиторий приватным (по умолчанию — публичный)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_dir = Path(args.data_dir).resolve()
    if args.batch_files < 1:
        warn(f"--batch-files {args.batch_files} < 1, использую 1")
        args.batch_files = 1
    set_num_threads(clamp_num_threads(args.num_threads))

    token = require_token(args.token)
    api = api_for(token)
    user = whoami_name(api)
    log(f"token owner:     {user or '(unknown)'}")
    log(f"repo:            {args.repo_id} (dataset)")
    log(f"data dir:        {data_dir}")

    types = find_types(data_dir)
    collect(types)
    inventory = build_inventory(types, data_dir)
    real_shots, real_shots_files = count_real_shots(data_dir)

    log(f"types found:     {len(types)}")
    log(f"png found:       {sum(t.inventory['png_files'] for t in types)}")
    log(f"labels found:    {len(types)}")
    log(f"real_shots (not published): {real_shots} PNG in {real_shots_files} files")

    for t in types:
        assert "real_shots" not in t.type_id.split("/"), t.type_id

    if args.verify:
        return verify(api, args.repo_id, types)

    mismatched = [(t.type_id, t.inventory["png_files"], t.inventory["samples"])
                  for t in types
                  if t.inventory["png_files"] != t.inventory["samples"]]
    for type_id, pngs, rows in mismatched:
        warn(f"тип {type_id}: {pngs} PNG против {rows} строк в labels.jsonl")

    if not args.dry_run:
        ensure_repo(api, args.repo_id, "dataset", token, args.private, False, user)

    log("")
    log("=== Дайджесты удалённых файлов ===")
    digests = remote_digests(api, args.repo_id)
    log(f"remote files:    {len(digests)}")
    plan, unchanged = build_plan(types, digests)

    local_paths = local_target_paths(types)
    labels_to_add = sum(1 for _, items in plan.batches for path, _ in items
                        if path.endswith("labels.jsonl"))
    png_to_add = plan.total_files() - labels_to_add
    chunks = plan.chunk_count(args.batch_files)

    stale: dict[str, int] = {}
    stale_dirs: list[str] = []
    stale_bytes = 0
    if args.prune:
        stale = stale_remote_files(remote_files(api, args.repo_id), local_paths)
        stale_dirs = stale_type_ids(stale, types)
        stale_bytes = sum(stale.values())

    log("")
    log("=== План загрузки ===")
    log(f"types:                 {len(types)}")
    log(f"local target paths:    {len(local_paths)}")
    log(f"unchanged (skipped):   {len(unchanged)}")
    log(f"labels to add:         {labels_to_add}")
    log(f"PNG to add:            {png_to_add}")
    log(f"files to upload:       {plan.total_files()}")
    log(f"bytes to upload:       {plan.total_bytes()} ({human_bytes(plan.total_bytes())})")
    log(f"batches:               {len(plan.batches)}")
    log(f"chunks (--batch-files {args.batch_files}): {chunks}")
    log(f"threads per commit: {current_num_threads()}")
    for name, items in plan.batches[:6]:
        log(f"  - {name}: {len(items)} files")
    if len(plan.batches) > 6:
        log(f"  ... and {len(plan.batches) - 6} more batches")

    if args.prune:
        log("")
        log("=== Prune ===")
        log(f"stale remote paths:    {len(stale)}")
        log(f"stale bytes:           {stale_bytes} ({human_bytes(stale_bytes)})")
        log(f"stale type ids:        {len(stale_dirs)}")
        log(f"prune chunks (--batch-files {args.batch_files}): "
            f"{chunk_count(len(stale), args.batch_files)}")
        for directory in stale_dirs[:50]:
            log(f"  - {type_id_of_dir(directory)}")
        if len(stale_dirs) > 50:
            log(f"  ... and {len(stale_dirs) - 50} more type ids")

    if args.dry_run:
        log("")
        log("DRY RUN: nothing was uploaded, nothing was deleted.")
        return EXIT_OK

    labels_bytes = sum(t.labels_path.stat().st_size for t in types)
    card = build_card(inventory, args.repo_id, real_shots, real_shots_files, labels_bytes)
    license_text, leftovers = render_dataset_license(inventory, args.repo_id)
    if leftovers:
        warn("в LICENSE остались плейсхолдеры: " + ", ".join(leftovers))
    inventory_bytes = json.dumps(inventory, ensure_ascii=False, indent=2).encode("utf-8")
    metadata = {
        "README.md": card.encode("utf-8"),
        INVENTORY_NAME: inventory_bytes,
        "LICENSE": license_text.encode("utf-8"),
    }
    if ".gitattributes" not in digests:
        metadata[".gitattributes"] = GITATTRIBUTES_FALLBACK.encode("utf-8")
    log("")
    log("=== Метаданные ===")
    for name, data in metadata.items():
        log(f"  {name}: {len(data)} bytes")
    upload_metadata(api, args.repo_id, metadata)
    log("  uploaded.")

    log("")
    log("=== Данные ===")
    uploaded = 0
    for index, (name, items) in enumerate(plan.batches, start=1):
        uploaded += upload_batch(api, args.repo_id, name, items, args.batch_files)
        log(f"  [{index}/{len(plan.batches)}] {name}: {len(items)} files "
            f"(всего {uploaded}/{plan.total_files()})")

    log("")
    log(f"uploaded {uploaded} files in {chunks} data commits")

    if args.prune:
        log("")
        log("=== Prune ===")
        log(f"stale remote paths:    {len(stale)}")
        log(f"stale bytes:           {stale_bytes} ({human_bytes(stale_bytes)})")
        log(f"stale type ids:        {len(stale_dirs)}")
        for directory in stale_dirs[:50]:
            log(f"  - {type_id_of_dir(directory)}")
        if len(stale_dirs) > 50:
            log(f"  ... and {len(stale_dirs) - 50} more type ids")
        deleted, deleted_bytes = prune_remote(api, args.repo_id, stale, args.batch_files)
        log(f"  deleted {deleted} files ({human_bytes(deleted_bytes)}) "
            f"in {chunk_count(len(stale), args.batch_files)} commits")

    log("")
    log("=== Проверка ===")
    return verify(api, args.repo_id, types)


def run() -> int:
    try:
        return main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        warn(f"{type(exc).__name__}: {exc}")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(run())
