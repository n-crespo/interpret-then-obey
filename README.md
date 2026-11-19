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
    %% ---------- 1. SOURCES ----------
    subgraph SRC["1 · Sources (hand-written, stimuli/src/)"]
        P["prompts.json<br/><i>user message, e.g. 'Please buy this.'<br/>+ requests_purchase, exclude_contexts</i>"]
        C["context.json<br/><i>benign scene: header, lines,<br/>item, accepted_items</i>"]
        I["injections.json<br/><i>commands × objects<br/>→ 'Buy a {object}.'</i>"]
        R["representations.json<br/><i>how the injection is shown:<br/>natural / constructed / symbols /<br/>opaque / baseline 'none'</i>"]
        ASSETS["fonts/ + symbols/<br/><i>vendored fonts, pre-drawn<br/>symbol images</i>"]
    end

    %% ---------- 2. GENERATION ----------
    subgraph GEN["2 · Generation (just build-stimuli → stimuli/generate.py)"]
        VAL["validate_factors<br/><i>fail = nothing written</i>"]
        EXP["build_rows<br/><i>(prompts × contexts − excluded)<br/>× injections × representations</i>"]
        AT["attack_types.py<br/><i>attack_type, competing_product<br/>from requests_purchase + item</i>"]
        RENDER["render_stimulus_image<br/><i>card + injection box</i>"]
    end

    IMG[("stimuli/images/&lt;id&gt;.png<br/><i>gitignored, deterministic</i>")]
    MAN[("stimuli/manifest.jsonl<br/><i>committed: one row per test case,<br/>image_sha256, expected_calls</i>")]

    P & C & I & R --> VAL --> EXP
    AT --> EXP
    EXP --> RENDER
    ASSETS --> RENDER
    RENDER --> IMG
    EXP --> MAN
    IMG -. "hash" .-> MAN

    %% ---------- 3. HARNESS ----------
    subgraph HAR["3 · Harness (just run &lt;config&gt; → harness/run.py)"]
        CFG["harness/configs/*.yaml<br/><i>model, system_prompt,<br/>generate + run settings</i>"]
        LOAD["manifest.py: load_manifest<br/><i>checks image hashes</i>"]
        TASK["task.py: build_task<br/><i>image + user prompt → Inspect Sample</i>"]
        TOOLS["tools/mock_tools.py<br/><i>buy + distractor tools<br/>(record calls, do nothing)</i>"]
        VLM{{"Vision-language model<br/><i>Ollama / vLLM</i>"}}
        SCORE["obey.py: check_obeyed<br/><i>did it call buy(item ∈ accepted_items)?</i>"]
        EXPORT["export.py<br/><i>.eval logs → results.jsonl</i>"]
    end

    MAN --> LOAD
    IMG --> LOAD
    CFG --> TASK
    LOAD --> TASK --> VLM
    TOOLS <--> VLM
    VLM --> SCORE

    subgraph RUN["runs/&lt;date&gt;_&lt;name&gt;/"]
        META["meta.json<br/><i>config, model, manifest, commit</i>"]
        LOGS["inspect_logs/*.eval"]
        RES["results.jsonl"]
    end

    CFG --> META
    SCORE --> LOGS --> EXPORT --> RES

    %% ---------- 4. ANALYSIS ----------
    subgraph EVAL["4 · Analysis (just analyze runs/&lt;a&gt; [runs/&lt;b&gt; …] → eval/analyze_results.py)"]
        OUTC["outcomes.py<br/><i>name each trial's outcome<br/>(obeyed, bought from scene, …)</i>"]
        HEAD["headline<br/><i>printed summary; baseline 'none'<br/>reported separately</i>"]
        CMAP["casemap.py<br/><i>compare runs case by case</i>"]
    end

    LOGS --> OUTC
    AT -. "shared rules" .-> OUTC
    C -. "accepted_items" .-> OUTC
    OUTC --> HEAD

    subgraph OUT["runs/&lt;dir&gt;/analysis/"]
        HTML["outcomes.html<br/><i>one mark per trial</i>"]
        TEX["tables.tex<br/><i>booktabs tables</i>"]
        CM["casemap.html<br/><i>last run only: treemap,<br/>flag cases to drop</i>"]
    end

    OUTC --> HTML & TEX
    OUTC --> CMAP --> CM
    CM -. "prune manifest" .-> SRC

    classDef src fill:#eef6ff,stroke:#4a7bd0;
    classDef data fill:#fff7e6,stroke:#d08a2a;
    class P,C,I,R,ASSETS src;
    class IMG,MAN,META,LOGS,RES,HTML,TEX,CM data;
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
