"""The uploader of the CaptchaOCR dataset to the Hugging Face Hub.

``tools/upload_dataset.py`` used to be one 998-line file: the plan, the digests, the
card, the upload and the verification.  They are this package now:

* ``card``    - the dataset card template and the numbers that fill it
* ``plan``    - what has to be uploaded: the digests, the batches, the stale files
* ``transfer``- the commits: the upload, the prune, the retries
* ``verify``  - the comparison of the remote tree with the local one
* ``cli``     - the command line

The command line did not move: ``python tools/upload_dataset.py --dry-run`` is the same
script as before, it only imports the package.
"""

import os
import sys

#: the repo root: tools/hf_upload/__init__.py -> tools/hf_upload -> tools -> <repo>
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# The publishing helpers live in the ``tools.publish_hf`` package.  The old script
# did ``import publish_hf as ph`` with ``tools/`` on sys.path, which resolved to the
# *package* ``tools/publish_hf/`` - and that package only re-exports ``main``, so
# ``ph.require_token`` did not exist and the script died with an AttributeError.
# The names are imported from the modules that define them instead.
from tools.publish_hf.auth import api_for, require_token, whoami_name  # noqa: E402,F401
from tools.publish_hf.cards import (agpl_note, dataset_card_values,  # noqa: E402,F401
                                    licence_summary_block, no_licence_note,
                                    render_dataset_license, render_template)
from tools.publish_hf.dataset import (build_inventory, collect_type,  # noqa: E402,F401
                                      find_type_dirs)
from tools.publish_hf.upload import ensure_repo  # noqa: E402,F401
from tools.publish_hf.utils import human_bytes, log, warn  # noqa: E402,F401

#: The repository this package publishes into; also the default of ``--repo-id``.
DEFAULT_REPO_ID = "Titlehhhh/captchaocr-dataset"
