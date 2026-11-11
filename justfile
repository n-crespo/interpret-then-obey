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
    {{ venv_python }} -m pip install -r stimuli/requirements.txt -r harness/requirements.txt

# Run all tests: stimuli reproducibility + harness smoke test (no model needed)
test *args:
    {{ python }} -m pytest stimuli/tests harness/tests -q {{ args }}

# Render stimulus images from src/languages/fictional_languages.json, then rebuild the manifest with their hashes
build-stimuli:
    {{ python }} stimuli/render/generate_fictional_stimuli.py
    {{ python }} stimuli/manifest/build_manifest.py

# Run the harness: `just run <config.yaml> [--limit N]` or `just run --resume runs/<dir>`
run *args:
    {{ python }} -m harness.run {{ args }}

# Run the harness end to end with a mock model (no GPU/Ollama): `just run-dry [--limit N]`
run-dry *args:
    {{ python }} -m harness.run harness/configs/qwen3vl-8b-ollama.yaml --model mockllm/model {{ args }}

# Standalone Ollama benchmark -> eval/results.json: `just benchmark [--model TAG] [--mock]`
benchmark *args:
    {{ python }} eval/run_benchmark.py {{ args }}

# Summarize eval/results.json -> tables + eval/results_table.tex
analyze:
    {{ python }} eval/analyze_results.py
