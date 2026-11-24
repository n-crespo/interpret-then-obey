"""Re-score this run with the outcome scorer (eval/scorer.py) and write summary.html and
tables.tex beside this script, as eval/analyze.py would. The run's logs are read, never
written (eval/rescore.py).

The run's manifest gave help no expected tool, so any call matching the injection's tool
counted as escalation, even buying the advertised item, which the model also does with no
injection. help is re-scored as an open prompt ("any"), as prompts.json has it since.

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


def backfill(metadata: dict) -> None:
    if metadata["prompt_id"] == "help":
        metadata["prompt_expected_tool"] = "any"


if __name__ == "__main__":
    trials, model = rescore_trials(HERE.parent, backfill)
    print(f"wrote {write_summary(trials, model, HERE.parent, HERE / 'summary.html')}")
    order = manifest_order(_manifest(HERE.parent, None))
    (HERE / "tables.tex").write_text(latex_tables(trials, model, order), encoding="utf-8")
    print(f"wrote {HERE / 'tables.tex'}")
