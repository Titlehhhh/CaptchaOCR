
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - экзотические потоки
        pass

HERE = Path(__file__).resolve().parent.parent
REPO_ROOT = HERE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NO_AUTH = 2
EXIT_NO_CONFIRM = 3

DATA_PREFIX = "data"

INVENTORY_NAME = "dataset_inventory.json"

DATASET_CARD_TEMPLATE = HERE / "hf_dataset_card.md"
DATASET_LICENSE_TEMPLATE = HERE / "hf_dataset_license.md"
MODEL_CARD_TEMPLATE = HERE / "hf_model_card.md"
MODEL_CARD_TEMPLATE_CRNN = HERE / "hf_model_card_crn.md"
MODEL_CARD_TEMPLATES = {
    "ppocrv6": MODEL_CARD_TEMPLATE,
    "crnn": MODEL_CARD_TEMPLATE_CRNN,
}
TRAINING_REPORT_JSON = REPO_ROOT / "reports" / "TRAINING_PPOCR_V6.json"
BENCH_JSON = REPO_ROOT / "reports" / "bench_models" / "ppocrv6-medium.json"
