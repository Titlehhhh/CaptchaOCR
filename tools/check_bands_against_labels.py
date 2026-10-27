"""Does every roi() band carry the answer, and nothing else?

    python tools/check_bands_against_labels.py dataset/out dataset/out_ru

This is the ``ink`` mode of ``tools/check_bands.py`` (kept as its own entry point
because the documentation points at this name).

The `roi` field of a sample is the bounding box of the text band that carries the
answer - the line of a chat log, the name in a window title, the code on a map. A
recogniser is trained on that crop, so a band that points at the wrong text is worse
than no band at all: the label cannot be fitted, the loss does not come down, and the
type silently scores 0.000. That is not a hypothetical - it is what a band that
pointed at the plugin's own prefix instead of the answer did to one training run.

So this checks the pixels, not the metadata. For every sample with a band it crops
the band and looks at the colours in it:

  * the ink colour of the answer has to be in the crop - the answer is written in a
    colour of its own (red in a chat line, yellow in a map, aqua in a dialog), so a
    crop without it holds something else;
  * the ink colours of the text that must NOT be in the band have to be absent - the
    instruction line, the window title, the caption.

The rules are per type, in the RULES table of ``check_bands.py``. A type that is not
in the table is reported with its colour census (``--verbose``), so the table can be
extended.

The other two checks live next to this one: ``tools/check_labels_and_roi.py`` re-derives
the labels and checks that the band is inside the canvas, and
``tools/check_band_vs_answer.py`` compares the `text` and `answer` fields (they differ
on purpose for the number-word and the arithmetic families).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_bands import build_parser, mode_ink  # noqa: E402


def main(argv=None):
    """The old wrapper: dataset roots, ``--verbose`` optional, exit 1 on a failure."""
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
