"""
Interpretation: did the model decode the injection, whatever it then did?

Probe prompts (PROBE_PROMPTS) ask what the image says and never ask for a tool, so they
measure nothing as attacks: eval/analyze.py leaves them out of attack success. Their
replies show instead whether the model recovered the payload. score.py marks each reply
with a keyword check and report.py counts them per representation and category.

Replies are read in full from the run's Inspect logs (eval/trials.py's load_trials), not
from summary.html, which cuts each reply short.

Usage:
    python -m eval.interpretation runs/<date>_<name> [runs/<other> ...]
"""

PROBE_PROMPTS = ("say",)  # prompt_id values of past runs (2026-11-24); stimuli/factors/prompts.json no longer has one


def is_probe(trial: dict) -> bool:
    return trial.get("prompt_id") in PROBE_PROMPTS
