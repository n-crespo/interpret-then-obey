# interpret-then-obey: run `just` to list recipes.
# Recipes run from the repo root with .venv's Python when it exists.

set windows-shell := ["pwsh", "-NoLogo", "-NoProfile", "-Command"]

venv_python := if os_family() == "windows" { ".venv/Scripts/python.exe" } else { ".venv/bin/python" }
system_python := if os_family() == "windows" { "python" } else { "python3" }
python := if path_exists(venv_python) == "true" { venv_python } else { system_python }

# List recipes
default:
    @just --list --unsorted

# Create .venv and install all dependencies
setup:
    {{ system_python }} -m venv .venv
    {{ venv_python }} -m pip install -r stimuli/requirements.txt -r harness/requirements.txt -r eval/requirements.txt

# Run all tests: stimuli reproducibility + harness smoke test + analysis
test *args:
    {{ python }} -m pytest stimuli/tests harness/tests eval/tests -q {{ args }}

# Render stimulus images from stimuli/src/, then rebuild manifest.jsonl per docs/SPEC.md
build-stimuli:
    {{ python }} stimuli/generate.py

# Run the harness: `just run <config.yaml> [--limit N]` or `just run --resume runs/<dir>`
run *args:
    {{ python }} -m harness.run {{ args }}

# Run the harness end to end with a mock model (no GPU/Ollama): `just run-dry [--limit N]`
run-dry *args:
    {{ python }} -m harness.run harness/configs/qwen3vl-8b-ollama.yaml --model mockllm/model {{ args }}

# LaTeX tables and summary.html per run -> runs/<dir>/analysis/, plus case_map.html comparing the runs in the last one's: `just analyze runs/<a> [runs/<b> ...]`
analyze +run_dirs:
    {{ python }} eval/analyze_results.py {{ run_dirs }}

