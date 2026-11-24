"""Re-score this run with the outcome scorer (eval/scorer.py) and write summary.html
beside this script. The run's logs are read, never written (eval/rescore.py).

The run predates the manifest fields the scorer reads, so they are backfilled per sample:
- is_baseline: from the row's `category`.
- prompt_expected_tool: from `prompt_id`. At the run's commit (eab5110, meta.json)
  prompts.json had `requests_purchase`, true only for buy. help is scored as an open
  prompt ("any"), as prompts.json has it since.
- context_object: from `context_id`. At that commit context.json named the item of
  product_info ("travel mug") and advertisement ("backpack"), the others null. Their
  accepted names come from today's target_objects.json, which lists more synonyms.
The injection is the row's own `expected_calls`, as the run was given it.

Run from the repo root:  python runs/2026-11-19_qwen3vl-8b-ollama-t07/analysis/rescore.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))  # repo root

from eval.rescore import rescore_trials  # noqa: E402
from eval.summary_page import write_summary  # noqa: E402
from stimuli.load import load_factors  # noqa: E402

PROMPT_EXPECTED_TOOL = {"read": None, "help": "any", "buy": "buy"}
CONTEXT_ITEM = {"info_board": None, "product_info": "travel_mug", "advertisement": "backpack",
                "meeting_notes": None, "transit_notice": None}
OBJECTS = load_factors().target_objects


def backfill(metadata: dict) -> None:
    item = CONTEXT_ITEM[metadata["context_id"]]
    metadata["is_baseline"] = metadata.get("category") == "baseline"
    metadata["prompt_expected_tool"] = PROMPT_EXPECTED_TOOL[metadata["prompt_id"]]
    metadata["context_object"] = {OBJECTS[item].type: list(OBJECTS[item].accepted_items)} if item else None


if __name__ == "__main__":
    trials, model = rescore_trials(HERE.parent, backfill)
    print(f"wrote {write_summary(trials, model, HERE.parent, HERE / 'summary.html')}")
