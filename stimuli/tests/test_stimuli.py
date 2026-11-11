"""Checks that the committed stimuli are reproducible and consistent with their source.
Run from repo root:  python -m pytest stimuli/tests -q   (needs stimuli/requirements.txt)"""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import PIL
import pytest
from PIL import Image, ImageDraw

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
        if m["medium"] == "text":
            assert r["text"] in m["user_prompt"]


def test_images_carry_no_english_translation():
    for r in load_rows():
        if r["medium"] == "image":
            assert not any("[" in line for line in r["lines"]), r["id"]


@pytest.mark.skipif(PIL.__version__ != render.PINNED_PILLOW, reason="hashes are only stable on the pinned Pillow")
def test_rerender_matches_manifest_hashes(tmp_path):
    rows = {r["id"]: r for r in load_rows()}
    for m in MANIFEST:
        if m["medium"] != "image":
            continue
        out = render.render_row(rows[m["id"]], out_dir=tmp_path)
        assert hashlib.sha256(out.read_bytes()).hexdigest() == m["image_sha256"], m["id"]


@pytest.mark.parametrize("script", ["tengwar", "piqad"])
def test_cipher_glyphs_are_distinct(script):
    alphabet = render.LATIN_ALPHABET if script == "tengwar" else render.KLINGON_ALPHABET
    seen = set()
    for i, _ in enumerate(alphabet):
        img = Image.new("RGB", (40, 80), "white")
        d = ImageDraw.Draw(img)
        if script == "tengwar":
            render.tengwar_glyph(d, 5, 60, i, False, (0, 0, 0), (200, 0, 0))
        else:
            render.piqad_glyph(d, 5, 60, i, (0, 0, 0), (90, 90, 90))
        seen.add(img.tobytes())
    assert len(seen) == len(alphabet)


def test_cipher_pairs_differ():
    by_id = {m["id"]: m for m in MANIFEST}
    for stem in ("fx-elvish-tengwar-image", "fx-klingon-piqad-image"):
        assert by_id[f"{stem}-injection"]["image_sha256"] != by_id[f"{stem}-benign"]["image_sha256"]
