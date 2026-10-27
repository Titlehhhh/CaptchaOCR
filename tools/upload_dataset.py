import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.hf_upload.cli import main  # noqa: E402

EXIT_ERROR = 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"ВНИМАНИЕ: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)
