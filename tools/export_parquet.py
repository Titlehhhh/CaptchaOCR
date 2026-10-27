"""Export the generated CaptchaOCR PNG dataset to Parquet shards and publish them.

The dataset tree lives in ``dataset/out`` (12 types) and ``dataset/out_ru``
(8 types); every type directory holds ``NNN.png`` files plus one
``labels.jsonl`` row per image.  This script turns that loose-PNG layout into a
small number of Parquet shards -- one row per sample, with the raw PNG bytes in
the ``image`` column -- so the Hugging Face repository can be loaded with
``datasets.load_dataset`` or with plain ``pyarrow``.

Modes::

    python tools/export_parquet.py --dry-run        # print the plan, write nothing
    python tools/export_parquet.py --out build/parquet
    python tools/export_parquet.py --out build/parquet --upload
    python tools/export_parquet.py --out build/parquet --verify

``--upload`` uploads ``<out>/data/*.parquet`` under ``data/`` and
``<out>/README.md`` to the repository root, then deletes every remaining file
under ``data/out/`` and ``data/out_ru/`` (the old loose PNG tree) in chunks of
1000 paths per commit.  It never deletes ``README.md``,
``dataset_inventory.json``, ``LICENSE*``, ``.gitattributes`` or anything
outside those two prefixes.

Only ``pyarrow`` is required to build the shards -- not ``datasets``.

The implementation is the ``tools/parquet_export/`` package (index, shards, card,
hub, cli); this file is the entry point, the command line did not change.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.parquet_export.cli import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())
