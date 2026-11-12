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
    {{ python }} -m pytest stimuli/tests stimuli/_bak/tests harness/tests -q {{ args }}

# Generate the spec test cases: render stimuli/images/ and write stimuli/manifest.jsonl from stimuli/src/
build-stimuli:
    {{ python }} stimuli/build.py

# Render the legacy stimulus set in stimuli/_bak/ and rebuild its manifest (the harness still reads it)
build-stimuli-legacy:
    {{ python }} stimuli/_bak/render/generate_fictional_stimuli.py
    {{ python }} stimuli/_bak/manifest/build_manifest.py

# Run the harness: `just run <config.yaml> [--limit N]` or `just run --resume runs/<dir>`
run *args:
    {{ python }} -m harness.run {{ args }}

# Run the harness end to end with a mock model (no GPU/Ollama): `just run-dry [--limit N]`
run-dry *args:
    {{ python }} -m harness.run harness/configs/qwen3vl-8b-ollama.yaml --model mockllm/model {{ args }}

# Tables + LaTeX for a harness run (ASR, hallucination by universe/language/script): `just analyze runs/<dir>`
analyze run_dir:
    {{ python }} eval/analyze_results.py {{ run_dir }}
