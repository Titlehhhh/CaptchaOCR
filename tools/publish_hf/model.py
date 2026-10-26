import json
import os
import shutil
import tempfile
from fnmatch import fnmatch
from pathlib import Path

from .auth import api_for, require_token, whoami_name
from .constants import REPO_ROOT
from .upload import ensure_repo, remote_file_sizes
from .utils import human_bytes, log, warn

# =====================================================================================
# Модель
# =====================================================================================

#: Файлы чекпоинта, которые копируются в репозиторий модели как есть.
#: Список явный: результаты замера (`val_report.json`) в репозиторий модели не попадают.
MODEL_EXTRA_PATTERNS = ("*.py", "onnx/*", "vocab.json", "processor_config.json",
                        "tokenizer_config.json", "special_tokens_map.json",
                        "added_tokens.json", "generation_config.json",
                        "LICENSE", "LICENSE.txt", "LICENSE.md")



def load_checkpoint_state(path: Path) -> tuple[dict, dict]:
    """Прочитать чекпоинт: вернуть (state_dict, прочие поля верхнего уровня)."""
    import torch

    obj = torch.load(path, map_location="cpu", weights_only=False)
    extra: dict = {}
    state = None
    if isinstance(obj, dict):
        for key in ("model", "state_dict", "model_state_dict", "weights", "net"):
            if key in obj and isinstance(obj[key], dict):
                state = obj[key]
                break
        if state is None:
            # возможно, это и есть state_dict: все значения — тензоры
            if obj and all(hasattr(v, "shape") for v in obj.values()):
                state = obj
            else:
                state = obj.get("model", {})
        extra = {k: v for k, v in obj.items() if k not in
                 ("model", "state_dict", "model_state_dict", "weights", "net", "optim",
                  "sched", "optimizer", "rng", "cuda_rng", "aug_rng")}
    elif hasattr(obj, "state_dict"):
        state = obj.state_dict()
    if not state:
        raise SystemExit(f"Не удалось найти state_dict в чекпоинте {path}")
    return state, extra


def derive_geometry(state: dict) -> dict:
    """Вывести параметры архитектуры из форм тензоров (это измерение, не догадка)."""
    out: dict = {}
    fc = state.get("fc.weight")
    if fc is not None and getattr(fc, "ndim", 0) == 2:
        out["num_classes"] = int(fc.shape[0])
        out["hidden"] = int(fc.shape[1]) // 2
    rnn = state.get("rnn.weight_ih_l0")
    if rnn is not None and getattr(rnn, "ndim", 0) == 2:
        out["rows"] = int(rnn.shape[1]) // 256
        out["glyph_height"] = out["rows"] * 8
    return out


def write_safetensors(state: dict, path: Path) -> None:
    """Сохранить state_dict в формате safetensors."""
    from safetensors.torch import save_file

    tensors = {k: v.detach().cpu().contiguous() for k, v in state.items()
               if hasattr(v, "detach")}
    save_file(tensors, str(path), metadata={"format": "pt"})


def preprocessor_config(height: int, width: int, mean: float, std: float,
                        charset: str, extra: dict) -> dict:
    """Описание препроцессора: размер входа, mean/std, charset."""
    cfg = {
        "image_processor_type": "CaptchaProcessor",
        "do_resize": True,
        "size": {"height": height, "width": width},
        "do_normalize": True,
        "image_mean": [mean],
        "image_std": [std],
        "resample": 2,
        "do_convert_rgb": False,
        "charset": charset,
    }
    cfg.update(extra)
    return cfg


def model_card_values(args, info: dict) -> dict[str, str]:
    """Значения для подстановки в шаблон карточки модели."""
    values = {
        "REPO_ID": args.repo_id,
        "CHECKPOINT": info.get("checkpoint", "не указан"),
        "N_CLASSES": info.get("num_classes", "не выведено"),
        "HIDDEN": info.get("hidden", "не выведено"),
        "GLYPH_HEIGHT": info.get("glyph_height", "не выведено"),
        "CHARSET": info.get("charset", "не указан"),
        "N_CHARS": str(len(info.get("charset", ""))) if info.get("charset") else "не указан",
        "IMAGE_HEIGHT": str(info.get("image_height", args.image_height)),
        "IMAGE_WIDTH": str(info.get("image_width", args.image_width)),
        "IMAGE_MEAN": str(info.get("image_mean", args.mean)),
        "IMAGE_STD": str(info.get("image_std", args.std)),
        "DATASET_REPO": args.dataset_repo or "не указан",
        "N_TRAIN_TYPES": info.get("n_train_types", "не указано"),
        "N_TRAIN_SAMPLES": info.get("n_train_samples", "не указано"),
        "RESULTS_BLOCK": info.get("results_block", "не указано"),
        "RESULTS_WARNING": info.get("results_warning", ""),
        "PENDING": "<!-- ЗАПОЛНИТЬ ВРУЧНУЮ -->",
    }
    # Значения, специфичные для выбранного шаблона (PP-OCRv6 и т. п.).
    values.update(info.get("card_values") or {})
    return values



def collect_model(args) -> tuple[dict, list[tuple[str, Path]], dict]:
    """Собрать файлы модели. Возвращает (info, список (путь в репозитории, локальный
    файл), временный каталог)."""
    ckpt = Path(args.checkpoint)
    if not ckpt.exists():
        raise SystemExit(f"Чекпоинт не найден: {ckpt}")

    staging = Path(tempfile.mkdtemp(prefix="hf_publish_", dir=str(REPO_ROOT)))
    info: dict = {"checkpoint": str(ckpt)}
    files: list[tuple[str, Path]] = []

    charset = ""
    if ckpt.is_file():
        ckpt_dir = ckpt.parent
        state, extra = load_checkpoint_state(ckpt)
        info.update(derive_geometry(state))
        info["state_keys"] = list(state.keys())[:40]
        charset = str(extra.get("charset") or "")
        info["step"] = extra.get("step")
        info["epoch"] = extra.get("epoch")
        weights = staging / "model.safetensors"
        write_safetensors(state, weights)
        files.append(("model.safetensors", weights))
    else:
        ckpt_dir = ckpt
        safes = sorted(ckpt.rglob("*.safetensors"))
        if safes:
            best = max(safes, key=lambda p: p.stat().st_mtime)
            files.append((best.name, best))
            info["weights_source"] = str(best.relative_to(ckpt))
            info["state_keys"] = []
        else:
            pts = sorted([p for p in ckpt.rglob("*")
                          if p.is_file() and p.suffix.lower() in (".pt", ".pth", ".ckpt")])
            if not pts:
                raise SystemExit(
                    f"В {ckpt} нет ни model.safetensors, ни *.pt — нечего публиковать.")
            best = max(pts, key=lambda p: p.stat().st_mtime)
            state, extra = load_checkpoint_state(best)
            info.update(derive_geometry(state))
            info["state_keys"] = list(state.keys())[:40]
            charset = str(extra.get("charset") or "")
            info["step"] = extra.get("step")
            info["epoch"] = extra.get("epoch")
            weights = staging / "model.safetensors"
            write_safetensors(state, weights)
            files.append(("model.safetensors", weights))
            info["weights_source"] = str(best.relative_to(ckpt))

    # config.json: из чекпоинта, иначе — синтезировать из форм тензоров.
    config_path = ckpt_dir / "config.json"
    if config_path.is_file():
        try:
            with open(config_path, encoding="utf-8") as handle:
                config = json.load(handle)
        except ValueError as exc:
            warn(f"config.json не читается ({exc}) — будет создан заново.")
            config = {}
        info["num_classes"] = config.get("num_classes", info.get("num_classes"))
        info["hidden"] = config.get("hidden", info.get("hidden"))
        info["glyph_height"] = config.get("glyph_height", info.get("glyph_height"))
        charset = config.get("charset") or charset
        info["model_type"] = config.get("model_type")
        info["config_source"] = "config.json из чекпоинта"
    else:
        keys = list(info.get("state_keys") or [])
        looks_ppocrv6 = ("backbone." in " ".join(keys)
                         or any(k.startswith("head.") for k in keys))
        if looks_ppocrv6:
            # У PP-OCRv6 config.json копируется из базового репозитория (так делает
            # train/run_ppocr/export_hf.py). Синтезировать «наш» config.json здесь
            # нельзя: архитектура была бы описана неверно.
            config = {}
            info["config_source"] = ("НЕ СОЗДАН: у чекпоинта нет config.json, а веса "
                                     "похожи на PP-OCRv6 — скопируйте config.json "
                                     "из базового репозитория "
                                     "(train/run_ppocr/export_hf.py)")
            warn("У чекпоинта нет config.json, а веса похожи на PP-OCRv6 — config.json "
                 "НЕ создан. Скопируйте его из базового репозитория перед публикацией.")
        else:
            config = {
                "architectures": ["CaptchaModel"],
                "model_type": "captha",
                "num_classes": info.get("num_classes"),
                "hidden": info.get("hidden"),
                "glyph_height": info.get("glyph_height"),
                "charset": charset,
                "blank_index": 0,
            }
            config = {k: v for k, v in config.items() if v is not None}
            info["config_source"] = ("синтезирован из state_dict "
                                      "(архитектура выведена из форм тензоров)")
            warn("В чекпоинте нет config.json — он собран из форм тензоров. "
                 "Проверьте его перед публикацией.")
    info["charset"] = charset
    config_bytes = json.dumps(config, ensure_ascii=False, indent=2).encode("utf-8") \
        if config else b""

    # preprocessor_config.json: из чекпоинта, иначе — по флагам.
    pre_path = ckpt_dir / "preprocessor_config.json"
    if pre_path.is_file():
        pre_bytes = pre_path.read_bytes()
        try:
            pre = json.loads(pre_bytes.decode("utf-8"))
        except ValueError:
            pre = {}
        size = pre.get("size") or {}
        info["image_height"] = size.get("height", args.image_height)
        info["image_width"] = size.get("width", args.image_width)
        mean = pre.get("image_mean") or [args.mean]
        std = pre.get("image_std") or [args.std]
        info["image_mean"] = mean[0] if isinstance(mean, list) and mean else args.mean
        info["image_std"] = std[0] if isinstance(std, list) and std else args.std
        info["preprocessor_source"] = "preprocessor_config.json из чекпоинта"
    else:
        pre = preprocessor_config(args.image_height, args.image_width, args.mean,
                                  args.std, charset, {})
        pre_bytes = json.dumps(pre, ensure_ascii=False, indent=2).encode("utf-8")
        info["image_height"] = args.image_height
        info["image_width"] = args.image_width
        info["image_mean"] = args.mean
        info["image_std"] = args.std
        info["preprocessor_source"] = "собран по флагам --image-height/--image-width/--mean/--std"

    # character_list.txt: из чекпоинта, иначе — из charset.
    char_path = ckpt_dir / "character_list.txt"
    if char_path.is_file():
        char_bytes = char_path.read_bytes()
        info["character_list_source"] = "character_list.txt из чекпоинта"
        if not charset:
            charset = char_path.read_text(encoding="utf-8").split()
    elif charset:
        char_bytes = ("\n".join(charset) + "\n").encode("utf-8")
        info["character_list_source"] = "собран из charset чекпоинта"
    else:
        char_bytes = b""
        info["character_list_source"] = "не найден (модель, возможно, его не использует)"

    # Прочие файлы экспорта (код модели, vocab.json, LICENSE, onnx/...).
    extra_files: list[tuple[str, Path]] = []
    if ckpt_dir.is_dir():
        for item in sorted(ckpt_dir.rglob("*")):
            if not item.is_file():
                continue
            if item.name in ("README.md", "labels.jsonl"):
                continue
            rel = item.relative_to(ckpt_dir).as_posix()
            if rel in ("model.safetensors", "config.json",
                       "preprocessor_config.json", "character_list.txt"):
                continue
            if not any(fnmatch(rel, pattern) for pattern in MODEL_EXTRA_PATTERNS):
                continue
            extra_files.append((rel, item))

    info["extra_files"] = [rel for rel, _ in extra_files]
    return {"info": info, "config_bytes": config_bytes, "pre_bytes": pre_bytes,
            "char_bytes": char_bytes}, files + extra_files, staging


def upload_model(args, meta: dict, files: list[tuple[str, Path]], card: str) -> int:
    """Залить модель в репозиторий."""
    token = require_token(args.token)
    api = api_for(token)
    user = whoami_name(api)
    ensure_repo(api, args.repo_id, "model", token, args.private,
                args.confirm_create, user)

    remote = remote_file_sizes(api, args.repo_id, "model")
    log(f"В репозитории уже есть {len(remote)} файлов.")

    from huggingface_hub import CommitOperationAdd

    operations = []
    plan: list[tuple[str, int]] = []
    for path_in_repo, local in files:
        size = local.stat().st_size
        if remote.get(path_in_repo) == size:
            log(f"  пропускаю {path_in_repo} (размер совпал)")
            continue
        operations.append(CommitOperationAdd(path_in_repo=path_in_repo,
                                             path_or_fileobj=str(local)))
        plan.append((path_in_repo, size))
    for path_in_repo, data in (("config.json", meta["config_bytes"]),
                               ("preprocessor_config.json", meta["pre_bytes"]),
                               ("README.md", card.encode("utf-8"))):
        if not data:
            continue
        if remote.get(path_in_repo) == len(data):
            log(f"  пропускаю {path_in_repo} (размер совпал)")
            continue
        operations.append(CommitOperationAdd(path_in_repo=path_in_repo,
                                             path_or_fileobj=data))
        plan.append((path_in_repo, len(data)))
    if meta["char_bytes"]:
        if remote.get("character_list.txt") != len(meta["char_bytes"]):
            operations.append(CommitOperationAdd(path_in_repo="character_list.txt",
                                                 path_or_fileobj=meta["char_bytes"]))
            plan.append(("character_list.txt", len(meta["char_bytes"])))

    if not operations:
        log("Все файлы уже загружены — нечего отправлять.")
        return 0

    total = sum(size for _, size in plan)
    log(f"К загрузке: {len(plan)} файлов, {human_bytes(total)}.")
    for path_in_repo, size in plan:
        log(f"  {path_in_repo} — {human_bytes(size)}")

    api.create_commit(repo_id=args.repo_id, operations=operations, repo_type="model",
                      commit_message="CaptchaOCR model export")
    return len(plan)


