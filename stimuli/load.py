"""The factor files in stimuli/factors/: loading, validating, and expanding
injections into their renditions.

Injections are injection commands × target objects: each command takes the objects of
one type (`object_type`, also the argument of its tool that the object fills), giving one
injection per pair, id `<command>_<object>`. A representation renders an injection by
filling `{object}` (str.format syntax) in its rendition of the command, or gives a whole
rendition of the injection (`injections`).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from stimuli.files import load_json
from stimuli.paths import FACTORS_DIR, REPO_ROOT
from stimuli.schema import Factors, Injection, Rendition, Representation

def load_factors(factors_dir: Path = FACTORS_DIR) -> Factors:
    """The five factor files, validated."""
    f = Factors.model_validate({name: load_json(factors_dir / f"{name}.json") for name in Factors.model_fields})
    check_references(f)
    return f


def check_references(f: Factors) -> None:
    """The rules that span factor files, which the models in stimuli/schema.py
    can't check one file at a time. Raises one ValueError listing every
    broken one."""
    errors: list[str] = []

    def require_known(what: str, refs: dict[str, Iterable[str]], known: Iterable[str]) -> None:
        known = set(known)
        for where, names in refs.items():
            if bad := sorted(set(names) - known):
                errors.append(f"{where}: unknown {what} {bad}")

    objects, reps = f.target_objects, f.representations.values()
    types = {o.type for o in objects.values()}
    injections = expand_injections(f, include_excluded=True)
    # A command takes the objects of one target object type.
    require_known("target object type", {f"injection_commands.{c.id}.object_type": [c.object_type] for c in f.injection_commands.values()}, types)
    # A prompt's object is a target object.
    require_known("target object", {f"prompts.{p.id}.object": [p.object] for p in f.prompts.values() if p.object is not None}, objects)
    # A prompt names contexts that exist.
    require_known("context", {f"prompts.{p.id}.contexts": p.contexts for p in f.prompts.values()}, f.contexts)
    # A context shows a target object, or nothing.
    require_known("target object", {f"contexts.{c.id}.item": [c.item] for c in f.contexts.values() if c.item is not None}, objects)
    # A representation renders commands, injections and objects that exist.
    require_known("injection command", {f"representations.{r.id}.injection_commands": r.injection_commands for r in reps}, f.injection_commands)
    require_known("injection", {f"representations.{r.id}.injections": r.injections for r in reps}, injections)
    require_known("target object", {f"representations.{r.id}.target_objects": r.target_objects for r in reps}, objects)
    # english comes first, so the plain meaning is readable at the top, and renders every injection.
    if next(iter(f.representations)) != "english":
        errors.append("representations: 'english' must be the first representation")
    elif missing := [i.id for i in injections.values() if rendition_of(f.representations["english"], i) is None]:
        errors.append(f"representations.english: no rendition of {missing}")
    if errors:
        raise ValueError("The factor files are invalid:\n  " + "\n  ".join(errors))


def expand_injections(f: Factors, include_excluded: bool = False) -> dict[str, Injection]:
    """Every command × target object of its type, keyed by injection id `<command>_<object>`.
    Target objects marked exclude_from_injections make none unless `include_excluded`."""
    out = {}
    for command in f.injection_commands.values():
        for obj in f.target_objects.values():
            if obj.type == command.object_type and (include_excluded or not obj.exclude_from_injections):
                inj = Injection(command, obj)
                out[inj.id] = inj
    return out


def rendition_of(rep: Representation, injection: Injection) -> Rendition | None:
    """The rendition of one injection in `rep`, or None when it has none.

    A whole rendition in `injections` wins. Otherwise the command's rendition has
    `{object}` filled in: by text representations with their own word for the object
    (`target_objects`), by image representations with the object id, which names the
    asset's folder. An image representation with no asset drawn for the object has no
    rendition of it.
    """
    if injection.id in rep.injections:
        return rep.injections[injection.id]
    rendition = rep.injection_commands.get(injection.command.id)
    word = rep.target_objects.get(injection.object.id) if rep.format == "text" else injection.object.id
    if rendition is None or word is None:
        return None
    filled = rendition.filled(word)
    if rep.format == "image" and not all((REPO_ROOT / p).is_file() for p in filled.content):
        return None
    return filled


def uncovered(f: Factors) -> dict[str, list[str]]:
    """representation id -> the injection ids it has no rendition of (the baseline needs none)."""
    out = {}
    for rep in f.representations.values():
        if rep.is_baseline:
            continue
        missing = [i.id for i in expand_injections(f).values() if rendition_of(rep, i) is None]
        if missing:
            out[rep.id] = missing
    return out
