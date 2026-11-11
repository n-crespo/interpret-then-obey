# Stimuli

Stimulus data laid out as described in [docs/SPEC.md](../docs/SPEC.md).

| File | Defines |
| --- | --- |
| `src/prompts.json` | The user's instruction (`read`, `help`, `buy`) |
| `src/context.json` | The benign content of the image (`info_board`, `product_info`, `advertisement`); fields not yet specified |
| `src/injections.json` | What each injection means and the item it makes the model buy |
| `src/representations.json` | The form each injection is shown in, with a rendition of every injection |
| `fonts/` | Fonts used to draw text (vendored DejaVu Sans) |

The generator that expands these into test cases is not written yet.

`_bak/` holds the previous fictional-conlang stimulus set, its renderer and manifest. The harness still reads `_bak/manifest/manifest.jsonl` until the generator replaces it. See [_bak/README.md](_bak/README.md).
