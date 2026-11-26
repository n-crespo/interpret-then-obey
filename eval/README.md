# eval/

Classifying responses and analysing harness runs. `classify.py` defines the outcomes
and labels, and `scorer.py` runs it as an Inspect scorer during every run.
`just analyze runs/<dir> [...]` (also run at the end of `just run`) writes
`runs/<dir>/analysis/` with `summary.html` and `tables.tex`; see
`analyze.py` (LaTeX in `tables.py`).

`just merge-runs runs/<out> runs/<a> runs/<b>` merges runs that together cover one
manifest into one run folder for `just analyze`; see `merge_runs.py`.

Probe prompts (`PROBE_PROMPTS` in `interpretation/__init__.py`) ask what the image says
and never ask for a tool, so they are left out of attack success. `interpretation/` scores
their replies for whether the model recovered the payload; `just analyze` prints it and
writes `interpretation.tex`, or run `python -m eval.interpretation runs/<dir>`. It reads
the full replies from `runs/<dir>/inspect_logs/`, which summary.html cuts short.
