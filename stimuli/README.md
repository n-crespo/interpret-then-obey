# Stimuli: Fictional Conlangs Dataset

Test cases, rendering scripts, stimulus images and manifest for the **fictional constructed languages (conlangs)** part of the interpret-then-obey study.

## Directory structure

```
stimuli/
├── src/
│   ├── languages/
│   │   └── fictional_languages.json   # every phrase: lines, translation, verification status
│   └── stimuli.json                   # one entry per manifest row: prompt, script, sign styling
├── spec.py                            # loader shared by the renderer and the manifest builder
├── render/
│   └── generate_fictional_stimuli.py  # src -> images/*.png
├── fonts/                             # vendored DejaVu Sans (+ license); the only fonts used
├── images/                            # 27 generated PNGs (committed)
├── manifest/
│   ├── build_manifest.py              # src + images -> manifest.jsonl / manifest.json (+ image_sha256)
│   ├── manifest.jsonl                 # loaded by harness.manifest.load_manifest()
│   └── manifest.json                  # same rows as a JSON array
├── tests/test_stimuli.py              # reproducibility + consistency checks
└── requirements.txt                   # pinned Pillow
```

## Single source of truth

All text lives in `src/`. The renderer and the manifest builder both read it through `spec.py`, so the text on an image and `injected_text_raw` in the manifest cannot drift apart. To add or change a stimulus, edit `src/` and rebuild. Don't edit images or manifests by hand.

## What is on the images

- **Only the conlang text.** Images never carry an English translation, so the model has to interpret the phrase before it can obey it. Translations live in the manifest (`injected_text_translation`) for scoring only.
- **Latin-script rows** render the phrase as text in DejaVu Sans Bold.
- **`tengwar_style_cipher` / `piqad_style_cipher` rows** draw the phrase as **invented glyphs, one per letter** (Klingon is split into its 26 letters, including `tlh`, `ch`, `gh`, `ng` and `'`). The glyphs are styled after Tengwar and pIqaD but **are not the real scripts**: no model has seen these glyphs, so these rows test reading an unknown script with no legend. The image ids still say `tengwar`/`piqad` to keep them stable. Rendering real Tengwar/pIqaD needs a properly licensed font for each, which is follow-up work.
- Every image shares the same 720×460 sign layout: a franchise tag, a title and the body. There is no footer or other text saying the image is a test. Themes (`convention_badge`, `fan_merch`, `scifi_hud`, `sticky_note`, `game_card`) and colours vary per row.

## Phrase verification status

Each phrase has a `*_status` in `fictional_languages.json`, copied into every manifest row as `text_status` (together with `verified_by`):

| status | meaning |
|---|---|
| `canonical` | well-known phrase from the source work; the translation is the commonly cited one |
| `unverified` | written for this benchmark and **not checked by a speaker**. All conlang injection payloads are currently in this state, and several contain English words (`banana`, `cart`) |
| `not_a_language` | Simlish and Minionese: gibberish with no real grammar |

The `notes` field records the specific problems known so far. Treat results on `unverified` rows as provisional until someone who knows the language fills in `verified_by`. Also note that `fx-scifi-trope-injection` is an English instruction with a fictional framing phrase, so compare it against the English baseline.

## Rebuilding

```bash
python -m pip install -r stimuli/requirements.txt
python stimuli/render/generate_fictional_stimuli.py   # src -> images/
python stimuli/manifest/build_manifest.py             # src + images -> manifest (+ sha256)
python -m pytest stimuli/tests -q
```

The fonts are vendored and Pillow is pinned, so a rebuild should produce byte-identical PNGs and leave the manifest hashes unchanged. The test re-renders every image and checks this. Bumping Pillow means re-rendering and committing the new images and manifest.

The renderer raises if any drawn text (title, phrase line or cipher glyph row) overflows the sign or a theme is unknown; the manifest builder raises on duplicate ids, missing images, or PNGs in `images/` with no row.
