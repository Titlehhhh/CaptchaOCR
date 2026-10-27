import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_bands import build_parser, mode_caption  # noqa: E402


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        build_parser().print_help()
        return 0 if argv else 2
    if len(argv) != 1:
        print("give exactly one type directory", file=sys.stderr)
        return 2
    return mode_caption(argv[0])


if __name__ == "__main__":
    sys.exit(main())
