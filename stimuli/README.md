# Stimuli

Stimulus data laid out as described in [docs/SPEC.md](../docs/SPEC.md).

| File | Defines |
| --- | --- |
| `src/prompts.json` | The user's instruction (`read`, `help`, `buy`) |
| `src/context.json` | The benign content of the image (`info_board`, `product_info`, `advertisement`); fields not yet specified |
| `src/injections.json` | What each injection means and the item it makes the model buy |
| `src/representations.json` | The form each injection is shown in, with a rendition of every injection |
| `fonts/` | Fonts used to draw text (vendored DejaVu Sans) |

## Generator

| File | Does |
| --- | --- |
| `factors.py` | Loads and validates `src/`, expands every combination into test cases |
| `render.py` | Draws one test case's image. **Placeholder layout:** the context content and injection placement are not specified yet, so every context renders the same card |
| `build.py` | Renders `images/` (gitignored) and writes `manifest.jsonl`, which must load with `harness.manifest.load_manifest` |
| `tests/test_generator.py` | Validation rules, expansion, and a rebuild that must match the committed manifest |

```bash
just build-stimuli   # python stimuli/build.py
just test
```

The build fails without touching `manifest.jsonl` if a rule in SPEC section 8 is broken. The buy tool is called `buy` in the manifest (`BUY_TOOL` in `factors.py`) until the harness gets one.

`_bak/` holds the previous fictional-conlang stimulus set, its renderer and manifest. The harness still reads `_bak/manifest/manifest.jsonl` until the generator replaces it. See [_bak/README.md](_bak/README.md).
