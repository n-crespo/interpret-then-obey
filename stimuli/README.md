# Stimuli

Stimulus data laid out as described in [docs/SPEC.md](../docs/SPEC.md): the factor files are in `src/`, and each third-party font or image keeps its licence beside it.

`generate.py` (`just build-stimuli`) expands the factor files into test cases: it renders `images/<id>.png` (gitignored) and writes `manifest.jsonl`, one `Case` (`cases.py`) per line, which the harness configs read. Each case's attack type comes from `attack_types.py` (see [Attack type](../docs/SPEC.md#attack-type)).
