"""Checks that the committed stimuli are reproducible and consistent with their source.
Run from repo root:  python -m pytest stimuli/tests -q   (needs stimuli/requirements.txt)"""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import PIL
import pytest

STIMULI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STIMULI))
from spec import load_rows  # noqa: E402


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


render = _load_module("render_stimuli", STIMULI / "render" / "generate_fictional_stimuli.py")
MANIFEST = [json.loads(l) for l in (STIMULI / "manifest" / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if l]


def test_manifest_matches_source():
    rows = {r["id"]: r for r in load_rows()}
    assert [m["id"] for m in MANIFEST] == list(rows)
    for m in MANIFEST:
        r = rows[m["id"]]
        assert m["injected_text_raw"] == (r["text"] if r["kind"] != "control" else "")
        assert m["injected_text_translation"] == r["translation"]
        assert m["user_prompt"] == r["user_prompt"]
        if m["medium"] == "text":
            assert r["text"] in m["user_prompt"]


@pytest.mark.skipif(PIL.__version__ != render.PINNED_PILLOW, reason="hashes are only stable on the pinned Pillow")
def test_rerender_matches_manifest_hashes(tmp_path):
    render.render_all(out_dir=tmp_path)
    image_rows = [m for m in MANIFEST if m.get("image")]
    assert image_rows
    for m in image_rows:
        out = tmp_path / Path(m["image"]).name
        assert out.exists(), m["id"]
        assert hashlib.sha256(out.read_bytes()).hexdigest() == m["image_sha256"], m["id"]
