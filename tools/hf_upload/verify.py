
from tools.publish_hf.utils import human_bytes, log

from .plan import DATA_PREFIX, INVENTORY_NAME, is_remote_folder, is_stale_path, local_target_paths

EXIT_OK = 0
EXIT_ERROR = 1


def verify(api, repo_id: str, types: list) -> int:
    try:
        entries = list(api.list_repo_tree(repo_id=repo_id, repo_type="dataset",
                                          recursive=True))
    except Exception as exc:  # noqa: BLE001
        log("MISMATCH")
        log(f"  - не удалось прочитать удалённое дерево: {type(exc).__name__}: {exc}")
        return EXIT_ERROR

    remote_png = 0
    remote_labels = 0
    remote_bytes = 0
    remote_paths: set[str] = set()
    for entry in entries:
        path = getattr(entry, "path", None)
        if path is None:
            continue
        if is_remote_folder(entry):
            continue
        remote_paths.add(path)
        size = getattr(entry, "size", 0) or 0
        if path.endswith(".png"):
            remote_png += 1
            remote_bytes += size
        elif path.endswith("labels.jsonl"):
            remote_labels += 1
            remote_bytes += size

    local_png = sum(t.inventory["png_files"] for t in types)
    local_labels = len(types)
    local_bytes = sum(t.inventory["bytes"] for t in types) + sum(
        t.labels_path.stat().st_size for t in types)
    local_paths = local_target_paths(types)
    stale_count = sum(1 for path in remote_paths if is_stale_path(path, local_paths))

    try:
        info = api.repo_info(repo_id=repo_id, repo_type="dataset")
        sha = getattr(info, "sha", "?")
    except Exception:  # noqa: BLE001
        sha = "?"

    log(f"repo:            {repo_id}")
    log(f"last commit:     {sha}")
    log(f"remote PNG:      {remote_png}")
    log(f"remote labels:   {remote_labels}")
    log(f"remote bytes:    {remote_bytes} ({human_bytes(remote_bytes)})")
    log(f"local PNG:       {local_png}")
    log(f"local labels:    {local_labels}")
    log(f"local bytes:     {local_bytes} ({human_bytes(local_bytes)})")
    log(f"stale remote paths: {stale_count}")

    log("")
    log("last commits:")
    try:
        commits = list(api.list_repo_commits(repo_id=repo_id, repo_type="dataset"))
        for commit in commits[:3]:
            message = (getattr(commit, "title", "") or "").splitlines()[0]
            log(f"  {getattr(commit, 'commit_id', '?')}  {message}")
    except Exception as exc:  # noqa: BLE001
        log(f"  (не удалось прочитать историю: {type(exc).__name__}: {exc})")

    problems: list[str] = []
    if remote_png != local_png:
        problems.append(f"PNG: remote {remote_png} != local {local_png}")
    if remote_labels != local_labels:
        problems.append(f"labels.jsonl: remote {remote_labels} != local {local_labels}")
    for extra in ("README.md", INVENTORY_NAME, ".gitattributes"):
        if extra not in remote_paths:
            problems.append(f"missing {extra}")
    for t in types:
        if f"{DATA_PREFIX}/{t.type_id}/labels.jsonl" not in remote_paths:
            problems.append(f"missing {DATA_PREFIX}/{t.type_id}/labels.jsonl")
        missing = [png.name for png in t.pngs
                   if f"{DATA_PREFIX}/{t.type_id}/{png.name}" not in remote_paths]
        if missing:
            problems.append(f"{t.type_id}: {len(missing)} PNG missing "
                            f"(e.g. {missing[:3]})")

    if problems:
        log("MISMATCH")
        for problem in problems[:50]:
            log(f"  - {problem}")
        if len(problems) > 50:
            log(f"  ... and {len(problems) - 50} more")
        return EXIT_ERROR
    log("OK")
    return EXIT_OK
