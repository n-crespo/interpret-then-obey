"""Re-score a run's logs in memory with today's scorer (eval/scorer.py), for runs whose
manifest rows lack a field the scorer reads or record a value it now reads differently.

The logs are read, never written. `backfill(metadata)` edits each sample's manifest row
before scoring, and the optional `edit(sample)` the rest of the sample (its messages, say);
a run's own analysis/rescore.py says what it changes and why.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from eval.scorer import outcome
from eval.trials import _stop_reason, _trial, merge_logs
from stimuli.build import context_object

if TYPE_CHECKING:
    from inspect_ai.log import EvalSample

    from stimuli.schema import Factors

# Contexts of past runs that stimuli/factors/contexts.json no longer has under their id:
# renamed, or removed with their context_object as stimuli/build.py made it.
RENAMED_CONTEXTS = {"info_board": "library_board"}
REMOVED_CONTEXT_OBJECTS = {
    "meeting_notes": {"subject": ["MEETING NOTES", "team sync", "meeting", "roadmap", "hiring"]},
    "transit_notice": {"subject": ["TRANSIT NOTICE", "Platform 2", "Line 4"]},
}


def past_context_object(context_id: str, factors: Factors) -> dict:
    """context_object for a context id a past run used, including renamed and removed ones."""
    if context_id in REMOVED_CONTEXT_OBJECTS:
        return REMOVED_CONTEXT_OBJECTS[context_id]
    return context_object(factors.contexts[RENAMED_CONTEXTS.get(context_id, context_id)], factors)


def rescore_trials(
    run_dir: Path, backfill: Callable[[dict], None], edit: Callable[[EvalSample], None] | None = None
) -> tuple[list[dict], str | None]:
    """Like eval.trials.load_trials, but with each sample re-scored after `backfill` and `edit`."""
    from inspect_ai import score
    from inspect_ai.analysis import SampleColumn, SampleScores, SampleSummary, samples_df
    from inspect_ai.log import read_eval_log

    columns = SampleSummary + SampleScores + [SampleColumn("stop_reason", path=_stop_reason, full=True)]
    per_log, model = [], None
    for path in sorted((run_dir / "inspect_logs").glob("*.eval")):
        log = read_eval_log(str(path))
        for sample in log.samples or []:
            backfill(sample.metadata)
            if edit is not None:
                edit(sample)
        scored = score(log, outcome(), action="overwrite", display="none")
        df = samples_df(scored, columns=columns, quiet=True)
        per_log.append([_trial(rec, path.name) for rec in df.to_dict("records")])
        model = log.eval.model
    return merge_logs(per_log), model
