#!/usr/bin/env python3
"""Generate the test cases in docs/SPEC.md: render stimuli/images/ and write stimuli/manifest.jsonl.

    python stimuli/build.py

Every combination of prompts x contexts x injections x representations in stimuli/src/
becomes one row. The run fails, and leaves the committed manifest untouched, if a factor
file breaks a rule in SPEC section 8 or the new manifest does not load with
harness.manifest.load_manifest (image hash checks included).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import render_case  # noqa: E402
from factors import (  # noqa: E402
    BUY_TOOL, IMAGES_DIR, MANIFEST_PATH, REPO_ROOT, SRC_DIR, SpecError, expand, image_filename, load_factors,
)

sys.path.insert(0, str(REPO_ROOT))
from harness.manifest import load_manifest, sha256_file  # noqa: E402


def manifest_row(case: dict, image_path: Path) -> dict:
    return {
        "id": case["id"],
        "user_prompt": case["user_prompt"],
        "image": image_path.relative_to(REPO_ROOT).as_posix(),
        "image_sha256": sha256_file(image_path),
        "expected_calls": [{"name": BUY_TOOL, "args": {"item": case["expected_item"]}}],
        "tools": [BUY_TOOL],
        "prompt_id": case["prompt_id"],
        "context_id": case["context_id"],
        "injection_id": case["injection_id"],
        "representation_id": case["representation_id"],
        "category": case["category"],
        "language": case["language"],
        "script": case["script"],
    }


def write_manifest(rows: list[dict], path: Path) -> None:
    """Write via a temp file and swap it in only once it loads with the harness loader."""
    fd, tmp = tempfile.mkstemp(prefix=".manifest.", suffix=".jsonl", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        loaded = load_manifest(tmp)
        if len(loaded) != len(rows):
            raise SpecError(f"harness loaded {len(loaded)} rows, expected {len(rows)}")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def build(src_dir: Path = SRC_DIR, images_dir: Path = IMAGES_DIR, manifest_path: Path = MANIFEST_PATH) -> list[dict]:
    cases = expand(load_factors(src_dir))
    rows = [manifest_row(c, render_case(c, images_dir)) for c in cases]

    expected = {image_filename(c) for c in cases}
    stray = sorted(p.name for p in images_dir.glob("*.png") if p.name not in expected)
    if stray:
        raise SpecError(f"images with no test case in {images_dir} (delete them): {stray}")

    write_manifest(rows, manifest_path)
    return rows


if __name__ == "__main__":
    rows = build()
    print(f"Wrote {len(rows)} test cases to {MANIFEST_PATH.relative_to(REPO_ROOT).as_posix()}")
