# eval/

Classifying responses and analysing harness runs.

**Classifier.** `classify.py` is the response classifier of
[docs/architecture.md section 4](../docs/architecture.md#4-evaluation): a plain function
of the sample's manifest fields and its `Response` (`response.py`). `scorer.py` wraps it
as the Inspect scorer `outcome`, which the harness task registers, so every run's log
holds each trial's outcome, labels and sources. Re-score a log with the command in
`scorer.py`'s docstring.

**Analysis.**

```bash
just analyze runs/<date>_<name> [runs/<other> ...]   # = python eval/analyze_results.py <the same dirs>
```

`just run` does this too when a run ends. `analyze_results.py` reads the run's Inspect
logs with their scores (`outcomes.py`, through `inspect_ai.analysis.samples_df`),
prints a headline, and writes `runs/<dir>/analysis/`:

| File | What it shows |
| --- | --- |
| `summary.html` | Every trial counted by outcome and by label (`summary_page.py`). Click one for its breakdown by factor and its trials. |
| `tables.tex` | Booktabs tables of the same results (see `latex_tables`). `\input{}` it; needs `\usepackage{booktabs}` |

Baseline rows (`is_baseline`, no injection) are never attack success. Their outcomes
are reported on their own, as the reference for the injected rows.

Only P(obey) is measured. P(interpret) and P(obey | interpret) need a per-trial
label of whether the model understood the payload (`docs/proposal.md`), and nothing
produces one yet.

Tests: `python -m pytest eval/tests -q` (part of `just test`).
