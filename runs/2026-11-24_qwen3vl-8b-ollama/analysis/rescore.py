"""Re-score this run with today's scorer (eval/scorer.py) and write summary.html,
tables.tex and interpretation.tex beside this script, as eval/analyze.py would. The run's
logs are read, never written (eval/rescore.py).

The run was scored at run time, before the scorer classified decoy picks and gave the
over-helpful outcome, and before the mention controls were split from the injected rows.
Every sample is kept, including those of prompts, contexts and representations today's
stimuli no longer make (directions, remind, meeting_notes, transit_notice, the
representations #140 dropped): their manifest rows carry every field the scorer reads.
Only the context is mapped onto today's stimuli:
- info_board is library_board today, with the same image: ids and context_id are renamed.
- context_object is rebuilt as stimuli/build.py makes it from today's contexts.json
  (eval/rescore.py past_context_object, which keeps the removed contexts' own).
say samples stay out of the attack tables and feed the interpretation report
(eval/interpretation).

Rows today's stimuli no longer make exist only in this run, so when it is combined with
another (eval/combine.py), compare rates within matching cells, not pooled over them.

`rescored_trials()` returns the trials, for eval/combine.py.

Run from the repo root:  python runs/2026-11-24_qwen3vl-8b-ollama/analysis/rescore.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))  # repo root

from eval.analyze import write_analysis  # noqa: E402
from eval.rescore import RENAMED_CONTEXTS, past_context_object, rescore_trials, renamed_id  # noqa: E402
from eval.trials import manifest_order  # noqa: E402
from stimuli.load import load_factors  # noqa: E402

FACTORS = load_factors()


def backfill(metadata: dict) -> None:
    metadata["context_object"] = past_context_object(metadata["context_id"], FACTORS)
    metadata["context_id"] = RENAMED_CONTEXTS.get(metadata["context_id"], metadata["context_id"])


def rename(sample) -> None:
    sample.id = renamed_id(str(sample.id))


def rescored_trials(run_dir: Path = HERE.parent) -> tuple[list[dict], str | None]:
    return rescore_trials(run_dir, backfill, rename)


if __name__ == "__main__":
    trials, model = rescored_trials()
    write_analysis(trials, model, HERE.parent, manifest_order(ROOT / "stimuli" / "manifest.jsonl"))
