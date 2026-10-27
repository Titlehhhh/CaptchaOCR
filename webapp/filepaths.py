#!/usr/bin/env python
import os

HERE = os.path.dirname(os.path.abspath(__file__))       # .../webapp
ROOT = os.path.dirname(HERE)                             # the repository root
TRAIN = os.path.join(ROOT, "train")
STATIC = os.path.join(HERE, "static")

DATA_ROOTS = [os.path.join(ROOT, "dataset", "out"),
              os.path.join(ROOT, "dataset", "out_ru")]

os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".hf-cache"))
os.environ.setdefault("HF_HUB_CACHE", os.path.join(ROOT, ".hf-cache", "hub"))
