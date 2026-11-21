"""
Summary page: every trial of one run counted by outcome, written by `analyze_run` in
eval/analyze_results.py (runs/<dir>/analysis/summary.html).

Prompts and contexts are abstracted away: each trial is counted under its `outcome`.
The outcomes' names, definitions, verdicts and colours come from `OUTCOMES` in
eval/outcomes.py. Click an outcome for a breakdown and every trial in it.
"""

from __future__ import annotations

from pathlib import Path

from eval.case_map_page import RESPONSE_CHARS, _js_json
from eval.outcomes import VERDICTS, call_label, outcomes_for_page
from eval.trials import Trial

TEMPLATE = Path(__file__).with_name("summary_template.html")


def summary_rows(trials: list[Trial]) -> list[dict]:
    """One record per trial: id, epoch, factors for the breakdowns, outcome, tool call
    text and the start of the reply."""
    return [{
        "id": t.id, "e": t.epoch, "at": t.case.attack_type, "cat": t.case.representation.category,
        "rep": t.case.representation.id, "base": t.case.is_baseline, "k": t.outcome,
        "d": call_label(t.response.calls), "r": t.response.text[:RESPONSE_CHARS],
    } for t in sorted(trials, key=lambda t: (t.id, t.epoch))]


def write_summary(trials: list[Trial], model: str | None, run_dir: Path, out: Path) -> Path:
    """Write the page for one run's trials."""
    data = {"model": model or "", "run": run_dir.name, "rows": summary_rows(trials),
            "outcomes": outcomes_for_page(), "verdicts": VERDICTS}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", _js_json(data)), encoding="utf-8")
    return out
