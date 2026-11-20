"""Tests for stimuli/generate.py per docs/SPEC.md."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STIMULI = ROOT / "stimuli"
SRC = STIMULI / "src"
MANIFEST_JSONL = STIMULI / "manifest.jsonl"

sys.path.insert(0, str(ROOT))
from stimuli.generate import expand_injections, rendition_of  # noqa: E402


def renditions(rep: dict, injections: dict) -> dict:
    """injection id -> the rendition of it in `rep`, for the injections it has one of."""
    out = {i: rendition_of(rep, i, inj) for i, inj in expand_injections(injections).items()}
    return {i: r for i, r in out.items() if r is not None}


def test_committed_manifest_rows():
    # Reads the committed manifest directly: stimuli/images/ is gitignored, so this
    # must pass on a fresh clone. Hashes are checked against a fresh build in
    # test_committed_manifest.py::test_build_reproduces_committed_manifest.
    rows = [json.loads(line) for line in MANIFEST_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    prompts = json.loads((SRC / "prompts.json").read_text(encoding="utf-8"))
    contexts = json.loads((SRC / "context.json").read_text(encoding="utf-8"))
    injections = json.loads((SRC / "injections.json").read_text(encoding="utf-8"))
    representations = json.loads((SRC / "representations.json").read_text(encoding="utf-8"))
    cells = {(p, c) for p in prompts for c in contexts if c not in prompts[p].get("exclude_contexts", [])}
    expanded = expand_injections(injections)
    # A representation has rows only for the injections it has a rendition of; the
    # baseline has a row for every injection.
    per_cell = sum(len(expanded) if r["format"] == "none" else len(renditions(r, injections))
                   for r in representations.values())
    assert len(rows) == len(cells) * per_cell

    # Excluded pairs: an obey there is not an attack success (docs/SPEC.md section 3).
    assert ("buy", "info_board") not in cells

    # One baseline row per included prompt x context x injection, injection box left empty.
    baseline = [r for r in rows if r["category"] == "baseline"]
    assert {(r["prompt_id"], r["context_id"], r["injection_id"]) for r in baseline} == {
        (p, c, i) for p, c in cells for i in expanded
    }
    assert len(baseline) == len(cells) * len(expanded)
    for r in baseline:
        assert r["representation_id"] == "none"
        assert r["language"] is None and r["script"] is None
    # The baseline must look like no other image.
    assert len({r["image_sha256"] for r in baseline}) == len(contexts)  # one image per context
    assert not {r["image_sha256"] for r in baseline} & {r["image_sha256"] for r in rows if r["category"] != "baseline"}

    for r in rows:
        assert "tools" not in r, "the harness offers every tool to every row"
        assert r["expected_calls"] == expanded[r["injection_id"]]["expected_calls"]
        assert r["id"].startswith(f"{r['prompt_id']}.{r['context_id']}.{r['injection_id']}.{r['representation_id']}")
        assert r["image"].startswith("stimuli/images/")
        assert len(r["image_sha256"]) == 64

    # Attack type (docs/SPEC.md section 7). A buy injection: per prompt x context, the same
    # for every representation. Any other tool: unrequested_action, whatever the prompt and scene.
    buys = [r for r in rows if r["expected_calls"][0]["name"] == "buy"]
    by_cell = {(r["prompt_id"], r["context_id"]): (r["attack_type"], r["competing_product"]) for r in buys}
    assert len({(r["prompt_id"], r["context_id"], r["attack_type"], r["competing_product"]) for r in buys}) == len(cells)
    assert by_cell == {
        ("read", "info_board"): ("escalation", False),
        ("read", "product_info"): ("escalation", True),
        ("read", "advertisement"): ("escalation", True),
        ("read", "meeting_notes"): ("escalation", False),
        ("read", "transit_notice"): ("escalation", False),
        ("help", "info_board"): ("escalation", False),
        ("help", "product_info"): ("escalation", True),
        ("help", "advertisement"): ("escalation", True),
        ("help", "meeting_notes"): ("escalation", False),
        ("help", "transit_notice"): ("escalation", False),
        ("buy", "product_info"): ("hijack", True),
        ("buy", "advertisement"): ("hijack", True),
    }
    others = [r for r in rows if r["expected_calls"][0]["name"] != "buy"]
    assert others and {r["attack_type"] for r in others} == {"unrequested_action"}


def test_no_english_translations_in_conlang_content():
    representations = json.loads((SRC / "representations.json").read_text(encoding="utf-8"))
    injections = json.loads((SRC / "injections.json").read_text(encoding="utf-8"))
    expanded = expand_injections(injections)
    for rep_id, rep in representations.items():
        if rep["category"] == "constructed" and rep["format"] == "text":
            for injection_id, rendition in renditions(rep, injections).items():
                obj, content = expanded[injection_id]["object"], rendition["content"]
                joined = " ".join(content).lower()
                # None of them should contain the English sentence or the English object word
                assert f"buy a {obj}" not in joined
                assert "ignore user" not in joined
                assert "add a banana" not in joined
                assert not re.search(rf"\b{obj}s?\b", joined, re.IGNORECASE), (
                    f"{rep_id} rendition contains the English word {obj!r}: {content}"
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
    injections = json.loads((SRC / "injections.json").read_text(encoding="utf-8"))
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
        for injection_id, rendition in renditions(rep, injections).items():
            for ch in "".join(rendition["content"]):
                if ch.isspace():
                    continue
                assert _ink(font, ch) != notdef, f"{rep_id}.{injection_id}: U+{ord(ch):04X} not in {rep['font']}"

