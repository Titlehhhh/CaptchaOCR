"""Restore the reference images into dataset/out_ru after a regeneration.

`dev.captcha.Gen` writes into the same tree, so a clean rebuild of a plugin folder
wipes the reference images. This script puts back the two sets that belong to the
repository and are ours to redistribute:

  research/jars/bf_dataset/  ->  dataset/out_ru/BotFilter/real_shots/
      510 real upstream BotFilter renders (MIT community dataset); the file name is
      the answer.

  research/refout/  ->  dataset/out_ru/CaptchaVerifyZ/real_shots/
      5 reference renders of the open-source CaptchaVerifyZ algorithm.

Nothing else is restored: the gallery-style families under `dataset/out_ru/GalleryCaptcha/`
have no reference material in the repository any more, and none is invented.

When a source folder is not available the script warns and does nothing for that set -
it never raises, so it is safe to call from a build step.

It also re-creates the `README.md` that explains what each `real_shots/` folder holds
(an existing one is never overwritten, so a hand-written note survives).

Usage:
    python tools/restore_real_shots.py [--dry-run] [--quiet]
"""

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import REPO

OUT_RU = os.path.join(REPO, "dataset", "out_ru")

# The two reference sets: (source folder relative to the repo root, destination folder
# relative to dataset/out_ru, a short name for the messages).
SETS = [
    (os.path.join("research", "jars", "bf_dataset"),
     os.path.join("BotFilter", "real_shots"),
     "BotFilter"),
    (os.path.join("research", "refout"),
     os.path.join("CaptchaVerifyZ", "real_shots"),
     "CaptchaVerifyZ"),
]

# the note that explains what each real_shots/ folder holds; written only when it is
# missing, so a hand-written one is never overwritten
READMES = {
    os.path.join("BotFilter", "real_shots", "README.md"): """# BotFilter - 510 real upstream renders

These are **not** generated samples. They are 510 captcha PNGs that the BotFilter plugin
actually produced, recovered from the community dataset

> <https://github.com/ServerSideProject/botfilter_captcha_dataset> - MIT, 2022

* The original archive is kept in `research/jars/botfilter_captcha_dataset.rar`; the
  extracted originals live in `research/jars/bf_dataset/`.
* Every file is a 128x128 PNG and **the file name is the answer** (`1024.png` -> `1024`).
  The answers are 4 or 5 digits, exactly as upstream's `randomAnswer()` produces.
* They are the **pre-quantisation** painter output, i.e. anti-aliased blends. The generated
  samples in `dataset/out_ru/BotFilter/map/` are quantised to the Minecraft map palette,
  which is what the player finally sees.
""",
    os.path.join("CaptchaVerifyZ", "real_shots", "README.md"): """# CaptchaVerifyZ - 5 reference renders

These are **not** generated samples. They are re-renders of the upstream renderer
algorithm, produced by `research/RefRender.java` (a hand transcription of the CFR decompile
of `CaptchaVerifyZ-1.4.jar`, itself checked against the raw bytecode):

```
ref-00000.png   ref-A7K2X.png   ref-M3P9L.png   ref-QWERT.png   ref-ZZZZZ.png
```

They are the ground truth for the pixel-identity check in `research/DiffCaptchaVerifyZ.java`:
the project's own generator renders the same five codes and the result is **0 differing
pixels out of 16384** with an equal MD5, for all five.

The originals are in `research/refout/`.
""",
}


def write_readmes(dry_run=False):
    """Re-create the real_shots/ notes that a clean rebuild would have wiped."""
    n = 0
    for rel, text in READMES.items():
        path = os.path.join(OUT_RU, rel)
        if os.path.exists(path):
            continue
        if not dry_run:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        n += 1
    return n


def copy_tree(src_dir, dst_dir, dry_run=False):
    """Copy every PNG of `src_dir` into `dst_dir`; returns the number of files copied."""
    n = 0
    for fn in sorted(os.listdir(src_dir)):
        if not fn.lower().endswith(".png"):
            continue
        if not dry_run:
            shutil.copy2(os.path.join(src_dir, fn), os.path.join(dst_dir, fn))
        n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Restore the BotFilter and CaptchaVerifyZ reference images "
                    "into dataset/out_ru after a regeneration.")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be copied, change nothing")
    ap.add_argument("--quiet", action="store_true", help="print nothing on success")
    args = ap.parse_args(argv)

    total = 0
    missing = 0

    for rel_src, rel_dst, name in SETS:
        src = os.path.join(REPO, rel_src)
        dst = os.path.join(OUT_RU, rel_dst)
        if not os.path.isdir(src):
            print(f"  [warn] source not available, {name}/real_shots left untouched: "
                  f"{rel_src}")
            missing += 1
            continue
        if not args.dry_run:
            os.makedirs(dst, exist_ok=True)
        n = copy_tree(src, dst, dry_run=args.dry_run)
        total += n
        if not args.quiet:
            verb = "would restore" if args.dry_run else "restored"
            print(f"  {verb} {n} reference image(s) -> dataset/out_ru/{rel_dst}")

    notes = write_readmes(dry_run=args.dry_run)
    if notes and not args.quiet:
        verb = "would write" if args.dry_run else "wrote"
        print(f"  {verb} {notes} real_shots README file(s)")

    if missing == len(SETS) and not args.quiet:
        print("  [warn] no reference source is available - nothing was restored")

    if not args.quiet:
        print(f"{'would restore' if args.dry_run else 'restored'} {total} reference "
              f"image(s) into {OUT_RU}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
