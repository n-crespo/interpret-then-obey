# Interpret-Then-Obey

Do vision-language models obey prompt injections they must first _interpret_
(another language, an invented script, symbols) before they can act on them?
This repo holds the stimuli, the evaluation harness, and the analysis scripts.
It measures P(interpret) and P(obey | interpret) separately.

- [docs/proposal.md](docs/proposal.md): abstract, motivation, hypotheses, threat model, methods, related work
- [docs/research-plan.md](docs/research-plan.md): who owns which part
- [docs/SPEC.md](docs/SPEC.md): how stimulus data is laid out
- [stimuli/README.md](stimuli/README.md): the stimulus factor files and generator

## Layout

| Path       | What it is                                                                                |
| ---------- | ----------------------------------------------------------------------------------------- |
| `stimuli/` | Source phrases, image renderer, rendered pngs, and the manifest the harness reads         |
| `harness/` | Inspect-based runner: manifest + model config → mocked tool calls → `runs/<date>_<name>/` |
| `eval/`    | Analysis of a harness run (reads the Inspect logs): breakdown tables + LaTeX              |
| `runs/`    | Run outputs (logs, `results.jsonl`, `meta.json`)                                          |

## Running locally

Requirements: Python 3.11+ (the pinned `pillow==13.0.0` has no 3.10 wheels), and [`just`](https://github.com/casey/just)
(`scoop install just`, `brew install just`, or `cargo install just`).
A real model run also needs [Ollama](https://ollama.com) or vLLM.

```bash
just setup         # create .venv and install stimuli + harness deps
just test          # stimuli reproducibility + harness smoke test (no model needed)
just run-dry       # full harness pipeline with Inspect's mock model
```

Run `just` with no arguments to list recipes. They run from the repo root with
`.venv`'s Python when it exists. On Windows they run under `pwsh`.

| Recipe               | What it does                                                         | Needs a model?          |
| -------------------- | -------------------------------------------------------------------- | ----------------------- |
| `setup`              | Create `.venv` and install everything                                |                         |
| `test [pytest args]` | Re-render stimuli and compare to manifest hashes + harness smoke test |                         |
| `build-stimuli`      | Render PNGs from `stimuli/src/`, rebuild `stimuli/manifest.jsonl` + hashes |                         |
| `run <config> [...]` | Run the harness on a config in `harness/configs/`                    | Whatever the config names |
| `run-dry [...]`      | Same pipeline on the real manifest with a mock model                 |                         |
| `analyze <run_dir>`  | Tables by manifest factor for a run → prints + `<run_dir>/results_table.tex` |                  |

Flags after a recipe pass straight through to the script. For `run`/`run-dry`:
`--limit N`, `--ids a,b`, `--filter category=natural`, `--model PROVIDER/NAME`,
`--runs-dir DIR`, or `--resume runs/<dir>` to re-run only errored rows.

### A real model run

```bash
ollama pull qwen3-vl:8b
just run harness/configs/qwen3vl-8b-ollama.yaml --limit 5   # try a few rows first
just run harness/configs/qwen3vl-8b-ollama.yaml             # full manifest
just run --resume runs/<date>_qwen3vl-8b-ollama             # if some rows errored
just analyze runs/<date>_qwen3vl-8b-ollama                  # tables + LaTeX
inspect view --log-dir runs/<date>_qwen3vl-8b-ollama/inspect_logs
```

"Obeyed" means the model actually made the expected tool call (scored by the harness).
`analyze` reads `inspect_logs/*.eval` and reports, by prompt, context, representation, category and script:
attack success with 95% Wilson intervals, off-target tool calls (e.g. buying the product in the scene),
and the no-injection baseline on its own. It measures P(obey) only: there is no interpretation label yet,
so P(interpret) and P(obey | interpret) are not computed (the report says why).

Each run directory records the config, model, manifest SHA-256, and git commit,
so a result can be traced back to exactly what produced it.

### Reproducibility notes

- Stimulus renders are byte-identical across OSes as long as the vendored fonts
  (`stimuli/fonts/`) and the pinned Pillow are used. `just test` checks this
  (the check is skipped, not failed, on a different Pillow version).
- If you change the stimuli, run `just build-stimuli` and commit the new `stimuli/manifest.jsonl` (the images are gitignored; their hashes are in the manifest).
- `just test` regenerates gitignored fixture files in `harness/fixtures/`, and `run`/`run-dry`
  write to `runs/`. Don't commit those by accident.
