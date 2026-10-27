
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.publish_hf.auth import api_for, require_token, whoami_name  # noqa: E402,F401
from tools.publish_hf.cards import (agpl_note, dataset_card_values,  # noqa: E402,F401
                                    licence_summary_block, no_licence_note,
                                    render_dataset_license, render_template)
from tools.publish_hf.dataset import (build_inventory, collect_type,  # noqa: E402,F401
                                      find_type_dirs)
from tools.publish_hf.upload import ensure_repo  # noqa: E402,F401
from tools.publish_hf.utils import human_bytes, log, warn  # noqa: E402,F401

DEFAULT_REPO_ID = "Titlehhhh/captchaocr-dataset"
