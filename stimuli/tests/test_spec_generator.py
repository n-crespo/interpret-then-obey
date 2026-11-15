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
