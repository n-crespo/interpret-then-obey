# eval/

Classifying responses and analysing harness runs. `classify.py` defines the outcomes
and labels, and `scorer.py` runs it as an Inspect scorer during every run.
`just analyze runs/<dir> [...]` (also run at the end of `just run`) writes
`runs/<dir>/analysis/` with `summary.html` and `tables.tex`; see
`analyze_results.py`.
