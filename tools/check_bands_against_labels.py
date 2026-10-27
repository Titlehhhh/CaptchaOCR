""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_bands import build_parser, mode_ink  # noqa: E402


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    verbose = "--verbose" in argv
    roots = [a for a in argv if not a.startswith("--")]
    if not roots:
        print(__doc__)
        return 2
    return mode_ink(roots, verbose)


if __name__ == "__main__":
    sys.exit(main())
