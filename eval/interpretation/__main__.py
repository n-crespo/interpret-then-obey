"""python -m eval.interpretation runs/<dir> [...]: the interpretation report alone, read from
each run's Inspect logs (eval/trials.py). `just analyze` prints and writes it too."""

from __future__ import annotations

import argparse
from pathlib import Path

from eval.interpretation.report import report_run
from eval.trials import load_trials, manifest_order

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dirs", type=Path, nargs="+", help="harness run directories with inspect_logs/")
    ap.add_argument("--manifest", type=Path, default=Path("stimuli/manifest.jsonl"),
                    help="manifest for representation order")
    args = ap.parse_args()
    for run_dir in args.run_dirs:
        trials, model = load_trials(run_dir)
        print(f"{run_dir}  ({model})")
        written = report_run(trials, model, run_dir / "analysis", manifest_order(args.manifest))
        print(f"\nWrote {written.relative_to(run_dir)}" if written else "  no probe-prompt trials")
