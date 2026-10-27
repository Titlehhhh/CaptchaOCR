"""Build the measured training reports from the artefacts of the runs.

    .venv-gpu\\Scripts\\python.exe train\\make_report.py --help

One entry point for the three reports that the run directories used to build with
their own copies of the script:

| kind | the report | what it reads |
|---|---|---|
| `ppocr-log` | `reports/TRAINING_PPOCR_V6.json` | the log of the first PP-OCRv6 run |
| `ppocr-result` | `reports/TRAINING_PPOCR_V6_BIG.json` | the `result.json` of the big run |
| `crnn` | `reports/TRAINING_CRNN_BIG.json` | the `val_report.json` of the CRNN run |

Every number in the reports is read out of a file that a run wrote; nothing is typed
in by hand. The reports themselves are **measured results**: they are written by the
command below and are never edited by hand.

The three builders live in `train/report_builders/`. They used to sit as copies
inside the run directories (`train/runs/**`), which are git-ignored - so the code
that produced a measured report was invisible to git and had to be looked for on
disk.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from report_builders import crnn as crnn_builder          # noqa: E402
from report_builders import markdown as markdown_tables    # noqa: E402
from report_builders import ppocr_log, ppocr_result        # noqa: E402


def rooted(p):
    """A path that is relative to the repository root."""
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("written:", path)


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("kind", choices=("ppocr-log", "ppocr-result", "crnn"),
                   help="which report to build")
    p.add_argument("--run-dir", default=None,
                   help="the run's directory (the default depends on the report)")
    p.add_argument("--out", default=None,
                   help="where to write the report JSON (the default depends on the report)")
    p.add_argument("--stdout-log", default=None,
                   help="the stdout log of the run (ppocr-log only)")
    p.add_argument("--log", default=None,
                   help="the run's log.txt (ppocr-log only)")
    p.add_argument("--baseline", default=None,
                   help="the archived per-type baseline JSON (ppocr-log only)")
    p.add_argument("--prev", default=None,
                   help="the previous run's report JSON (ppocr-result only)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.kind == "ppocr-log":
        run_dir = rooted(args.run_dir or os.path.join("train", "runs", "ppocrv6"))
        stdout_log = rooted(args.stdout_log or os.path.join(run_dir, "final_stdout.log"))
        log_path = rooted(args.log or os.path.join(run_dir, "log.txt"))
        baseline = rooted(args.baseline or os.path.join(run_dir, "baseline_per_type.json"))
        out_path = rooted(args.out or os.path.join("reports", "TRAINING_PPOCR_V6.json"))
        report, summary = ppocr_log.build(run_dir, stdout_log, log_path, baseline)
        write_json(out_path, report)
        print("zero step held-out:", report["zero_step"]["aggregate"])
        print("after training held-out:", report["after_training"]["aggregate"])
        print("better:", summary["better"], "worse:", summary["worse"],
              "unchanged:", summary["same"])
        print("epochs:", summary["epochs"], "steps:", summary["steps"])
        return 0

    if args.kind == "ppocr-result":
        run_dir = rooted(args.run_dir or os.path.join("train", "runs", "ppocrv6", "big"))
        prev_path = rooted(args.prev or os.path.join("reports", "TRAINING_PPOCR_V6.json"))
        out_path = rooted(args.out or os.path.join("reports", "TRAINING_PPOCR_V6_BIG.json"))
        report, soup = ppocr_result.build(run_dir, prev_path)
        write_json(out_path, report)
        print("verdict:", report["verdict"]["helped_or_hurt"],
              "| median", report["verdict"]["zero_step_median_exact_pct"], "% ->",
              report["verdict"]["finetuned_median_exact_pct"], "%")
        markdown_tables.print_tables(report, soup)
        return 0

    # crnn
    run_dir = rooted(args.run_dir or os.path.join("train", "runs", "crnn", "crnn_big"))
    out_path = rooted(args.out or os.path.join("reports", "TRAINING_CRNN_BIG.json"))
    report = crnn_builder.build(run_dir)
    write_json(out_path, report)
    print(json.dumps({"held_out": report["held_out"],
                      "training_types": report["training_types"],
                      "memorisation_gap": report["memorisation_gap"]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
