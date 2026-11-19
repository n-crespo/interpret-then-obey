# eval/

Analysis of a harness run.

```bash
just analyze runs/<date>_<name>     # = python eval/analyze_results.py runs/<date>_<name>
```

`analyze_results.py` reads the run's Inspect logs (`inspect_logs/*.eval`) with
`inspect_ai.analysis.samples_df`, prints a headline, and writes `runs/<dir>/analysis/`:

| File | What it shows |
| --- | --- |
| `outcomes.html` | Interactive, self-contained page: one mark per trial. Rows are the outcome (`outcome` in `outcomes.py`); colour is the representation (the baseline is grey), shape is the context, border is the prompt. Hover a mark for the trial's details and reply; click a legend item to show or hide it. |
| `tables.tex` | Booktabs tables of the same results (see `latex_tables`). `\input{}` it; needs `\usepackage{booktabs}` |

The `none` representation (no injection) is never counted in attack success. It is
reported on its own, as how often the model bought the injected item anyway and how
often it made any tool call. That second rate is the reference for off-target calls.

Only P(obey) is measured. P(interpret) and P(obey | interpret) need a per-trial
label of whether the model understood the payload (`docs/proposal.md`), and nothing
produces one yet.

Tests: `python -m pytest eval/tests -q` (part of `just test`).
