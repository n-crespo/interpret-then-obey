# Stimuli

The factor files are in `factors/`. `just build-stimuli` renders `images/` (gitignored) and
writes `manifest.jsonl`, which the harness configs read. Start from
`build.py`; what each factor file holds is declared in `schema.py`.
Vendored fonts and images and the drawn symbols are in `assets/`, each third-party file
with its licence beside it; `tools/` holds the scripts that made them, run by hand.
