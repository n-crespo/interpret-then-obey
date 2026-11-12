"""Load the four factor files in stimuli/src/ and expand them into test cases (docs/SPEC.md).

The renderer and the manifest builder both go through here, so the text drawn in an
image and the row recorded in the manifest come from the same place.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

STIMULI_DIR = Path(__file__).resolve().parent  # stimuli/
REPO_ROOT = STIMULI_DIR.parent
SRC_DIR = STIMULI_DIR / "src"
IMAGES_DIR = STIMULI_DIR / "images"
FONTS_DIR = STIMULI_DIR / "fonts"
MANIFEST_PATH = STIMULI_DIR / "manifest.jsonl"

# Harness name of the open-ended buy tool. Not settled yet (SPEC section 9); this is the
# placeholder name the spec uses in its examples.
BUY_TOOL = "buy"

FACTOR_FILES = ("prompts", "context", "injections", "representations")
FORMATS = ("text", "image")
CATEGORIES = ("natural", "constructed", "symbols")
SCRIPTS = ("latin", "non_latin")


class SpecError(ValueError):
    """A factor file breaks a rule in SPEC section 8."""


def _load(name: str, src_dir: Path) -> dict:
    with open(src_dir / f"{name}.json", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise SpecError(f"{name}.json must be an object keyed by id")
    return data


def load_factors(src_dir: Path = SRC_DIR) -> dict[str, dict]:
    """Return {'prompts': ..., 'context': ..., 'injections': ..., 'representations': ...}, validated."""
    factors = {name: _load(name, src_dir) for name in FACTOR_FILES}
    validate(factors, stimuli_dir=src_dir.parent)
    return factors


def validate(factors: dict[str, dict], stimuli_dir: Path = STIMULI_DIR) -> None:
    """Raise SpecError on the first broken rule from SPEC sections 3-6 and 8."""
    prompts = factors["prompts"]
    injections, reps = factors["injections"], factors["representations"]

    for name, data in factors.items():
        if not data:
            raise SpecError(f"{name}.json defines nothing")
        for key in data:
            if "." in key:
                raise SpecError(f"{name}.json: id {key!r} must not contain '.' (it separates factors in row ids)")

    for pid, p in prompts.items():
        if not isinstance(p.get("text"), str) or not p["text"].strip():
            raise SpecError(f"prompts.json: {pid!r} needs a non-empty 'text'")

    for iid, inj in injections.items():
        for field in ("meaning", "expected_item"):
            if not isinstance(inj.get(field), str) or not inj[field].strip():
                raise SpecError(f"injections.json: {iid!r} needs a non-empty {field!r}")

    if next(iter(reps)) != "english":
        raise SpecError("representations.json: 'english' must be the first entry")

    for rid, rep in reps.items():
        where = f"representations.json: {rid!r}"
        fmt = rep.get("format")
        if fmt not in FORMATS:
            raise SpecError(f"{where}: format must be one of {FORMATS}, got {fmt!r}")
        if rep.get("category") not in CATEGORIES:
            raise SpecError(f"{where}: category must be one of {CATEGORIES}, got {rep.get('category')!r}")
        if fmt == "text":
            if not rep.get("language"):
                raise SpecError(f"{where}: text representations need a 'language'")
            if rep.get("script") not in SCRIPTS:
                raise SpecError(f"{where}: script must be one of {SCRIPTS}, got {rep.get('script')!r}")
        if rep.get("font") and not (stimuli_dir / "fonts" / rep["font"]).exists():
            raise SpecError(f"{where}: font {rep['font']!r} not found in stimuli/fonts/")

        renditions = rep.get("injections") or {}
        unknown = sorted(set(renditions) - set(injections))
        if unknown:
            raise SpecError(f"{where}: renditions for unknown injection id(s) {unknown}")
        missing = sorted(set(injections) - set(renditions))
        if missing:
            raise SpecError(f"{where}: no rendition for injection id(s) {missing}")

        for iid, rend in renditions.items():
            content = rend.get("content")
            if not isinstance(content, list) or not content or not all(isinstance(c, str) and c for c in content):
                raise SpecError(f"{where}.{iid}: content must be a non-empty list of strings")
            if fmt == "image":
                absent = [c for c in content if not (stimuli_dir / c).exists()]
                if absent:
                    raise SpecError(f"{where}.{iid}: image(s) not found under stimuli/: {absent}")


def case_id(prompt_id: str, context_id: str, injection_id: str, representation_id: str) -> str:
    return f"{prompt_id}.{context_id}.{injection_id}.{representation_id}"


def expand(factors: dict[str, dict]) -> list[dict]:
    """Every combination prompts x contexts x injections x representations, in file order.

    Each case holds the four ids plus what the renderer and manifest builder need.
    """
    reps = factors["representations"]
    cases = []
    for pid, cid, iid, rid in itertools.product(
        factors["prompts"], factors["context"], factors["injections"], reps
    ):
        rep = reps[rid]
        cases.append({
            "id": case_id(pid, cid, iid, rid),
            "prompt_id": pid,
            "context_id": cid,
            "injection_id": iid,
            "representation_id": rid,
            "user_prompt": factors["prompts"][pid]["text"],
            "context": factors["context"][cid],
            "expected_item": factors["injections"][iid]["expected_item"],
            "format": rep["format"],
            "font": rep.get("font"),
            "content": rep["injections"][iid]["content"],
            "category": rep["category"],
            "language": rep.get("language"),
            "script": rep.get("script"),
        })
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise SpecError(f"duplicate test case ids: {dupes}")
    return cases


def image_filename(case: dict) -> str:
    return f"{case['id']}.png"
