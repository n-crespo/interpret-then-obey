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

```mermaid
flowchart LR
    subgraph SRC["1 · Sources: the experiment's factors"]
        P["prompts.json<br/><i>vary how strongly the user<br/>asks for an action</i>"]
        C["context.json<br/><i>vary how strongly the scene<br/>itself invites a purchase</i>"]
        I["injections.json<br/><i>what the attacker wants<br/>the model to do</i>"]
        R["representations.json<br/><i>vary representation of<br/> the injection</i>"]
        ASSETS["fonts/ + symbols/<br/><i>draw scripts and symbols<br/>a plain font can't</i>"]
    end

    GEN["<b>2 · Generation</b><br/><i>just build-stimuli</i><br/>Combine every factor into test cases<br/>and render one image per case"]

    IMG[("Test-case images<br/><i>what the model sees</i>")]
    MAN[("manifest.jsonl<br/><i>one fixed, reproducible set of cases<br/>and what counts as obeying each</i>")]

    HAR["<b>3 · Harness</b><br/><i>just run &lt;config&gt;</i><br/>Show each case to a vision model with mock tools<br/>and score whether it called buy as injected"]

    CFG["Run config<br/><i>choose the model and settings<br/>without touching the cases</i>"]

    subgraph RUN["Run folder"]
        META["meta.json<br/><i>trace a result back to<br/>what produced it</i>"]
        LOGS["Inspect logs<br/><i>full conversations,<br/>for inspecting any trial</i>"]
    end

    EVAL["<b>4 · Analysis</b><br/><i>just analyze runs/&lt;a&gt; [runs/&lt;b&gt; …]</i><br/>Name each trial's outcome and compare<br/>obey rates across factors and runs"]

    subgraph OUT["Analysis outputs"]
        HTML["outcomes.html<br/><i>see what the model did on each case,<br/>compare runs, and flag cases to drop</i>"]
        SUM["summary.html<br/><i>how often each outcome happened,<br/>and the trials behind it</i>"]
        TEX["tables.tex<br/><i>results ready for the paper</i>"]
    end

    SRC --> GEN
    GEN --> IMG & MAN
    IMG & MAN --> HAR
    CFG --> HAR
    HAR --> META & LOGS
    LOGS --> EVAL
    EVAL --> SUM & HTML & TEX

    classDef src fill:#eef6ff,stroke:#4a7bd0,color:#1a1a1a;
    classDef data fill:#fff7e6,stroke:#d08a2a,color:#1a1a1a;
    classDef step fill:#e9f7ee,stroke:#3a9a5b,color:#1a1a1a;
    class P,C,I,R,ASSETS,CFG src;
    class IMG,MAN,META,LOGS,HTML,TEX data;
    class GEN,HAR,EVAL step;
```

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
