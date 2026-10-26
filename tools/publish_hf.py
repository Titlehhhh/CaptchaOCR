import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.publish_hf.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
