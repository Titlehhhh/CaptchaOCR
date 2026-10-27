"""The unified benchmark harness for ready-made captcha/OCR models.

``bench/bench_models.py`` used to be one 760-line file: the items, the metrics, the
six backends, the model registry and the runner.  They are this package now, one
module per job:

* ``items``     - the item sets (which types, which samples, band or frame)
* ``metrics``   - exact match and CER, per type and in aggregate
* ``backends``  - the six model backends (PP-OCR/ONNX, Graf-J, TrOCR, txtcaptcha,
  docTR/ONNX, EasyOCR)
* ``registry``  - the model keys and their repositories
* ``runner``    - the run loop and the contact sheet
* ``cli``       - the command line

The command line did not move: ``python bench/bench_models.py --help`` is the same
script as before, it only imports the package.
"""

import os
import sys

#: the repo root: bench/harness/__init__.py -> bench/harness -> bench -> <repo>
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

# The HF cache must live inside the workspace: the sandbox that runs the
# python processes cannot write to %USERPROFILE%\\.cache.
os.environ.setdefault("HF_HOME", os.path.join(REPO, "build", "hf_cache"))
