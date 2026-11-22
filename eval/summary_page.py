"""
Summary page: every trial of one run counted by outcome and by label, written by
`analyze_run` in eval/analyze.py (runs/<dir>/analysis/summary.html).

Outcomes and labels are the scorer's (eval/scorer.py, eval/classify.py). A trial has one
outcome and one label per tool call, so it counts once per outcome and once under each
of its labels. Click an outcome or a label for its breakdown by factor and every trial in it.
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.classify import LABELS, OUTCOMES, label_outcome
from eval.trials import call_label

TEMPLATE = Path(__file__).with_name("summary_template.html")
RESPONSE_CHARS = 280


def _js_json(obj) -> str:
    """JSON safe to inline in a <script> block (model replies can contain '</script>')."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")


def summary_rows(trials: list[dict]) -> list[dict]:
    """One record per trial: id, epoch, factors for the breakdowns, outcome, labels, tool
    call text and the start of the reply."""
    return [{
        "id": t["id"], "e": t["epoch"], "p": t.get("prompt_id"), "c": t.get("context_id"),
        "cat": t.get("category"), "rep": t.get("representation_id"), "base": bool(t.get("is_baseline")),
        "o": t["outcome"], "l": t["labels"], "d": call_label(t["tool_calls"]),
        "r": (t.get("response") or "")[:RESPONSE_CHARS],
    } for t in sorted(trials, key=lambda t: (t["id"], t["epoch"]))]


def write_summary(trials: list[dict], model: str | None, run_dir: Path, out: Path) -> Path:
    """Write the page for one run's trials."""
    data = {
        "model": model or "", "run": run_dir.name, "outcomes": list(OUTCOMES),
        "labels": {label: label_outcome(label) for label in LABELS}, "rows": summary_rows(trials),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", _js_json(data)), encoding="utf-8")
    return out
