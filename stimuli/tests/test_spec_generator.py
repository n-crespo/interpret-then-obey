"""Tests for stimuli/generate.py per docs/SPEC.md."""

import json
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
STIMULI = ROOT / "stimuli"
SRC = STIMULI / "src"
MANIFEST_JSONL = STIMULI / "manifest.jsonl"


def test_factor_files():
    prompts = json.loads((SRC / "prompts.json").read_text(encoding="utf-8"))
    contexts = json.loads((SRC / "context.json").read_text(encoding="utf-8"))
    injections = json.loads((SRC / "injections.json").read_text(encoding="utf-8"))
    representations = json.loads((SRC / "representations.json").read_text(encoding="utf-8"))

    assert len(prompts) == 3
    assert set(prompts) == {"read", "help", "buy"}

    assert len(contexts) == 3
    assert set(contexts) == {"info_board", "product_info", "advertisement"}

    assert len(injections) == 1
    assert "buy_bear" in injections
    assert injections["buy_bear"]["expected_item"] == "bear"

    # Rule 1: english is the first representation
    assert list(representations.keys())[0] == "english"

    # The no-injection baseline is one representation, last, with nothing to render.
    baselines = [rep_id for rep_id, rep in representations.items() if rep["category"] == "baseline"]
    assert baselines == ["none"] == list(representations)[-1:]
    assert representations["none"]["format"] == "none"
    assert "injections" not in representations["none"]

    # Rule 2: every (non-baseline) representation has a rendition for every injection
    for rep_id, rep in representations.items():
        if rep["format"] == "none":
            continue
        assert "buy_bear" in rep["injections"], f"{rep_id} missing buy_bear"
        content = rep["injections"]["buy_bear"]["content"]
        assert isinstance(content, list) and len(content) > 0
        if rep["format"] == "image":
            for p in content:
                assert (ROOT / p).exists(), f"Image asset {p} not found"


def test_committed_manifest_rows():
    # Reads the committed manifest directly: stimuli/images/ is gitignored, so this
    # must pass on a fresh clone. Hashes are checked against a fresh build in
    # test_committed_manifest.py::test_build_reproduces_committed_manifest.
    rows = [json.loads(line) for line in MANIFEST_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 90

    # 9 baseline rows: one per prompt x context, injection box left empty.
    baseline = [r for r in rows if r["category"] == "baseline"]
    assert len(baseline) == 9
    assert {(r["prompt_id"], r["context_id"]) for r in baseline} == {
        (p, c) for p in ("read", "help", "buy") for c in ("info_board", "product_info", "advertisement")
    }
    for r in baseline:
        assert r["representation_id"] == "none"
        assert r["language"] is None and r["script"] is None
    # The baseline must look like no other image.
    assert len({r["image_sha256"] for r in baseline}) == 3  # one image per context
    assert not {r["image_sha256"] for r in baseline} & {r["image_sha256"] for r in rows if r["category"] != "baseline"}

    for r in rows:
        assert r["tools"] == ["buy"]
        assert r["expected_calls"] == [{"name": "buy", "args": {"item": "bear"}}]
        assert r["id"].startswith(f"{r['prompt_id']}.{r['context_id']}.{r['injection_id']}.{r['representation_id']}")
        assert r["image"].startswith("stimuli/images/")
        assert len(r["image_sha256"]) == 64


def test_no_english_translations_in_conlang_content():
    representations = json.loads((SRC / "representations.json").read_text(encoding="utf-8"))
    for rep_id, rep in representations.items():
        if rep["category"] == "constructed" and rep["format"] == "text":
            content = rep["injections"]["buy_bear"]["content"]
            joined = " ".join(content).lower()
            # None of them should contain "buy a bear" or English translations
            assert "buy a bear" not in joined
            assert "ignore user" not in joined
            assert "add a banana" not in joined
            assert not re.search(r"\bbear\b", joined, re.IGNORECASE), (
                f"{rep_id} rendition contains the English word 'bear': {content}"
            )


def _ink(font, ch):
    from PIL import Image, ImageDraw
    img = Image.new("L", (160, 160), 0)
    ImageDraw.Draw(img).text((40, 30), ch, font=font, fill=255)
    return img.tobytes()


def test_fonted_renditions_have_no_missing_glyphs():
    """Every character of a rendition drawn with its own `font` must exist in that font.

    A missing character falls back to .notdef (tofu, or nothing at all), so its
    rendering equals that of a code point no font maps (U+0378, unassigned).
    """
    from PIL import ImageFont

    representations = json.loads((SRC / "representations.json").read_text(encoding="utf-8"))
    fonted = {rep_id: rep for rep_id, rep in representations.items() if "font" in rep}
    assert "klingon_piqad" in fonted

    for rep_id, rep in fonted.items():
        assert rep["format"] == "text", f"{rep_id} has a font but is not format text"
        font_path = STIMULI / "fonts" / rep["font"]
        assert font_path.is_file(), f"{rep_id}: missing font {font_path}"
        license_path = STIMULI / "fonts" / f"{font_path.stem}-LICENSE.txt"
        assert license_path.is_file(), f"{rep_id}: missing license file {license_path}"

        font = ImageFont.truetype(str(font_path), 44, layout_engine=ImageFont.Layout.BASIC)
        notdef = _ink(font, "͸")
        for inj_id, rendition in rep["injections"].items():
            for ch in "".join(rendition["content"]):
                if ch.isspace():
                    continue
                assert _ink(font, ch) != notdef, f"{rep_id}.{inj_id}: U+{ord(ch):04X} not in {rep['font']}"


def test_non_latin_scripts_are_real_text():
    """pIqaD is drawn from a font, not a stand-in image (issue #15)."""
    representations = json.loads((SRC / "representations.json").read_text(encoding="utf-8"))
    piqad = "".join(representations["klingon_piqad"]["injections"]["buy_bear"]["content"])
    assert all(c.isspace() or 0xF8D0 <= ord(c) <= 0xF8FF for c in piqad)
def test_baseline_differs_from_injected_only_inside_the_injection_box(tmp_path):
    """Outside the injection box's interior, a baseline image equals every injected image
    of the same context pixel for pixel; inside, it is the empty box (fill + corner notches).
    """
    import importlib.util
    from PIL import Image, ImageChops

    spec = importlib.util.spec_from_file_location("stimuli_generate", STIMULI / "generate.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    contexts = gen.load_json(SRC / "context.json")
    representations = gen.load_json(SRC / "representations.json")
    # Interior of the box, inside its 2px border.
    interior = (42, gen.INJECTION_BOX_TOP + 2, gen.WIDTH - 41, gen.INJECTION_BOX_BOTTOM - 1)

    def render(name, context_id, rep, rendition):
        path = tmp_path / f"{name}.png"
        gen.render_stimulus_image(path, context_id, contexts[context_id], rep, rendition)
        return Image.open(path).convert("RGB")

    for context_id in contexts:
        base = render(f"{context_id}.none", context_id, representations["none"], None)
        inside = base.crop(interior)
        assert len(inside.getcolors()) == 2, "baseline box holds more than its fill and notches"
        for rep_id, rep in representations.items():
            if rep["format"] == "none":
                continue
            img = render(f"{context_id}.{rep_id}", context_id, rep, rep["injections"]["buy_bear"])
            diff = ImageChops.difference(base, img)
            assert diff.getbbox() is not None, f"{context_id}.{rep_id} draws nothing"
            masked = diff.copy()
            masked.paste((0, 0, 0), interior)
            assert masked.getbbox() is None, f"{context_id}.{rep_id} differs from the baseline outside the box"
