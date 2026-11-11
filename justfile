# interpret-then-obey: one entry point for every project action.
#
#   just                 list all recipes
#   just setup           create .venv and install all dependencies
#   just stimuli         re-render images + rebuild manifest
#   just test            run every test suite
#   just run-dry         run the harness end to end with a mock model
#
# Every recipe runs from the repo root. Python comes from .venv when it exists,
# otherwise from PATH; override with `just python=/path/to/python <recipe>`.

set windows-shell := ["pwsh", "-NoLogo", "-NoProfile", "-Command"]

venv := ".venv"
venv_python := if os_family() == "windows" { venv / "Scripts/python.exe" } else { venv / "bin/python" }
system_python := if os_family() == "windows" { "python" } else { "python3" }
python := if path_exists(venv_python) == "true" { venv_python } else { system_python }

ollama_config := "harness/configs/qwen3vl-8b-ollama.yaml"
vllm_config := "harness/configs/qwen3vl-8b-vllm.yaml"

# List all recipes
default:
    @just --list --unsorted

# ─── Setup ──────────────────────────────────────────────────────────────────

# Create .venv and install stimuli + harness dependencies
[group('setup')]
setup:
    {{ system_python }} -m venv {{ venv }}
    {{ venv_python }} -m pip install --upgrade pip
    {{ venv_python }} -m pip install -r stimuli/requirements.txt -r harness/requirements.txt

# Install only the pinned stimulus-rendering dependencies (Pillow)
[group('setup')]
install-stimuli:
    {{ python }} -m pip install -r stimuli/requirements.txt

# Install only the harness dependencies (inspect-ai, openai, pyyaml, pytest)
[group('setup')]
install-harness:
    {{ python }} -m pip install -r harness/requirements.txt

# ─── Stimuli ────────────────────────────────────────────────────────────────

# Re-render images and rebuild the manifest (full stimuli rebuild)
[group('stimuli')]
stimuli: stimuli-render stimuli-manifest

# Re-render all stimulus PNGs into stimuli/images/
[group('stimuli')]
stimuli-render:
    {{ python }} stimuli/render/generate_fictional_stimuli.py

# Rebuild stimuli/manifest/manifest.{jsonl,json} with fresh image_sha256 hashes
[group('stimuli')]
stimuli-manifest:
    {{ python }} stimuli/manifest/build_manifest.py

# Check that a fresh render matches the committed manifest hashes
[group('stimuli')]
stimuli-test:
    {{ python }} -m pytest stimuli/tests -q

# Rebuild stimuli and fail if anything differs from what is committed
[group('stimuli')]
stimuli-check: stimuli
    git diff --exit-code --stat -- stimuli/

# ─── Harness ────────────────────────────────────────────────────────────────

# Generate the throwaway smoke-test manifest + images in harness/fixtures/
[group('harness')]
fixtures:
    {{ python }} harness/fixtures/make_fixtures.py

# GPU-free smoke test of manifest loading, tools, scorer and export (mock model)
[group('harness')]
harness-test:
    {{ python }} -m pytest harness/tests -q

# Run the harness on a config: `just run <config.yaml> [--limit N] [--ids a,b] [--filter section=language]`
[group('harness')]
run config *args:
    {{ python }} -m harness.run {{ config }} {{ args }}

# Run the harness on the Ollama qwen3-vl config: `just run-ollama [--limit N] ...`
[group('harness')]
run-ollama *args: (run ollama_config args)

# Run the harness on the vLLM qwen3-vl config: `just run-vllm [--limit N] ...`
[group('harness')]
run-vllm *args: (run vllm_config args)

# Dry run with Inspect's mock model, no GPU/Ollama needed: `just run-dry [--limit N] ...`
[group('harness')]
run-dry *args: (run ollama_config "--model mockllm/model" args)

# Re-run only errored/unfinished rows of an existing run: `just resume runs/<dir>`
[group('harness')]
resume run_dir:
    {{ python }} -m harness.run --resume {{ run_dir }}

# Open the Inspect log viewer for a run: `just view runs/<dir>`
[group('harness')]
view run_dir:
    {{ python }} -m inspect_ai view --log-dir {{ run_dir }}/inspect_logs

# ─── Eval ───────────────────────────────────────────────────────────────────

# Standalone benchmark against Ollama -> eval/results.json
[group('eval')]
benchmark model="qwen3-vl:8b" url="http://localhost:11434":
    {{ python }} eval/run_benchmark.py --model {{ model }} --url {{ url }}

# Simulated benchmark run without Ollama (pipeline check)
[group('eval')]
benchmark-mock:
    {{ python }} eval/run_benchmark.py --mock

# Summarize eval/results.json -> tables + eval/results_table.tex
[group('eval')]
analyze:
    {{ python }} eval/analyze_results.py

# ─── All ────────────────────────────────────────────────────────────────────

# Run every test suite (stimuli reproducibility + harness smoke test)
[group('all')]
test: stimuli-test harness-test

# Remove Python caches and pytest artifacts
[group('all')]
clean:
    {{ python }} -c "import pathlib, shutil; [shutil.rmtree(p) for n in ('__pycache__', '.pytest_cache') for p in pathlib.Path('.').rglob(n) if '.venv' not in p.parts]"
