# Stimuli

The factor files are in `src/`. `just build-stimuli` renders `images/` (gitignored) and
writes `manifest.jsonl`, which the harness configs read. Start from
`generate_samples.py`; what each factor file holds is declared in `schema.py`.
Third-party fonts and images keep their licence beside them.
