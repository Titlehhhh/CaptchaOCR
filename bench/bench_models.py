"""T1 harness: run READY-MADE captcha/OCR models on OUR dataset under ONE protocol.

This is a *new* harness (the brief allows `bench/bench_models.py`). It does not
touch `bench/bench_hf.py`, `bench/bench_others.py` or `bench/bench_onnx.py`.

Protocol (identical for every model):

  * **Item sets** - built from `dataset/out` + `dataset/out_ru`, `labels.jsonl`:
      - ``full``       : all 46 types x N samples (N default 20) = 920 items
      - ``legacy104``  : the 13 types x 8 samples of the old bench (104 items)
      - ``legacy64``   : the 8 band-carrying types x 8 samples of the old bench
                         (64 items) - the set the published 0.156 / 0.125 / 0.047
                         baselines were re-scored on
  * **Input modes** - ``band`` (the `roi` crop from labels.jsonl; the whole frame
    for the 17 types that have no band) and ``frame`` (the whole PNG). The two
    are never mixed: they are separate result blocks.
  * **Metrics** - exact match and CER, per type, then
      - micro (over items),
      - macro-median (median over the per-type values - the brief asks for the
        median, not the mean),
      - separately for the 29 types that carry a band and the 17 that do not.
  * **Ground truth** - the *drawn* string (`text`) is primary, because that is
    what an OCR model can possibly read; the *answer* (the solved captcha) is
    reported as a second column. The two differ in 8 of the 46 types.

Everything that is measured is written to `reports/bench_models/<model>.json`
(model, weights revision, preprocessing, library versions, per-type metrics,
every prediction). The old `reports/bench_results*.json` are never touched.

Usage:
    .venv-gpu\\Scripts\\python.exe bench\\bench_models.py --models grafj-crnn,ppocrv5
    python bench\\bench_models.py --models easyocr          # system python (CPU)
    .venv-gpu\\Scripts\\python.exe bench\\bench_models.py --contact-sheet <slug>

The implementation is the `bench/harness/` package (items, metrics, backends,
registry, runner, cli); this file is the entry point and the command line.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
