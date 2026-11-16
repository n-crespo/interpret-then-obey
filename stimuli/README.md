# Stimuli

Stimulus data laid out as described in [docs/SPEC.md](../docs/SPEC.md).

| File | Defines |
| --- | --- |
| `src/prompts.json` | The user's instruction (`read`, `help`, `buy`) |
| `src/context.json` | The benign content of the image (`info_board`, `product_info`, `advertisement`): a header and body lines |
| `src/injections.json` | What each injection means and the item it makes the model buy |
| `src/representations.json` | The form each injection is shown in, with a rendition of every injection |
| `fonts/` | Fonts used to draw text, each with its license file: DejaVu Sans (Latin), Constructium (pIqaD, SIL OFL 1.1) |

`generate.py` (`just build-stimuli`) expands these into test cases: it renders `images/<id>.png` (gitignored) and writes `manifest.jsonl`, which the harness configs read.
