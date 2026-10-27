import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from export.hf_export.cli import main  # noqa: E402  (the package lives under train/export/)

if __name__ == "__main__":
    sys.exit(main())
