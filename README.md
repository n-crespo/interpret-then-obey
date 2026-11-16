# Interpret-Then-Obey

Do vision-language models obey prompt injections they must first _interpret_
(another language, an invented script, symbols) before they can act on them?
This repo holds the stimuli, the evaluation harness, and the analysis scripts.
It measures P(interpret) and P(obey | interpret) separately.

- [docs/proposal.md](docs/proposal.md): abstract, motivation, hypotheses, threat model, methods, related work
- [docs/research-plan.md](docs/research-plan.md): who owns which part
- [docs/SPEC.md](docs/SPEC.md): how stimulus data is laid out
- [stimuli/README.md](stimuli/README.md): the stimulus generator
- [eval/README.md](eval/README.md): analysis of a run

The pipeline: `stimuli/` renders the test-case images and writes the manifest,
`harness/` runs a model on the manifest with mocked tools and writes to `runs/`,
and `eval/` analyses a run.

## Running locally

Requirements: Python 3.11+ (the Pillow pinned in `stimuli/requirements.txt` has no 3.10 wheels), and [`just`](https://github.com/casey/just)
(`scoop install just`, `brew install just`, or `cargo install just`).
A real model run also needs [Ollama](https://ollama.com) or vLLM.

```bash
just setup         # create .venv and install dependencies
just test          # all tests (no model needed)
just run-dry       # full harness pipeline with Inspect's mock model
```

Run `just` with no arguments to list recipes and what each does. They run from the repo root with
`.venv`'s Python when it exists. On Windows they run under `pwsh`. Only `run` needs a real model.

Arguments after a recipe pass straight through to the script; `just run --help` lists the harness's flags.

### A real model run

```bash
ollama pull qwen3-vl:8b
just run harness/configs/qwen3vl-8b-ollama.yaml --limit 5   # try a few rows first
just run harness/configs/qwen3vl-8b-ollama.yaml             # full manifest
just run --resume runs/<date>_qwen3vl-8b-ollama             # if some rows errored
ollama pull gemma3:4b                                       # judge: a different model family
just judge runs/<date>_qwen3vl-8b-ollama                    # noticed / interpreted labels
just analyze runs/<date>_qwen3vl-8b-ollama                  # interactive plot + LaTeX tables
inspect view --log-dir runs/<date>_qwen3vl-8b-ollama/inspect_logs
```

"Obeyed" means the model actually made the expected tool call (scored by the harness).
See [eval/README.md](eval/README.md) for what `analyze` reports.

Each run directory records, in `meta.json`, what produced it,
so a result can be traced back to exactly that config, model, manifest and commit.

### Reproducibility notes

- Stimulus renders are byte-identical across OSes as long as the vendored fonts
  (`stimuli/fonts/`) and the pinned Pillow are used. `just test` checks this
  (the check is skipped, not failed, on a different Pillow version).
- If you change the stimuli, run `just build-stimuli` and commit the new `stimuli/manifest.jsonl` (the images are gitignored; their hashes are in the manifest).
- `just test` regenerates gitignored fixture files in `harness/fixtures/`, and `run`/`run-dry`
  write to `runs/`. Don't commit those by accident.
