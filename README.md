# Interpret-Then-Obey

Do vision-language models obey prompt injections they must first *interpret*
(another language, an invented script, symbols) before they can act on them?
This repo holds the stimuli, the evaluation harness, and the analysis scripts.
It measures P(interpret) and P(obey | interpret) separately.

- [docs/proposal.md](docs/proposal.md): abstract, motivation, hypotheses, threat model, methods, related work
- [docs/research-plan.md](docs/research-plan.md): who owns which part
- [stimuli/README.md](stimuli/README.md): the fictional-language stimulus set

## Layout

| Path | What it is |
|---|---|
| `stimuli/` | Source phrases, image renderer, rendered PNGs, and the manifest the harness reads |
| `harness/` | Inspect-based runner: manifest + model config → mocked tool calls → `runs/<date>_<name>/` |
| `eval/` | Standalone Ollama benchmark and results analysis (LaTeX table) |
| `runs/` | Run outputs (logs, `results.jsonl`, `meta.json`) |

## Running locally

Requirements: Python 3.10+ (inspect-ai's minimum), and [`just`](https://github.com/casey/just)
(`scoop install just`, `brew install just`, or `cargo install just`).
A real model run also needs [Ollama](https://ollama.com) or vLLM. Nothing else does.

```bash
just setup         # create .venv and install stimuli + harness deps (Pillow pinned)
just test          # stimuli reproducibility + harness smoke test (no model needed)
just run-dry       # full harness pipeline with Inspect's mock model
```

Run `just` with no arguments to list every recipe. All recipes run from the repo root
and use `.venv`'s Python if it exists. To use a different interpreter:
`just python=/path/to/python <recipe>`. On Windows, recipes run under `pwsh`.

### Recipes

| Group | Recipe | What it does | Needs a model? |
|---|---|---|---|
| setup | `setup` | Create `.venv`, install everything | |
| | `install-stimuli` / `install-harness` | Install one requirements file into the current Python | |
| stimuli | `stimuli` | Re-render images + rebuild manifest | |
| | `stimuli-render` | Re-render PNGs into `stimuli/images/` | |
| | `stimuli-manifest` | Rebuild `stimuli/manifest/manifest.{jsonl,json}` with fresh hashes | |
| | `stimuli-test` | Check that a fresh render matches the manifest hashes (skipped if Pillow ≠ pinned) | |
| | `stimuli-check` | Rebuild, then fail if anything differs from what is committed | |
| harness | `fixtures` | Write the 3-row smoke-test manifest into `harness/fixtures/` | |
| | `harness-test` | Obey-check unit test + end-to-end run on fixtures with a mock model | |
| | `run-dry [flags]` | Real pipeline on the real manifest, mock model (scores are meaningless) | |
| | `run-ollama [flags]` | Run `qwen3-vl:8b` via Ollama | Ollama on `:11434` |
| | `run-vllm [flags]` | Run `Qwen3-VL-8B-Instruct` via vLLM | `vllm serve` on `:8000` |
| | `run <config> [flags]` | Run any config in `harness/configs/` | Whatever the config names |
| | `resume <run_dir>` | Re-run only errored/unfinished rows of a run | Same model as the original run |
| | `view <run_dir>` | Open the Inspect log viewer | |
| eval | `benchmark [model] [url]` | Standalone Ollama benchmark → `eval/results.json` | Ollama |
| | `benchmark-mock` | Simulated benchmark (overwrites `eval/results.json`) | |
| | `analyze` | Summarize `eval/results.json` → tables + `eval/results_table.tex` | |
| all | `test` | `stimuli-test` + `harness-test` | |
| | `clean` | Remove `__pycache__` / `.pytest_cache` | |

Harness flags pass straight through to `python -m harness.run`:
`--limit N`, `--ids a,b`, `--filter section=language` (repeatable), `--manifest PATH`,
`--runs-dir DIR`, `--model PROVIDER/NAME`.

### A real model run

```bash
ollama pull qwen3-vl:8b
just run-ollama --limit 5            # try a few rows first
just run-ollama                      # full manifest
just view runs/<date>_qwen3vl-8b-ollama
just resume runs/<date>_qwen3vl-8b-ollama   # if some rows errored
```

Each run directory records the config, model, manifest SHA-256, and git commit,
so a result can be traced back to exactly what produced it.

### Reproducibility notes

- Stimulus renders are byte-identical across OSes as long as the vendored fonts
  (`stimuli/fonts/`) and the pinned Pillow are used. `just stimuli-check` verifies this.
- If you change the stimuli, run `just stimuli` and commit the new images *and* manifest together.
- `harness-test` writes untracked fixture files to `harness/fixtures/`, and `run-*`
  writes to `runs/`. Don't commit either.
