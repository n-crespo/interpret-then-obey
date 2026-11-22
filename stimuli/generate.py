#!/usr/bin/env python3
"""
Stimulus generator for the interpret-then-obey benchmark per docs/SPEC.md.

Combines the 4 factors:
  prompts × contexts × injections × representations

The factor files are loaded and validated by stimuli/factors.py. The `none`
representation (format "none", category "baseline") is the no-injection baseline:
its images have the injection box drawn but empty.

Deterministically renders images to stimuli/images/<id>.png and writes
the harness-loadable manifest to stimuli/manifest.jsonl (the only file it
writes, per docs/SPEC.md section 7).

Section 8: if any check fails, nothing is written. Images and the manifest
are built in a staging dir under stimuli/, the staged manifest is checked
with harness.manifest.load_manifest(..., verify_hashes=True), and only then
are both moved into place.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from harness.manifest import load_manifest  # noqa: E402
from stimuli.attack_types import attack_fields  # noqa: E402
from stimuli.factors import SRC_DIR, expand_injections, load_factors, rendition_of, uncovered  # noqa: E402
from stimuli.files import sha256_file, swap_in_dir  # noqa: E402
from stimuli.render import render_stimulus_image  # noqa: E402
from stimuli.schema import Factors  # noqa: E402

STIMULI_DIR = REPO_ROOT / "stimuli"
STAGING_PREFIX = ".generate-"  # gitignored; removed after every run


def build_rows(f: Factors, images_rel: str) -> list[tuple[dict, tuple]]:
    """Every row in memory (image_sha256 filled in after rendering), each with its render arguments."""
    out = []
    seen_ids = set()
    for prompt in f.prompts.values():
        for context in f.contexts.values():
            if context.id in prompt.exclude_contexts:
                continue
            for injection in expand_injections(f).values():
                # The injected object is never the scene's own item.
                if injection.object.id == context.item:
                    continue
                for rep in f.representations.values():
                    # A representation with no rendition of this injection has no row for it
                    # (`uncovered`); the baseline has one for every injection.
                    rendition = None
                    if not rep.is_baseline:
                        rendition = rendition_of(rep, injection)
                        if rendition is None:
                            continue
                    sample_id = f"{prompt.id}.{context.id}.{injection.id}.{rep.id}"
                    if sample_id in seen_ids:
                        raise ValueError(f"Duplicate sample id: {sample_id}")
                    seen_ids.add(sample_id)

                    row = {
                        "id": sample_id,
                        "user_prompt": prompt.text,
                        "image": f"{images_rel}/{sample_id}.png",
                        "image_sha256": None,
                        "expected_calls": injection.expected_calls,
                        "prompt_id": prompt.id,
                        "context_id": context.id,
                        "injection_id": injection.id,
                        "representation_id": rep.id,
                        "category": rep.category,
                        "language": rep.language,
                        "script": rep.script,
                        **attack_fields(prompt.expected_tool, context.item, injection.command.expected_tool),
                    }
                    out.append((row, (context, rep, rendition)))
    return out


def generate(src_dir: Path = SRC_DIR, stimuli_dir: Path = STIMULI_DIR) -> list[dict]:
    print(f"Loading factor files from {src_dir}...")
    f = load_factors(src_dir)
    for rep_id, missing in uncovered(f).items():
        print(f"WARNING: representation {rep_id} has no rendition of {len(missing)} injection(s), "
              f"so no rows for them: {', '.join(missing)}", file=sys.stderr)

    # Image paths in the manifest are relative to stimuli_dir's parent (the repo root).
    images_rel = f"{stimuli_dir.name}/images"
    built = build_rows(f, images_rel)
    rows = [row for row, _ in built]
    print(f"Expanded the factors into {len(rows)} test cases")

    # Render and write under `staging`, which mirrors the layout of
    # stimuli_dir's parent, so the staged manifest's paths resolve to the
    # staged images. Nothing outside it changes until every check has passed.
    staging = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=stimuli_dir))
    try:
        for row, render_args in built:
            staged_image = staging / row["image"]
            render_stimulus_image(staged_image, *render_args)
            row["image_sha256"] = sha256_file(staged_image)

        staged_manifest = staging / stimuli_dir.name / "manifest.jsonl"
        with open(staged_manifest, "w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

        print("Verifying manifest with harness.manifest.load_manifest(..., verify_hashes=True)...")
        loaded = load_manifest(staged_manifest, image_root=staging, verify_hashes=True)
        if len(loaded) != len(rows):
            raise ValueError(f"Loaded {len(loaded)} rows, expected {len(rows)}")

        swap_in_dir(staging / images_rel, stimuli_dir / "images", staging)
        os.replace(staged_manifest, stimuli_dir / "manifest.jsonl")
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    print(f"SUCCESS: wrote and verified {len(rows)} test cases in {stimuli_dir / 'manifest.jsonl'}")
    return rows


if __name__ == "__main__":
    generate()
