"""Is the string inside the text band the same as the `answer` field?

    python tools/check_band_vs_answer.py dataset/out_ru

This is the ``summary`` mode of ``tools/check_bands.py`` (kept as its own entry point
because the documentation points at this name).  The `text` field of a sample is the
literal string that is drawn in the picture, and the `answer` field is what the player
has to type.  For most types they are the same.  For the number-word family they are
not, on purpose: the map shows the number in Russian words and the player answers with
the digits.  A recogniser has to be trained on the `text`, and a lexicon turns the
words into the digits - so a mismatch is not a bug, but it does have to be *known*,
because a trainer that compares the prediction with the `answer` of such a type will
score zero.

The types with no band at all are reported as well: the band is where the recogniser
looks, and a type without one cannot be a recogniser's training target.

The other two band checks live in the same script: ``--mode ink`` (the colour rule)
and ``--mode caption`` (the caption's ink).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_bands import build_parser, mode_summary  # noqa: E402


def main(argv=None):
    """The old wrapper: one dataset root, the summary table, exit 0."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        build_parser("check_band_vs_answer.py").print_help()
        return 0 if argv else 2
    return mode_summary(argv)


if __name__ == "__main__":
    sys.exit(main())
