"""
Trials of one harness run, with the outcome the scorer gave each, and counts over them.

Loads the Inspect logs in runs/<dir>/inspect_logs/*.eval through
`inspect_ai.analysis.samples_df` into one dict per trial (sample x epoch). The outcome,
labels and sources are the `outcome` score (eval/scorer.py), not re-derived here. An
errored sample has no score; its outcome is `harness_error`, the outcome the classifier
gives any errored response.

Attack success is counted on injected rows only: baseline rows (`is_baseline`) show no
injection, and errored trials are left out of every rate. Control rows (a category in
CONTROL_CATEGORIES) are scored like injected rows but reported apart from them: they show
the injection's object with no command, so their attack success is priming by the
object, not obeying.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from eval.classify import OUTCOMES

FACTORS = ["prompt_id", "context_id", "injection_id", "representation_id", "category", "language", "script",
           "is_baseline", "prompt_expected_tool"]
CONTROL_CATEGORIES = ("mention",)  # stimuli/schema.py's Category
LEVEL_ORDER = ["natural", "obfuscated", "keyed", "constructed", "symbols", "latin", "non_latin", "read", "say", "summarize", "help", "buy", "directions", "remind"]  # help, directions, remind: old runs


# ----------------------------------------------------------------------------
# Loading


def _clean(v):
    """pandas NA/NaN -> None."""
    try:
        import pandas as pd

        if v is None or (not isinstance(v, (list, dict)) and pd.isna(v)):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _json(v, default):
    v = _clean(v)
    if v is None:
        return default
    return json.loads(v) if isinstance(v, str) else v


def _stop_reason(sample):
    out = sample.output
    return out.stop_reason if out and out.choices else None


def merge_logs(trials_per_log: list[list[dict]]) -> list[dict]:
    """A resumed run (`harness.run --resume`) has several logs, oldest first. A later
    result replaces an earlier one for the same (id, epoch) unless that would replace a
    clean result with an error."""
    merged: dict = {}
    for trials in trials_per_log:
        for t in trials:
            key = (t["id"], t["epoch"])
            if key in merged and t["error"] and not merged[key]["error"]:
                continue
            merged[key] = t
    return list(merged.values())


def _trial(rec: dict, where: str) -> dict:
    """samples_df record -> trial dict."""
    error = _clean(rec.get("error")) or None
    value = _clean(rec.get("score_outcome"))
    if value is None and not error:
        sys.exit(f"Error: {where} has samples without an `outcome` score (eval/scorer.py). Logs written "
                 "before the scorer cannot be analysed; rerun the harness.")
    sm: dict = _json(rec.get("score_outcome_metadata"), {})
    return {
        "id": rec["id"],
        "epoch": int(rec["epoch"]),
        **{f: _clean(rec.get(f"metadata_{f}")) for f in FACTORS},
        "outcome": value or "harness_error",
        "labels": sm.get("classification") or (["harness_error"] if error else []),
        "tool_calls": sm.get("tool_calls") or [],
        "expected_calls": _json(rec.get("metadata_expected_calls"), []),
        "stop_reason": _clean(rec.get("stop_reason")),
        "error": error,
        "response": _clean(rec.get("score_outcome_answer")) or "",
    }


def load_trials(run_dir: Path) -> tuple[list[dict], str | None]:
    """One dict per (sample, epoch) from run_dir/inspect_logs/*.eval, plus the model name."""
    from inspect_ai.analysis import SampleColumn, SampleScores, SampleSummary, samples_df
    from inspect_ai.log import read_eval_log

    log_dir = run_dir / "inspect_logs"
    # Oldest first: filenames start with a timestamp (the order harness/run.py uses too)
    logs = sorted(log_dir.glob("*.eval"))
    if not logs:
        sys.exit(f"Error: no .eval logs in {log_dir}. Run the harness first: just run <config.yaml>")

    columns = SampleSummary + SampleScores + [SampleColumn("stop_reason", path=_stop_reason, full=True)]
    per_log = [[_trial(rec, lp.name) for rec in samples_df(str(lp), columns=columns, quiet=True).to_dict("records")]
               for lp in logs]
    model = read_eval_log(str(logs[-1]), header_only=True).eval.model
    return merge_logs(per_log), model


# ----------------------------------------------------------------------------
# Counting


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def summarize(trials: list[dict]) -> dict:
    """Trials per outcome, plus n."""
    c = Counter(t["outcome"] for t in trials)
    return {"n": len(trials), **{o: c[o] for o in OUTCOMES}}


def group_by(trials: list[dict], *fields: str) -> dict:
    """Trials keyed by one field value, or by a tuple of values for several fields."""
    groups: dict = defaultdict(list)
    for t in trials:
        groups[tuple(t.get(f) for f in fields) if len(fields) > 1 else t.get(fields[0])].append(t)
    return dict(groups)


def split(trials: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """(injected, control, baseline, errored); errored trials are left out of every rate."""
    ok = [t for t in trials if t["outcome"] != "harness_error"]
    control = [t for t in ok if t.get("category") in CONTROL_CATEGORIES]
    baseline = [t for t in ok if t.get("is_baseline")]
    injected = [t for t in ok if not t.get("is_baseline") and t.get("category") not in CONTROL_CATEGORIES]
    return injected, control, baseline, [t for t in trials if t["outcome"] == "harness_error"]


def _order(keys, preferred: list | None = None):
    rank = {k: i for i, k in enumerate(preferred or [])}
    return sorted(keys, key=lambda k: (rank.get(k, len(rank)), str(k)))


def call_label(calls: list[dict]) -> str:
    """name(args) for each call, or "no call"."""
    if not calls:
        return "no call"
    return ", ".join(f"{c['name']}({', '.join(str(v) for v in (c.get('args') or {}).values())})" for c in calls)


def manifest_order(path: Path) -> list:
    """representation_id order as it appears in the manifest (english first, none last)."""
    order: list = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rep = json.loads(line).get("representation_id")
                if rep not in order:
                    order.append(rep)
    except OSError:
        pass
    return sorted(order, key=lambda r: r == "none")  # stable: keeps manifest order, baseline last
