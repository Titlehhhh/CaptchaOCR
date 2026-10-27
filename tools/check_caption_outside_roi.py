"""Check that the caption's ink is never inside the text band of a composite.

    python tools/check_caption_outside_roi.py dataset/out_ru/GalleryCaptcha/ru-numberword-caption

This is the ``caption`` mode of ``tools/check_bands.py`` (kept as its own entry point
because the documentation points at this name).

The caption is a *different* string from the answer, so a recogniser that is handed the
text band must never see it. The band of a composite is the band of the map, cut off at
the first row the caption's ink is on - this checks that the cut really works, by
looking for the caption's own fill colour inside the band.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_bands import build_parser, mode_caption  # noqa: E402


def main(argv=None):
    """The old wrapper: exactly one type directory, exit 1 on a failure."""
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
