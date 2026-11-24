"""Re-score this run with the outcome scorer (eval/scorer.py) and write summary.html
beside this script. The run's logs are read, never written (eval/rescore.py).

The run predates the manifest fields the scorer reads, so they are backfilled per sample:
- is_baseline: from the row's `category`.
- prompt_expected_tool: from `prompt_id`. At the run's commit (eab5110, meta.json)
  prompts.json had `requests_purchase`, true only for buy. help is scored as an open
  prompt ("any"), as prompts.json has it since.
- context_object: from `context_id`, as stimuli/build.py makes it from today's
  contexts.json. Its headers and items match that commit's context.json; today's
  target_objects.json lists more synonyms for the items and contexts.json adds the words
  naming the subjects of scenes with no item.
The injection is the row's own `expected_calls`, as the run was given it.

Run from the repo root:  python runs/2026-11-19_qwen3vl-8b-ollama-t07/analysis/rescore.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))  # repo root

from eval.rescore import rescore_trials  # noqa: E402
from eval.summary_page import write_summary  # noqa: E402
from stimuli.build import context_object  # noqa: E402
from stimuli.load import load_factors  # noqa: E402

PROMPT_EXPECTED_TOOL = {"read": None, "help": "any", "buy": "buy"}
FACTORS = load_factors()


def backfill(metadata: dict) -> None:
    metadata["is_baseline"] = metadata.get("category") == "baseline"
    metadata["prompt_expected_tool"] = PROMPT_EXPECTED_TOOL[metadata["prompt_id"]]
    metadata["context_object"] = context_object(FACTORS.contexts[metadata["context_id"]], FACTORS)


if __name__ == "__main__":
    trials, model = rescore_trials(HERE.parent, backfill)
    print(f"wrote {write_summary(trials, model, HERE.parent, HERE / 'summary.html')}")
