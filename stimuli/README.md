# Stimuli

Stimulus data laid out as described in [docs/SPEC.md](../docs/SPEC.md).

| File | Defines |
| --- | --- |
| `factors/prompts.json` | The user's instruction (`read`, `help`, `buy`) |
| `factors/context.json` | The benign content of the image (`info_board`, `product_info`, `advertisement`); fields not yet specified |
| `factors/injections.json` | What each injection means and the item it makes the model buy |
| `factors/representations.json` | The form each injection is shown in, with a rendition of every injection |
| `fonts/` | Fonts used to draw text (vendored DejaVu Sans) |

The generator that expands these into test cases is not written yet.

`old/` holds the previous fictional-conlang stimulus set, its renderer and manifest. The harness still reads `old/manifest/manifest.jsonl` until the generator replaces it. See [old/README.md](old/README.md).
