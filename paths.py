"""Repo-relative path resolution shared by the benchmark and tool scripts.

The harnesses live in ``bench/`` and the helpers in ``tools/``; both read the
dataset from ``dataset/out`` and write their JSON into ``reports/``. Resolving
the repo root from ``__file__`` keeps every script runnable from any working
directory:

    python bench/bench_hf.py
    python tools/fix_b64.py
"""

import os

# repo root: this file sits next to README.md, AGENTS.md and build.ps1
REPO = os.path.dirname(os.path.abspath(__file__))

DATASET = os.path.join(REPO, "dataset")
GENERATOR = os.path.join(DATASET, "generator")
OUT = os.path.join(DATASET, "out")
OUT_RU = os.path.join(DATASET, "out_ru")
REPORTS = os.path.join(REPO, "reports")
TOOLS = os.path.join(REPO, "tools")
# The GalleryCaptcha reference gallery was removed from this repository on
# 2026-10-22 - it held third-party screenshots. Its path constant is gone with
# it; nothing in bench/, train/ or tools/ imports it any more.


def results(name):
    """Absolute path of a result JSON inside reports/."""
    return os.path.join(REPORTS, name)


def dataset_type(*parts):
    """Absolute path of one captcha type folder inside dataset/out."""
    return os.path.join(OUT, *parts)
