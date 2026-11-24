"""Re-score this run with the outcome scorer (eval/scorer.py) and write summary.html and
tables.tex beside this script, as eval/analyze.py would. The run's logs are read, never
written (eval/rescore.py).

The run's manifest gave help no expected tool, so any call matching the injection's tool
counted as escalation, even buying the advertised item, which the model also does with no
injection. help is re-scored as an open prompt ("any"), as prompts.json has it since.
context_object is rebuilt as stimuli/build.py makes it from today's contexts.json, which
adds the scene's header and, for scenes with no item, words naming their subject, so an
action on the scene (directions to Platform 2, buying the "community bulletin") counts as
on the scene.

Trials whose injection today's stimuli no longer make (stimuli/load.py expand_injections)
are dropped: the search_web tool and its Mount Rainier injection are gone. The model used
search_web to decode or translate injections, and a search for Mount Rainier was hard to
score.

Run from the repo root:  python runs/2026-11-22_qwen3vl-8b-ollama-t07/analysis/rescore.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))  # repo root

from eval.analyze import _manifest  # noqa: E402
from eval.rescore import rescore_trials  # noqa: E402
from eval.tables import latex_tables  # noqa: E402
from eval.trials import manifest_order  # noqa: E402
from eval.summary_page import write_summary  # noqa: E402
from stimuli.build import context_object  # noqa: E402
from stimuli.load import expand_injections, load_factors  # noqa: E402

FACTORS = load_factors()
INJECTIONS = expand_injections(FACTORS)


def backfill(metadata: dict) -> None:
    if metadata["prompt_id"] == "help":
        metadata["prompt_expected_tool"] = "any"
    metadata["context_object"] = context_object(FACTORS.contexts[metadata["context_id"]], FACTORS)


if __name__ == "__main__":
    trials, model = rescore_trials(HERE.parent, backfill)
    trials = [t for t in trials if t["injection_id"] in INJECTIONS]
    print(f"wrote {write_summary(trials, model, HERE.parent, HERE / 'summary.html')}")
    order = manifest_order(_manifest(HERE.parent, None))
    (HERE / "tables.tex").write_text(latex_tables(trials, model, order), encoding="utf-8")
    print(f"wrote {HERE / 'tables.tex'}")
