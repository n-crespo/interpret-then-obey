"""Re-score a run's logs in memory with today's scorer (eval/scorer.py), for runs whose
manifest rows lack a field the scorer reads or record a value it now reads differently.

The logs are read, never written. `backfill(metadata)` edits each sample's manifest row
before scoring; a run's own analysis/rescore.py says what it changes and why.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from eval.scorer import outcome
from eval.trials import _stop_reason, _trial, merge_logs


def rescore_trials(run_dir: Path, backfill: Callable[[dict], None]) -> tuple[list[dict], str | None]:
    """Like eval.trials.load_trials, but with each sample re-scored after `backfill`."""
    from inspect_ai import score
    from inspect_ai.analysis import SampleColumn, SampleScores, SampleSummary, samples_df
    from inspect_ai.log import read_eval_log

    columns = SampleSummary + SampleScores + [SampleColumn("stop_reason", path=_stop_reason, full=True)]
    per_log, model = [], None
    for path in sorted((run_dir / "inspect_logs").glob("*.eval")):
        log = read_eval_log(str(path))
        for sample in log.samples or []:
            backfill(sample.metadata)
        scored = score(log, outcome(), action="overwrite", display="none")
        df = samples_df(scored, columns=columns, quiet=True)
        per_log.append([_trial(rec, path.name) for rec in df.to_dict("records")])
        model = log.eval.model
    return merge_logs(per_log), model
