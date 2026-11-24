"""The committed manifest is the full factorial expansion of the factor files, and the
hand-written renditions are drawable and say nothing in English where they must not."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STIMULI = ROOT / "stimuli"
MANIFEST_JSONL = STIMULI / "manifest.jsonl"

sys.path.insert(0, str(ROOT))
from harness.tools import TOOLS  # noqa: E402
from stimuli.load import expand_injections, load_factors, rendition_of  # noqa: E402
from stimuli.scenes import build_scenes  # noqa: E402

FACTORS = load_factors()
INJECTIONS = expand_injections(FACTORS)


def renditions(rep):
    """injection id -> the rendition of it in `rep`, for the injections it has one of."""
    out = {i: rendition_of(rep, inj) for i, inj in INJECTIONS.items()}
    return {i: r for i, r in out.items() if r is not None}


def test_committed_manifest_pairs_every_prompt_with_every_scene():
    # Reads the committed manifest directly: stimuli/images/ is gitignored, so this
    # must pass on a fresh clone. Hashes are checked against a fresh build in
    # test_committed_manifest.py.
    rows = [json.loads(line) for line in MANIFEST_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))

    expected = {(p.id, s.context_id, s.injection_id, s.representation_id)
                for p in FACTORS.prompts.values() for s in build_scenes(FACTORS)
                if p.pairs_with(s.context_id)}
    assert {(r["prompt_id"], r["context_id"], r["injection_id"], r["representation_id"]) for r in rows} == expected

    for r in rows:
        assert r["id"] == f"{r['prompt_id']}.{r['context_id']}.{r['injection_id']}.{r['representation_id']}"
        assert FACTORS.prompts[r["prompt_id"]].pairs_with(r["context_id"])
        # The injected object is never the scene's own item.
        assert INJECTIONS[r["injection_id"]].object.id != FACTORS.contexts[r["context_id"]].item
        assert r["expected_calls"] == INJECTIONS[r["injection_id"]].expected_calls
        assert all(c["name"] in TOOLS for c in r["expected_calls"])
        assert r["is_baseline"] == (r["representation_id"] == "none")

    # One image per scene, shared by every prompt; the baseline has one per context.
    by_image: dict = {}
    for r in rows:
        by_image.setdefault(r["image"], set()).add(r["image_sha256"])
    assert all(len(h) == 1 for h in by_image.values())
    baseline_images = {r["image"] for r in rows if r["is_baseline"]}
    assert len(baseline_images) == len(FACTORS.contexts)
    assert not {r["image_sha256"] for r in rows if r["is_baseline"]} & {r["image_sha256"] for r in rows if not r["is_baseline"]}


def test_no_english_translations_in_conlang_content():
    for rep in FACTORS.representations.values():
        if rep.category == "constructed" and rep.format == "text":
            for injection_id, rendition in renditions(rep).items():
                obj = INJECTIONS[injection_id].object.id
                joined = " ".join(rendition.content).lower()
                assert f"buy a {obj}" not in joined
                assert not re.search(rf"\b{obj}s?\b", joined, re.IGNORECASE), (
                    f"{rep.id} rendition contains the English word {obj!r}: {rendition.content}"
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

    fonted = [rep for rep in FACTORS.representations.values() if rep.font is not None]
    assert any(rep.id == "klingon_piqad" for rep in fonted)

    for rep in fonted:
        assert rep.format == "text", f"{rep.id} has a font but is not format text"
        font_path = STIMULI / "assets" / "fonts" / rep.font
        license_path = STIMULI / "assets" / "fonts" / f"{font_path.stem}-LICENSE.txt"
        assert license_path.is_file(), f"{rep.id}: missing license file {license_path}"

        font = ImageFont.truetype(str(font_path), 44, layout_engine=ImageFont.Layout.BASIC)
        notdef = _ink(font, "͸")
        for injection_id, rendition in renditions(rep).items():
            for ch in "".join(rendition.content):
                if not ch.isspace():
                    assert _ink(font, ch) != notdef, f"{rep.id}.{injection_id}: U+{ord(ch):04X} not in {rep.font}"
