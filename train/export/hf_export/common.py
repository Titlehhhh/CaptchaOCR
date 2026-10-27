"""The paths, the constants and the small helpers of the CRNN export.

Split out of `train/export_hf.py` so that every module of the package agrees on
where the repository is, where the training code is and what the characters are.
"""

import json
import os

#: `train/export/hf_export` - this package.
HERE = os.path.dirname(os.path.abspath(__file__))
#: `train` - the training code (`captcha_crnn.py`) and the entry script.
#: The package now lives one level deeper (`train/export/hf_export`), so the
#: training directory is two levels up.
TRAIN_DIR = os.path.dirname(os.path.dirname(HERE))
#: the repository root.
REPO = os.path.dirname(TRAIN_DIR)

#: The dataset trees the verification images are picked from.
DEFAULT_OUT_DIRS = [os.path.join(REPO, "dataset", "out"),
                    os.path.join(REPO, "dataset", "out_ru")]

#: The entry script of the export. The fresh-process check re-executes *this*
#: file, not a module of this package, so that the child is started exactly the
#: way a user starts the export.
ENTRY_SCRIPT = os.path.join(TRAIN_DIR, "export_hf.py")

LATIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
CYRILLIC_CHARSET = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"

AUTO_MAP = {
    "AutoConfig": "configuration_captcha.CaptchaConfig",
    "AutoModel": "modeling_captcha.CaptchaModel",
    "AutoProcessor": "processing_captcha.CaptchaProcessor",
}


def log(msg: str) -> None:
    """Print a line of the export's own progress log."""
    print(msg, flush=True)


def read_labels(directory: str) -> list[dict]:
    """Read a `labels.jsonl` file."""
    rows = []
    with open(os.path.join(directory, "labels.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def find_types(roots: list[str]) -> list[tuple[str, str, str]]:
    """Every dataset type under the roots, as `(type_id, directory, root)`."""
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
    """The newest `ckpt/step_*.pt` under any of the directories."""
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
