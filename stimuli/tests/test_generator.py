"""Checks the spec generator (docs/SPEC.md sections 7-8).
Run from repo root:  python -m pytest stimuli/tests -q   (needs stimuli/requirements.txt)"""

import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

import PIL
import pytest

STIMULI = Path(__file__).resolve().parents[1]
REPO = STIMULI.parent
sys.path.insert(0, str(STIMULI))
sys.path.insert(0, str(REPO))

import build  # noqa: E402
import render  # noqa: E402
from harness.manifest import load_manifest  # noqa: E402
from factors import SpecError, expand, load_factors, validate  # noqa: E402

FACTORS = load_factors()
MANIFEST = [json.loads(l) for l in (STIMULI / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if l]


def _broken(mutate):
    f = copy.deepcopy(FACTORS)
    mutate(f)
    return f


def test_expands_every_combination():
    n = 1
    for name in ("prompts", "context", "injections", "representations"):
        n *= len(FACTORS[name])
    cases = expand(FACTORS)
    assert len(cases) == n
    assert len({c["id"] for c in cases}) == n


def test_committed_manifest_matches_source():
    cases = expand(FACTORS)
    assert [m["id"] for m in MANIFEST] == [c["id"] for c in cases]
    for m, c in zip(MANIFEST, cases):
        assert m["user_prompt"] == FACTORS["prompts"][c["prompt_id"]]["text"]
        assert m["expected_calls"] == [{"name": build.BUY_TOOL, "args": {"item": c["expected_item"]}}]
        assert m["tools"] == [build.BUY_TOOL]
        assert m["image"] == f"stimuli/images/{c['id']}.png"
        for k in ("prompt_id", "context_id", "injection_id", "representation_id", "category", "language", "script"):
            assert m[k] == c[k], (m["id"], k)
        assert "context" not in m  # reserved harness field (SPEC section 7)


@pytest.mark.skipif(PIL.__version__ != render.PINNED_PILLOW, reason="hashes are only stable on the pinned Pillow")
def test_build_reproduces_committed_manifest(tmp_path):
    out = tmp_path / "stimuli"
    (out / "src").mkdir(parents=True)
    for p in (STIMULI / "src").glob("*.json"):
        shutil.copy(p, out / "src" / p.name)
    rows = build.build(src_dir=out / "src", images_dir=STIMULI / "images", manifest_path=tmp_path / "manifest.jsonl")
    assert rows == MANIFEST
    for m in MANIFEST:
        assert hashlib.sha256((REPO / m["image"]).read_bytes()).hexdigest() == m["image_sha256"], m["id"]


def test_harness_loads_committed_manifest():
    if not all((REPO / m["image"]).exists() for m in MANIFEST):
        pytest.skip("images not rendered (run `just build-stimuli`)")
    assert len(load_manifest(STIMULI / "manifest.jsonl")) == len(MANIFEST)


@pytest.mark.parametrize("mutate, message", [
    (lambda f: f.update(representations={"en2": f["representations"]["english"], **f["representations"]}),
     "'english' must be the first"),
    (lambda f: f["representations"].update(
        {"x": {**f["representations"]["english"], "injections": {}}}), "no rendition"),
    (lambda f: f["representations"]["english"]["injections"].update({"ghost": {"content": ["x"]}}), "unknown injection"),
    (lambda f: f["representations"]["english"]["injections"]["buy_bear"].update({"content": []}), "non-empty list"),
    (lambda f: f["representations"]["english"].update({"category": "other"}), "category"),
    (lambda f: f["representations"]["english"].update({"script": None}), "script"),
    (lambda f: f["representations"].update({"pics": {
        "format": "image", "category": "symbols",
        "injections": {"buy_bear": {"content": ["symbols/missing.png"]}}}}), "not found"),
    (lambda f: f["injections"]["buy_bear"].pop("expected_item"), "expected_item"),
    (lambda f: f["prompts"].update({"a.b": {"text": "x"}}), "must not contain '.'"),
    (lambda f: f["context"].clear(), "defines nothing"),
])
def test_validation_rejects(mutate, message):
    with pytest.raises(SpecError, match=message):
        validate(_broken(mutate))


def test_failed_build_leaves_manifest_untouched(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    for p in (STIMULI / "src").glob("*.json"):
        shutil.copy(p, src / p.name)
    (src / "representations.json").write_text('{"other": {}}', encoding="utf-8")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("sentinel\n", encoding="utf-8")
    with pytest.raises(SpecError):
        build.build(src_dir=src, images_dir=tmp_path / "images", manifest_path=manifest)
    assert manifest.read_text(encoding="utf-8") == "sentinel\n"
    assert not (tmp_path / "images").exists()


def test_renderer_draws_the_rendition(tmp_path, monkeypatch):
    from PIL import ImageDraw
    drawn = []
    original = ImageDraw.ImageDraw.text
    monkeypatch.setattr(ImageDraw.ImageDraw, "text",
                        lambda self, xy, text, *a, **k: drawn.append(text) or original(self, xy, text, *a, **k))
    case = next(c for c in expand(FACTORS) if c["format"] == "text")
    render.render_case(case, tmp_path)
    assert drawn == case["content"]
