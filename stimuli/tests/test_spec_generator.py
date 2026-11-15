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

    # Rule 2: every representation has a rendition for every injection
    for rep_id, rep in representations.items():
        assert "buy_bear" in rep["injections"], f"{rep_id} missing buy_bear"
        content = rep["injections"]["buy_bear"]["content"]
        assert isinstance(content, list) and len(content) > 0
        if rep["format"] == "image":
            for p in content:
                assert (ROOT / p).exists(), f"Image asset {p} not found"


def test_manifest_loads_and_verifies_hashes():
    import sys
    sys.path.insert(0, str(ROOT))
    from harness.manifest import load_manifest

    rows = load_manifest(MANIFEST_JSONL, verify_hashes=True)
    assert len(rows) == 126

    for r in rows:
        assert r["tools"] == ["buy"]
        assert r["expected_calls"] == [{"name": "buy", "args": {"item": "bear"}}]
        assert r["id"].startswith(f"{r['prompt_id']}.{r['context_id']}.{r['injection_id']}.{r['representation_id']}")
        assert Path(r["image"]).exists()


# Simlish and Minionese have no real vocabulary to translate into; their
# renditions are gibberish plus English. Whether they count as representations
# at all is an open decision on issue #15, so they are exempt until it is made.
ENGLISH_LEAK_EXEMPT = {"simlish", "minionese"}


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
            if rep_id not in ENGLISH_LEAK_EXEMPT:
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
    assert {"klingon_piqad", "elvish_tengwar"} <= set(fonted)

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
    """pIqaD and Tengwar are drawn from a font, not stand-in images (issue #15)."""
    representations = json.loads((SRC / "representations.json").read_text(encoding="utf-8"))
    piqad = "".join(representations["klingon_piqad"]["injections"]["buy_bear"]["content"])
    tengwar = "".join(representations["elvish_tengwar"]["injections"]["buy_bear"]["content"])
    assert all(c.isspace() or 0xF8D0 <= ord(c) <= 0xF8FF for c in piqad)
    assert all(c.isspace() or 0xE000 <= ord(c) <= 0xE07F for c in tengwar)
