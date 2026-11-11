"""Checks that the committed stimulus images are reproducible from the renderer.
Run from repo root:  python -m pytest stimuli/tests -q   (needs stimuli/requirements.txt)"""

import hashlib
import importlib.util
import json
from pathlib import Path

import PIL
import pytest

STIMULI = Path(__file__).resolve().parents[1]


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


render = _load_module("render_stimuli", STIMULI / "render" / "generate_fictional_stimuli.py")
MANIFEST = [json.loads(l) for l in (STIMULI / "manifest" / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if l]


@pytest.mark.skipif(PIL.__version__ != render.PINNED_PILLOW, reason="hashes are only stable on the pinned Pillow")
def test_rerender_matches_manifest_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "IMAGES_DIR", tmp_path)
    render.render_all()
    image_rows = [m for m in MANIFEST if m.get("image")]
    assert image_rows
    for m in image_rows:
        out = tmp_path / Path(m["image"]).name
        assert out.exists(), m["id"]
        assert hashlib.sha256(out.read_bytes()).hexdigest() == m["image_sha256"], m["id"]
