#!/usr/bin/env python3
"""Stimulus generator (docs/SPEC.md): renders the images and writes the samples to
stimuli/manifest.jsonl, the file the harness reads.

A sample is one prompt paired with one scene (stimuli/generate_images.py), except the
contexts a prompt excludes. Its id is `<prompt>.<context>.<injection>.<representation>`.
Baseline samples (representation `none`) are marked `is_baseline`.

Section 8: if any check fails, nothing is written. Images and the manifest are built in
a staging dir under stimuli/, the staged manifest is checked with
harness.manifest.load_manifest(..., verify_hashes=True), and only then are both moved
into place.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from harness.manifest import load_manifest  # noqa: E402
from stimuli.attack_types import attack_fields  # noqa: E402
from stimuli.factors import SRC_DIR, expand_injections, load_factors, uncovered  # noqa: E402
from stimuli.files import swap_in_dir  # noqa: E402
from stimuli.generate_images import Scene, build_scenes, render_images  # noqa: E402
from stimuli.schema import Factors, Sample  # noqa: E402

STIMULI_DIR = REPO_ROOT / "stimuli"
STAGING_PREFIX = ".generate-"  # gitignored; removed after every run


def build_samples(f: Factors, scenes: list[Scene], images_rel: str) -> list[Sample]:
    """Every sample; image_sha256 is filled in after rendering."""
    injections = expand_injections(f)
    samples, seen = [], set()
    for prompt in f.prompts.values():
        for s in scenes:
            if s.context_id in prompt.exclude_contexts:
                continue
            sample_id = f"{prompt.id}.{s.context_id}.{s.injection_id}.{s.representation_id}"
            if sample_id in seen:
                raise ValueError(f"Duplicate sample id: {sample_id}")
            seen.add(sample_id)
            rep, injection = f.representations[s.representation_id], injections[s.injection_id]
            samples.append(Sample(
                id=sample_id,
                user_prompt=prompt.text,
                image=f"{images_rel}/{s.image_id}.png",
                image_sha256=None,
                expected_calls=injection.expected_calls,
                prompt_id=prompt.id,
                context_id=s.context_id,
                injection_id=s.injection_id,
                representation_id=s.representation_id,
                is_baseline=rep.is_baseline,
                category=rep.category,
                language=rep.language,
                script=rep.script,
                **attack_fields(prompt.expected_tool, f.contexts[s.context_id].item, injection.command.expected_tool),
            ))
    return samples


def generate(src_dir: Path = SRC_DIR, stimuli_dir: Path = STIMULI_DIR) -> list[Sample]:
    print(f"Loading factor files from {src_dir}...")
    f = load_factors(src_dir)
    for rep_id, missing in uncovered(f).items():
        print(f"WARNING: representation {rep_id} has no rendition of {len(missing)} injection(s), "
              f"so no samples for them: {', '.join(missing)}", file=sys.stderr)

    # Image paths in the manifest are relative to stimuli_dir's parent (the repo root).
    images_rel = f"{stimuli_dir.name}/images"
    scenes = build_scenes(f)
    samples = build_samples(f, scenes, images_rel)

    # Render and write under `staging`, which mirrors the layout of stimuli_dir's
    # parent, so the staged manifest's paths resolve to the staged images. Nothing
    # outside it changes until every check has passed.
    staging = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=stimuli_dir))
    try:
        hashes = render_images(f, scenes, staging / images_rel)
        for s in samples:
            s.image_sha256 = hashes[Path(s.image).stem]
        print(f"Rendered {len(hashes)} images for {len(samples)} samples")

        staged_manifest = staging / stimuli_dir.name / "manifest.jsonl"
        with open(staged_manifest, "w", encoding="utf-8", newline="\n") as out:
            for s in samples:
                out.write(json.dumps(asdict(s)) + "\n")

        print("Verifying manifest with harness.manifest.load_manifest(..., verify_hashes=True)...")
        loaded = load_manifest(staged_manifest, image_root=staging, verify_hashes=True)
        if len(loaded) != len(samples):
            raise ValueError(f"Loaded {len(loaded)} rows, expected {len(samples)}")

        swap_in_dir(staging / images_rel, stimuli_dir / "images", staging)
        os.replace(staged_manifest, stimuli_dir / "manifest.jsonl")
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    print(f"SUCCESS: wrote and verified {len(samples)} samples in {stimuli_dir / 'manifest.jsonl'}")
    return samples


if __name__ == "__main__":
    generate()
