#!/usr/bin/env python
"""Where the web app finds things.

The repository root is resolved from this file's own location, so every
script of the app can be started from any working directory.  The module is
deliberately tiny: it holds the paths and nothing else.

(The name is `filepaths` and not `paths` on purpose: the repository root has
its own `paths.py`, shared by `bench/` and `tools/`, and the web app must not
shadow it.)

    from filepaths import HERE, ROOT, STATIC, DATA_ROOTS
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))       # .../webapp
ROOT = os.path.dirname(HERE)                             # the repository root
TRAIN = os.path.join(ROOT, "train")
STATIC = os.path.join(HERE, "static")

# The dataset is read-only for this app; only these two trees may be read.
DATA_ROOTS = [os.path.join(ROOT, "dataset", "out"),
              os.path.join(ROOT, "dataset", "out_ru")]

# The machine's Hugging Face cache lives inside the repository and holds the
# PP-OCRv6 weights; it must be pointed at BEFORE huggingface_hub is imported
# (the same trick `train/finetune_ppocr.py` uses).  The app never needs the
# network: the hub is asked for local files only.
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".hf-cache"))
os.environ.setdefault("HF_HUB_CACHE", os.path.join(ROOT, ".hf-cache", "hub"))
