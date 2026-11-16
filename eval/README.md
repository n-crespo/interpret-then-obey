# eval/

Analysis of a harness run.

```bash
just analyze runs/<date>_<name>     # = python eval/analyze_results.py runs/<date>_<name>
```

`analyze_results.py` reads the run's Inspect logs (`runs/<dir>/inspect_logs/*.eval`) with
`inspect_ai.analysis.samples_df`, so it does not depend on `results.jsonl`. It prints:

- the headline: attack success (ASR) on injected rows with a 95% Wilson interval, the
  off-target and no-call rates, and the no-injection baseline (`representation_id: none`)
  on its own;
- injected rows by representation, category, script, prompt and context;
- baseline vs injected rows for each prompt × context, so off-target calls on injected
  rows can be compared with what the model does with no injection;
- an outcome grid, one character per trial;
- what the run can and cannot say about P(interpret) and P(obey | interpret).

It also writes `runs/<dir>/results_table.tex` (by representation, with the baseline row).

Tests: `python -m pytest eval/tests -q` (part of `just test`).

Planned, not built yet:

```
eval/
├── judge/                 # LLM judge for "interpreted", different model family
├── gold/                  # hand-labeled set + agreement script (judge validation)
└── report/                # figures
```
