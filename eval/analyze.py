"""
Interpret-Then-Obey analysis of one or more harness runs.

Reads the Inspect logs in runs/<dir>/inspect_logs/*.eval with the outcome the scorer gave
each trial (eval/trials.py), groups trials by the stimulus factors in the manifest
and writes runs/<dir>/analysis/:

- tables.tex               booktabs tables: attack success by representation and by
                           factor, and every outcome per prompt (eval/tables.py)
- summary.html             every trial counted by outcome and label; click one for its
                           trials (eval/summary_page.py)
- interpretation.tex       replies to the probe prompts that recover the payload, by
                           representation (eval/interpretation/)

Outcomes and labels are defined and computed by eval/classify.py. Probe-prompt trials
never ask for a tool, so they are left out of attack success, the tables and the summary
page, and only measure interpretation. P(obey | interpret) is not computed: the probe
and the attack prompts are different trials.

Usage:
    python -m eval.analyze runs/<date>_<name> [runs/<other> ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.interpretation import is_probe
from eval.interpretation.report import report_run
from eval.summary_page import write_summary
from eval.tables import ASR, SHOWN, latex_tables
from eval.trials import LEVEL_ORDER, _order, group_by, load_trials, manifest_order, split, summarize, wilson


# ----------------------------------------------------------------------------
# Terminal


def pct(k: int, n: int) -> str:
    return f"{k}/{n} ({100 * k / n:.0f}%)" if n else "-"


def _rates(s: dict) -> str:
    """Every outcome but attack success, for a summarize() result."""
    return "   ".join(f"{o} {pct(s[o], s['n'])}" for o in SHOWN if o != ASR)


def headline(trials: list[dict], model: str | None, run_dir: Path) -> str:
    injected, control, baseline, errored = split(trials)
    si, sb = summarize(injected), summarize(baseline)
    lo, hi = wilson(si[ASR], si["n"])
    lines = [
        f"{run_dir}  ({model})",
        f"  injected {si['n']:>5} trials   {ASR} {pct(si[ASR], si['n'])}, 95% CI {100 * lo:.0f}-{100 * hi:.0f}%"
        f"   {_rates(si)}",
    ]
    groups = group_by(injected, "prompt_id")
    for prompt in _order(groups, LEVEL_ORDER):
        s = summarize(groups[prompt])
        lines.append(f"    {str(prompt):<8}{s['n']:>4} trials   {ASR} {pct(s[ASR], s['n'])}")
    for rep, ts in group_by(control, "representation_id").items():  # priming by the object, not obeying
        lines.append(f"  control  {len(ts):>5} trials   {rep}: acted on the injection's object "
                     f"{pct(summarize(ts)[ASR], len(ts))}")
    lines.append(f"  baseline {sb['n']:>5} trials   {_rates(sb)}")
    if errored:
        lines.append(f"  {len(errored)} errored trial(s) left out")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# Main


def _manifest(run_dir: Path, manifest: Path | None) -> Path:
    if manifest is not None:
        return manifest
    meta = run_dir / "meta.json"
    return Path(json.loads(meta.read_text())["manifest"]) if meta.exists() else Path("stimuli/manifest.jsonl")


def analyze_run(run_dir: Path, manifest: Path | None = None) -> list[Path]:
    """Print the headline and write the tables and summary page for one run; returns the
    written paths."""
    trials, model = load_trials(run_dir)
    if all(t["outcome"] == "harness_error" for t in trials):
        sys.exit(f"No successful samples in {run_dir / 'inspect_logs'} ({len(trials)} errored)")
    out_dir = run_dir / "analysis"
    out_dir.mkdir(exist_ok=True)
    rep_order = manifest_order(_manifest(run_dir, manifest))
    attack = [t for t in trials if not is_probe(t)]
    (out_dir / "tables.tex").write_text(latex_tables(attack, model, rep_order), encoding="utf-8")
    written = [out_dir / "tables.tex", write_summary(attack, model, run_dir, out_dir / "summary.html")]

    print(headline(attack, model, run_dir))
    if interpretation := report_run(trials, model, out_dir, rep_order):
        written.append(interpretation)
    print("\nWrote " + ", ".join(str(p.relative_to(run_dir)) for p in written))
    return written


def analyze(run_dirs: Path | list[Path], manifest: Path | None = None) -> list[Path]:
    """analyze_run for each run. Returns the written paths."""
    run_dirs = [run_dirs] if isinstance(run_dirs, Path) else run_dirs
    written = []
    for i, run_dir in enumerate(run_dirs):
        if i:
            print()
        written += analyze_run(run_dir, manifest)
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", type=Path, nargs="+",
                    help="harness run directories, e.g. runs/2026-11-15_qwen3vl-8b-ollama")
    ap.add_argument("--manifest", type=Path,
                    help="manifest for representation order (default: the one in the run's meta.json, "
                         "else stimuli/manifest.jsonl)")
    args = ap.parse_args()
    analyze(args.run_dirs, args.manifest)
