"""
Several runs' trials analysed as one dataset, for runs that each cover part of today's
manifest (a later run filling in the rows an earlier one lacks).

Each run's trials are its re-scored ones when its analysis/rescore.py defines
`rescored_trials()` (as runs/2026-11-24_qwen3vl-8b-ollama's does), else those of its logs
(eval/trials.py). The runs must share a model and must not share a trial (id and epoch):
a trial in two runs has no single result. Each trial keeps the name of its run as `run`.
The combined trials are written to <out>/analysis/ as eval/analyze.py writes a run's.

Usage:
    python -m eval.combine runs/<out> runs/<a> runs/<b> [...]
"""

from __future__ import annotations

import argparse
import runpy
import sys
from collections import Counter
from pathlib import Path

from eval.analyze import write_analysis
from eval.trials import load_trials, manifest_order


def run_trials(run_dir: Path) -> tuple[list[dict], str | None]:
    """A run's trials: re-scored by its analysis/rescore.py when that defines
    `rescored_trials()`, else read from its logs."""
    script = run_dir / "analysis" / "rescore.py"
    if script.exists():
        rescored = runpy.run_path(str(script)).get("rescored_trials")
        if rescored is None:
            sys.exit(f"Error: {script} defines no rescored_trials(), and the run's logs hold its run-time scores")
        return rescored(run_dir)
    return load_trials(run_dir)


def combine(runs: dict[str, tuple[list[dict], str | None]]) -> tuple[list[dict], str | None]:
    """One trial list from {run name: (trials, model)}."""
    models = {model for _, model in runs.values()}
    if len(models) > 1:
        sys.exit(f"Error: the runs have different models: {sorted(map(str, models))}")
    owners = Counter((t["id"], t["epoch"]) for trials, _ in runs.values() for t in trials)
    if shared := sorted(k for k, n in owners.items() if n > 1):
        sys.exit(f"Error: {len(shared)} trial(s) are in more than one run, e.g. {shared[0]}")
    trials = [{**t, "run": name} for name, (ts, _) in runs.items() for t in ts]
    return trials, models.pop() if models else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path, help="directory for the combined analysis/, e.g. runs/<date>_combined")
    ap.add_argument("run_dirs", type=Path, nargs="+", help="harness run directories")
    ap.add_argument("--manifest", type=Path, default=Path("stimuli/manifest.jsonl"),
                    help="manifest for representation order")
    args = ap.parse_args()
    trials, model = combine({d.name: run_trials(d) for d in args.run_dirs})
    for name, n in Counter(t["run"] for t in trials).items():
        print(f"{name}: {n} trials")
    write_analysis(trials, model, args.out, manifest_order(args.manifest))
