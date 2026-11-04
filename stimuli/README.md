Example Structure:

```
stimuli/                   # test cases
├── src/
│   ├── languages/         # prompts/phrases per language, translations + who verified
│   ├── symbols/           # emoji, standard, hand-drawn, invented sets + legends
│   └── payloads.yaml      # add_to_cart, send_message, retarget/steer variants
├── scenes/                # base scene photos or renders the stimuli go into
├── render/                # scripts that combine stimulus + scene -> image
├── images/                # generated images (git-lfs, or gitignored + rebuilt)
└── manifest/
    ├── manifest.jsonl     # one row per stimulus and mode
    └── build_manifest.py  # src + scenes -> manifest.jsonl, writes image_sha256
```
