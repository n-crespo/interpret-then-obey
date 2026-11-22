"""Re-score this run with the outcome scorer (eval/scorer.py) and write summary.html
beside this script. The run's logs are read, never written: the scoring happens in memory.

The run predates the manifest fields the scorer reads, so they are backfilled per sample:
- is_baseline: from the row's `category`.
- prompt_expected_tool: from `prompt_id`. At the run's commit (eab5110, meta.json)
  prompts.json had `requests_purchase`, true only for buy.
- context_object: from `context_id`. At that commit context.json named the item of
  product_info ("travel mug") and advertisement ("backpack"), the others null. Their
  accepted names come from today's target_objects.json, which lists more synonyms.
The injection is the row's own `expected_calls`, as the run was given it.

Run from the repo root:  python runs/2026-11-19_qwen3vl-8b-ollama-t07/analysis/rescore.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_DIR = HERE.parent
sys.path.insert(0, str(HERE.parents[2]))  # repo root

from inspect_ai import score  # noqa: E402
from inspect_ai.analysis import SampleColumn, SampleScores, SampleSummary, samples_df  # noqa: E402
from inspect_ai.log import read_eval_log  # noqa: E402

from eval.outcomes import _stop_reason, _trial, merge_logs  # noqa: E402
from eval.scorer import outcome  # noqa: E402
from eval.summary_page import write_summary  # noqa: E402
from stimuli.factors import load_factors  # noqa: E402

PROMPT_EXPECTED_TOOL = {"read": None, "help": None, "buy": "buy"}
CONTEXT_ITEM = {"info_board": None, "product_info": "travel_mug", "advertisement": "backpack",
                "meeting_notes": None, "transit_notice": None}


def backfill(metadata: dict, objects) -> None:
    item = CONTEXT_ITEM[metadata["context_id"]]
    metadata["is_baseline"] = metadata.get("category") == "baseline"
    metadata["prompt_expected_tool"] = PROMPT_EXPECTED_TOOL[metadata["prompt_id"]]
    metadata["context_object"] = {objects[item].type: list(objects[item].accepted_items)} if item else None


def main() -> None:
    objects = load_factors().target_objects
    columns = SampleSummary + SampleScores + [SampleColumn("stop_reason", path=_stop_reason, full=True)]
    per_log, model = [], None
    for path in sorted((RUN_DIR / "inspect_logs").glob("*.eval")):
        log = read_eval_log(str(path))
        for sample in log.samples or []:
            backfill(sample.metadata, objects)
        scored = score(log, outcome(), action="overwrite", display="none")
        df = samples_df(scored, columns=columns, quiet=True)
        per_log.append([_trial(rec, path.name) for rec in df.to_dict("records")])
        model = log.eval.model
    page = write_summary(merge_logs(per_log), model, RUN_DIR, HERE / "summary.html")
    print(f"wrote {page}")


if __name__ == "__main__":
    main()
