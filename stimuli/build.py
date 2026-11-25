"""Stimulus generator: renders the images and writes the samples to
stimuli/manifest.jsonl, the file the harness reads.

A sample is one prompt paired with one scene (stimuli/scenes.py) whose context
the prompt pairs with (Prompt.contexts). Its id is `<prompt>.<context>.<injection>.<representation>`.
Baseline samples (representation `none`) are marked `is_baseline`.

If any check fails, nothing is written. Images and the manifest are built in
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

from harness.manifest import load_manifest
from stimuli.files import swap_in_dir
from stimuli.load import expand_injections, load_factors, uncovered
from stimuli.paths import FACTORS_DIR, STIMULI_DIR
from stimuli.scenes import Scene, build_scenes, render_images
from stimuli.schema import Context, Factors, Sample

STAGING_PREFIX = ".build-"  # gitignored; removed after every run


def context_object(context: Context, f: Factors) -> dict:
    """What the scene shows, as {argument: accepted names}: its item, if any, and under
    "subject" its header and accepted_items (models often name a scene by its header)."""
    subject = {"subject": [context.header, *context.accepted_items]}
    if context.item is None:
        return subject
    obj = f.target_objects[context.item]
    return {obj.type: list(obj.accepted_items), **subject}


def build_samples(f: Factors, scenes: list[Scene], images_rel: str) -> list[Sample]:
    """Every sample; image_sha256 is filled in after rendering."""
    injections = expand_injections(f)
    samples, seen = [], set()
    for prompt in (p for p in f.prompts.values() if p.enabled):
        for s in scenes:
            if not prompt.pairs_with(s.context_id):
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
                prompt_expected_tool=prompt.expected_tool,
                context_object=context_object(f.contexts[s.context_id], f),
                prompt_id=prompt.id,
                context_id=s.context_id,
                injection_id=s.injection_id,
                representation_id=s.representation_id,
                is_baseline=rep.is_baseline,
                category=rep.category,
                language=rep.language,
                script=rep.script,
            ))
    return samples


def generate(factors_dir: Path = FACTORS_DIR, stimuli_dir: Path = STIMULI_DIR) -> list[Sample]:
    print(f"Loading factor files from {factors_dir}...")
    f = load_factors(factors_dir)
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
