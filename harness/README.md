Example Structure:

```
harness/                   # role 3: runs rows against a model
├── run.py                 # CLI: manifest + config -> run log
├── models/                # one adapter per backend (ollama qwen3-vl, others later)
├── tools/                 # mocked buy plus AR-glasses distractor tools (save_photo, send_message, ...) + trace capture
├── cache.py               # keyed on (row, config, model build, seed)
└── configs/               # one yaml per run: model, temperature, seed, samples
```
