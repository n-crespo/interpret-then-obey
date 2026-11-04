Example Structure:

```
eval/                      # role 4: grades and analyzes
├── obey_check.py          # deterministic check on the tool-call trace
├── judge/                 # LLM judge prompt, runner, different model family
├── gold/                  # hand-labeled set + agreement script (judge validation)
├── stats.py               # Wilson intervals, P(interpret), P(obey | interpret)
└── report/                # notebooks or scripts -> figures and tables
```
