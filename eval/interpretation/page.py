"""
Interpretation page: runs/<dir>/analysis/interpretation.html, written by `report_run` in
report.py from the same counts as interpretation.tex.

Shows the share of probe replies that name the injection's object per representation,
with Wilson 95% intervals, grouped by category; then the control rows and the baseline
false-positive rate. Click a row for its probe trials with the full reply and the
keyword check's verdict (score.py), to eyeball the check.
"""

from __future__ import annotations

from pathlib import Path

from eval.interpretation.report import interpretation_rows, probe_split
from eval.interpretation.score import action_words, items, names_action, names_object
from eval.summary_page import _js_json
from eval.trials import group_by, wilson

TEMPLATE = Path(__file__).with_name("template.html")


def _rate(n: int, k: int, a: int | None = None) -> dict:
    lo, hi = wilson(k, n)
    return {"n": n, "k": k, "a": a, "lo": lo, "hi": hi}


def _trials(ts: list[dict], accepted: list[str] | None = None) -> list[dict]:
    """One record per trial: id, epoch, context, verdicts and the full reply. Baseline
    trials (`accepted` given) are checked against every injected object of the run."""
    return [{
        "id": t["id"], "e": t["epoch"], "c": t.get("context_id"),
        "obj": names_object(t, accepted), "act": accepted is None and names_action(t),
        "w": items(t) if accepted is None else None, "aw": action_words(t), "r": t.get("response") or "",
    } for t in sorted(ts, key=lambda t: (t["id"], t["epoch"]))]


def page_data(trials: list[dict], model: str | None, run: str, rep_order: list | None = None) -> dict:
    rows = interpretation_rows(trials, rep_order)
    injected, control, baseline, every_item = probe_split(trials)
    by_rep = group_by(injected + control, "representation_id")
    n, fp = rows["baseline"]
    return {
        "model": model or "", "run": run, "baseline_items": every_item,
        "representation": [{"rep": rep, "cat": cat, **_rate(n, k, a)} for rep, cat, n, k, a in rows["representation"]],
        "category": [{"cat": cat, **_rate(n, k, a)} for cat, n, k, a in rows["category"]],
        "control": [{"rep": rep, "cat": cat, **_rate(n, k, a)} for rep, cat, n, k, a in rows["control"]],
        "baseline": _rate(n, fp),
        "trials": {**{rep: _trials(ts) for rep, ts in by_rep.items()}, "": _trials(baseline, every_item)},
    }


def write_page(trials: list[dict], model: str | None, run: str, out: Path, rep_order: list | None = None) -> Path:
    """Write the page for one run's probe trials."""
    out.parent.mkdir(parents=True, exist_ok=True)
    data = _js_json(page_data(trials, model, run, rep_order))
    out.write_text(TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", data), encoding="utf-8")
    return out
