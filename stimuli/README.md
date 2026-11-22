# Stimuli

Stimulus data laid out as described in [docs/SPEC.md](../docs/SPEC.md): the factor files are in `src/`, and each third-party font or image keeps its licence beside it.

`just build-stimuli` runs `generate_samples.py`, which renders `images/<image id>.png` (gitignored) and writes `manifest.jsonl`, which the harness configs read.

The core logic:

- `factors.py` loads and validates the factor files into the types in `schema.py`, and expands injections.
- `generate_images.py` decides which images exist and renders them.
- `generate_samples.py` pairs prompts with images and writes the manifest.

Helpers: `render.py` draws one image, and `files.py` holds the JSON loading, hashing and staged write. Each sample's attack type comes from `attack_types.py`, which the analysis uses too (see [Attack type](../docs/SPEC.md#attack-type)).
