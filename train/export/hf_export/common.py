import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TRAIN_DIR = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TRAIN_DIR)

DEFAULT_OUT_DIRS = [os.path.join(REPO, "dataset", "out"),
                    os.path.join(REPO, "dataset", "out_ru")]

ENTRY_SCRIPT = os.path.join(TRAIN_DIR, "export_hf.py")

LATIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
CYRILLIC_CHARSET = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"

AUTO_MAP = {
    "AutoConfig": "configuration_captcha.CaptchaConfig",
    "AutoModel": "modeling_captcha.CaptchaModel",
    "AutoProcessor": "processing_captcha.CaptchaProcessor",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def read_labels(directory: str) -> list[dict]:
    rows = []
    with open(os.path.join(directory, "labels.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def find_types(roots: list[str]) -> list[tuple[str, str, str]]:
    found = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            if "labels.jsonl" not in files:
                continue
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            found.append((rel, dirpath, root))
    return sorted(found)


def newest_checkpoint(*dirs: str) -> str | None:
    best = None
    for d in dirs:
        for sub in (d, os.path.join(d, "ckpt")):
            if not os.path.isdir(sub):
                continue
            for name in os.listdir(sub):
                if not (name.startswith("step_") and name.endswith(".pt")):
                    continue
                path = os.path.join(sub, name)
                if best is None or os.path.getmtime(path) > os.path.getmtime(best):
                    best = path
    return best
