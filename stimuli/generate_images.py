"""Stimulus images: one per context × injection × representation (docs/SPEC.md section 7).

The prompt is not drawn, so one image serves every prompt it is paired with. Left out:
- an injection whose object is the context's own item (the injected and the scene's
  object would be the same thing);
- an injection the representation has no rendition of (`uncovered` in stimuli/factors.py).
The baseline draws no injection, so it has one image per context, shared by the
baseline scenes of every injection.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from stimuli.factors import expand_injections, rendition_of
from stimuli.files import sha256_file
from stimuli.render import render_stimulus_image
from stimuli.schema import Factors, Rendition


@dataclass(frozen=True)
class Scene:
    """What one image shows: a context and an injection in one representation."""
    context_id: str
    injection_id: str
    representation_id: str
    rendition: Rendition | None  # None for the baseline

    @property
    def image_id(self) -> str:
        if self.rendition is None:
            return f"{self.context_id}.{self.representation_id}"
        return f"{self.context_id}.{self.injection_id}.{self.representation_id}"


def build_scenes(f: Factors) -> list[Scene]:
    """Every scene a sample can show, in context, injection, representation order."""
    scenes = []
    for context in f.contexts.values():
        for injection in expand_injections(f).values():
            if injection.object.id == context.item:
                continue
            for rep in f.representations.values():
                rendition = None
                if not rep.is_baseline:
                    rendition = rendition_of(rep, injection)
                    if rendition is None:
                        continue
                scenes.append(Scene(context.id, injection.id, rep.id, rendition))
    return scenes


def render_images(f: Factors, scenes: list[Scene], images_dir: Path) -> dict[str, str]:
    """Render each scene's image once into images_dir/<image_id>.png. Returns image id -> sha256."""
    hashes: dict[str, str] = {}
    for s in scenes:
        if s.image_id in hashes:
            continue
        path = images_dir / f"{s.image_id}.png"
        render_stimulus_image(path, f.contexts[s.context_id], f.representations[s.representation_id], s.rendition)
        hashes[s.image_id] = sha256_file(path)
    return hashes
