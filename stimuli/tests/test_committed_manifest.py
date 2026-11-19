"""The committed stimuli/manifest.jsonl must reproduce from the factor files on any platform.

generate.py verifies the manifest against the images it just rendered, so on its own it
can't notice a stale manifest or a platform that renders different bytes. This test
compares against the committed file instead. CI runs it on Linux, Windows and macOS.
"""

import importlib.util
import re
import shutil
from pathlib import Path

import PIL
import pytest

ROOT = Path(__file__).resolve().parents[2]
STIMULI = ROOT / "stimuli"
MANIFEST_JSONL = STIMULI / "manifest.jsonl"

_spec = importlib.util.spec_from_file_location("stimuli_generate", STIMULI / "generate.py")
assert _spec is not None and _spec.loader is not None
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

_pin = re.search(r"^pillow==(\S+)", (STIMULI / "requirements.txt").read_text(encoding="utf-8"), re.M | re.I)
assert _pin is not None, "stimuli/requirements.txt must pin pillow=="
PINNED_PILLOW = _pin.group(1)


@pytest.mark.skipif(PIL.__version__ != PINNED_PILLOW, reason=f"hashes are only stable on the pinned Pillow {PINNED_PILLOW}")
def test_build_reproduces_committed_manifest(tmp_path):
    """A fresh build reproduces the committed manifest byte for byte, hashes included."""
    out = tmp_path / "stimuli"
    shutil.copytree(STIMULI / "src", out / "src")
    gen.generate(src_dir=out / "src", stimuli_dir=out)
    assert (out / "manifest.jsonl").read_bytes() == MANIFEST_JSONL.read_bytes()
