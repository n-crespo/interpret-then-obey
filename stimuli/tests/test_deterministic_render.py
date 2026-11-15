"""Re-render a few manifest rows and check they hash to the committed image_sha256.

generate.py verifies the manifest against the images it just rendered, so it cannot
notice when another platform renders different bytes. This test compares against the
committed manifest instead. CI runs it on Linux, Windows and macOS.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_JSONL = ROOT / "stimuli" / "manifest.jsonl"

# One text representation (font layout) and one image representation (asset resize/paste).
CASES = [
    "help.advertisement.buy_bear.english",
    "read.info_board.buy_bear.klingon_piqad",
]


def _load_generate():
    spec = importlib.util.spec_from_file_location("stimuli_generate", ROOT / "stimuli" / "generate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("sample_id", CASES)
def test_render_matches_committed_hash(sample_id, tmp_path):
    gen = _load_generate()
    rows = {r["id"]: r for r in map(json.loads, MANIFEST_JSONL.read_text(encoding="utf-8").splitlines())}
    row = rows[sample_id]

    contexts = gen.load_json(gen.SRC_DIR / "context.json")
    representations = gen.load_json(gen.SRC_DIR / "representations.json")
    rep = representations[row["representation_id"]]

    out = tmp_path / f"{sample_id}.png"
    gen.render_stimulus_image(
        out,
        row["context_id"],
        contexts[row["context_id"]],
        rep,
        rep["injections"][row["injection_id"]],
    )
    assert gen.sha256_file(out) == row["image_sha256"]
