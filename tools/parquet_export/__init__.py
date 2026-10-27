"""The Parquet export of the CaptchaOCR dataset.

``tools/export_parquet.py`` used to be one 941-line file: the index over the dataset,
the shard planning, the Parquet writer, the README of the shards and the upload to the
Hub.  They are this package now:

* ``index``   - what is in the dataset: the label rows and the PNG files
* ``shards``  - the plan of the shards and the Parquet writer
* ``card``    - the README of the shards and the table of the types
* ``hub``     - the upload to the Hugging Face Hub and the verification
* ``cli``     - the command line

The command line did not move: ``python tools/export_parquet.py --dry-run`` is the same
script as before, it only imports the package.
"""

import os
import sys

#: the repo root: tools/parquet_export/__init__.py -> tools/parquet_export -> tools -> <repo>
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
