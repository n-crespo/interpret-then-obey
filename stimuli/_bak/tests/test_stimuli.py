"""Checks that the committed stimuli are reproducible and consistent with their source.
Run from repo root:  python -m pytest stimuli/_bak/tests -q   (needs stimuli/requirements.txt)"""

import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import PIL
import pytest
from PIL import ImageDraw

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


RENDERER_SRC = STIMULI / "render" / "generate_fictional_stimuli.py"
IMAGE_ROWS = [r for r in load_rows() if r["medium"] == "image"]


def _render_capturing_text(row, out_dir, monkeypatch):
    """Render one row and return (strings passed to ImageDraw.text, PNG bytes)."""
    drawn = []
    original = ImageDraw.ImageDraw.text

    def spy(self, xy, text, *args, **kwargs):
        drawn.append(text)
        return original(self, xy, text, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(ImageDraw.ImageDraw, "text", spy)
        path = render.render_row(row, out_dir)
    return drawn, path.read_bytes()


def _expected_text(row):
    header = row["render"].get("header")
    body = [] if "glyphs" in row["render"] else row["lines"]
    return ([header] if header else []) + list(body)


@pytest.mark.parametrize("row", IMAGE_ROWS, ids=[r["id"] for r in IMAGE_ROWS])
def test_renderer_draws_exactly_spec_text(row, tmp_path, monkeypatch):
    drawn, _ = _render_capturing_text(row, tmp_path, monkeypatch)
    assert drawn == _expected_text(row)


def _sign_strings():
    out = set()
    for r in load_rows():
        out.update(r.get("lines", []))
        if r.get("render", {}).get("header"):
            out.add(r["render"]["header"])
    return {s for s in out if len(s.strip()) >= 4}


def test_renderer_has_no_hardcoded_sign_text():
    tree = ast.parse(RENDERER_SRC.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    constants = [n.value for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]
    signs = _sign_strings()
    assert signs
    leaked = sorted({s for s in signs for c in constants if s in c})
    assert not leaked, f"sign text hard-coded in renderer: {leaked}"


def test_editing_spec_changes_render(tmp_path, monkeypatch):
    row = next(r for r in IMAGE_ROWS if "glyphs" not in r["render"] and r["kind"] != "control")
    edited = copy.deepcopy(row)
    edited["lines"] = ["EDITED SPEC LINE", "SECOND EDIT"]
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    drawn_a, png_a = _render_capturing_text(row, tmp_path / "a", monkeypatch)
    drawn_b, png_b = _render_capturing_text(edited, tmp_path / "b", monkeypatch)
    assert drawn_b == _expected_text(edited)
    assert drawn_a != drawn_b
    assert png_a != png_b
