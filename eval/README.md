# eval/

Analysis of a harness run.

```bash
just analyze runs/<date>_<name> [runs/<other> ...]   # = python eval/analyze_results.py <the same dirs>
```

`trials.py` reads the run's Inspect logs (`inspect_logs/*.eval`) into one `Trial` per case and
epoch: the `Case` that was shown, the model's `Response` and the scorer's verdict.
`outcomes.py` gives each trial one outcome and lists them all (`OUTCOMES`).
`analyze_results.py` prints a headline and writes `runs/<dir>/analysis/` for each run:

| File | What it shows |
| --- | --- |
| `case_map.html` | Only in the last run's folder. Interactive, self-contained treemap of every test case (`eval/case_map_page.py`), one outcome strip per run given (`outcome` in `outcomes.py`). Hover for each run's call and reply; click a case or group to flag it for dropping from the manifest and copy the flagged ids. |
| `summary.html` | Every trial counted by outcome, prompts and contexts abstracted away (`eval/summary_page.py`). Click an outcome for its breakdown and trials. |
| `tables.tex` | Booktabs tables of the same results (see `latex_tables`). `\input{}` it; needs `\usepackage{booktabs}` |

The `none` representation (no injection) is never counted in attack success. It is
reported on its own, as how often the model bought the injected item anyway and how
often it made any tool call. That second rate is the reference for off-target calls.

Only P(obey) is measured. P(interpret) and P(obey | interpret) need a per-trial
label of whether the model understood the payload (`docs/proposal.md`), and nothing
produces one yet.

Tests: `python -m pytest eval/tests -q` (part of `just test`).
