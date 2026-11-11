"""Manifest-loader error messages; no inspect_ai needed.
Run from repo root:  python -m pytest harness/tests/test_manifest.py -q"""

import json

import pytest

from harness.manifest import RENDER_CMD, load_manifest, sha256_file


def _write_manifest(tmp_path, image, sha=None):
    row = {"id": "r1", "user_prompt": "hi", "image": image}
    if sha:
        row["image_sha256"] = sha
    path = tmp_path / "manifest.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return path


def test_missing_generated_image_names_render_command(tmp_path):
    path = _write_manifest(tmp_path, "stimuli/images/fx-nope.png")
    with pytest.raises(FileNotFoundError) as e:
        load_manifest(path, image_root=tmp_path)
    assert "generated" in str(e.value) and RENDER_CMD in str(e.value)


def test_missing_other_image_has_no_render_hint(tmp_path):
    path = _write_manifest(tmp_path, "fixtures/nope.png")
    with pytest.raises(FileNotFoundError) as e:
        load_manifest(path, image_root=tmp_path)
    assert RENDER_CMD not in str(e.value)


def test_hash_mismatch_on_generated_image_mentions_pinned_pillow(tmp_path):
    img = tmp_path / "stimuli" / "images" / "fx-a.png"
    img.parent.mkdir(parents=True)
    img.write_bytes(b"not the rendered png")
    path = _write_manifest(tmp_path, "stimuli/images/fx-a.png", sha="0" * 64)
    with pytest.raises(ValueError) as e:
        load_manifest(path, image_root=tmp_path)
    assert RENDER_CMD in str(e.value) and "Pillow" in str(e.value)
    # and a matching hash loads fine
    path = _write_manifest(tmp_path, "stimuli/images/fx-a.png", sha=sha256_file(img))
    assert load_manifest(path, image_root=tmp_path)[0]["image"] == str(img.resolve())
