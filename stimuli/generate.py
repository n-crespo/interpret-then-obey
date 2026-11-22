#!/usr/bin/env python3
"""
Stimulus generator for the interpret-then-obey benchmark per docs/SPEC.md.

Combines the 4 factors:
  prompts × contexts × injections × representations

The `none` representation (format "none", category "baseline") is the
no-injection baseline: its images have the injection box drawn but empty.

Injections are commands × objects (stimuli/src/injections.json): each command
takes the objects of one group (its tool argument), and the `{object}`
placeholder (str.format syntax) in its renditions is filled with each of them,
giving one injection per pair, id `<command>_<object>`. A representation may
instead give a whole rendition of one injection (`injections`), and one that
has no rendition of an injection is left out of its rows, with a warning.

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
import string
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from harness.manifest import load_manifest  # noqa: E402
from stimuli.attack_types import attack_fields  # noqa: E402
from stimuli.files import load_json, sha256_file, swap_in_dir  # noqa: E402
from stimuli.render import FONT_SIZE_RANGE, FONTS_DIR, render_stimulus_image  # noqa: E402

STIMULI_DIR = REPO_ROOT / "stimuli"
SRC_DIR = STIMULI_DIR / "src"
STAGING_PREFIX = ".generate-"  # gitignored; removed after every run

FORMATS = ("text", "image", "none")
CATEGORIES = ("natural", "constructed", "symbols", "opaque", "obfuscated", "keyed", "baseline")


def placeholders(text: str) -> set[str]:
    """The str.format field names used in `text`."""
    return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}


def expand_injections(injections: dict) -> dict[str, dict]:
    """Every command × object of its group in injections.json, keyed by injection id
    `<command>_<object>`, with the tool call that obeys it."""
    return {
        f"{command_id}_{obj}": {
            "command_id": command_id,
            "object": obj,
            "expected_calls": [{"name": command["tool"], "args": {command["arg"]: spec["accepted"]}}],
        }
        for command_id, command in injections["commands"].items()
        for obj, spec in injections["objects"][command["arg"]].items()
    }


def rendition_of(rep: dict, injection_id: str, injection: dict) -> dict | None:
    """The rendition of one injection in `rep`, or None when it has none.

    A whole rendition in `injections` wins. Otherwise the command's rendition has
    `{object}` filled in: by text representations with their own word for the object
    (`target_objects`), by image representations with the object id, which names the asset's folder.
    """
    if injection_id in rep.get("injections", {}):
        return rep["injections"][injection_id]
    rendition = rep.get("injection_commands", {}).get(injection["command_id"])
    word = rep.get("target_objects", {}).get(injection["object"]) if rep["format"] == "text" else injection["object"]
    if rendition is None or word is None:
        return None
    return {**rendition, "content": [line.format(object=word) for line in rendition["content"]]}


def uncovered(injections: dict, representations: dict) -> dict[str, list[str]]:
    """representation id -> the injection ids it has no rendition of (the baseline needs none)."""
    expanded = expand_injections(injections)
    out = {}
    for rep_id, rep in representations.items():
        if rep["format"] == "none":
            continue
        missing = [i for i, inj in expanded.items() if rendition_of(rep, i, inj) is None]
        if missing:
            out[rep_id] = missing
    return out


def _is_item_list(x) -> bool:
    """A non-empty list of non-empty strings: the shape of every `accepted` and `accepted_items`."""
    return isinstance(x, list) and bool(x) and all(isinstance(a, str) and a.strip() for a in x)


def validate_factors(prompts: dict, contexts: dict, injections: dict, representations: dict) -> None:
    """Validate all requirements from docs/SPEC.md Section 8."""
    if not prompts:
        raise ValueError("prompts.json is empty")
    if not contexts:
        raise ValueError("contexts.json is empty")
    if set(injections) != {"commands", "objects"}:
        raise ValueError("injections.json must have exactly the keys 'commands' and 'objects'")
    commands, objects = injections["commands"], injections["objects"]
    if not commands:
        raise ValueError("injections.json: 'commands' is empty")
    # objects: argument name -> object id -> spec. Representations name objects by id
    # alone (their `objects` word lists), so ids must be unique across groups.
    if not isinstance(objects, dict) or not objects:
        raise ValueError("injections.json: 'objects' must be a non-empty object keyed by argument name")
    object_ids: list[str] = []
    for arg, group in objects.items():
        if not isinstance(group, dict) or not group:
            raise ValueError(f"injections.json: objects.{arg} must be a non-empty object keyed by object id")
        for obj, spec in group.items():
            if set(spec) != {"accepted"} or not _is_item_list(spec["accepted"]):
                raise ValueError(f"injections.json: object {obj!r} must have exactly 'accepted', a non-empty list of non-empty strings")
        object_ids += group
    duplicates = sorted({o for o in object_ids if object_ids.count(o) > 1})
    if duplicates:
        raise ValueError(f"injections.json: object id(s) {duplicates} appear in more than one group")
    for command_id, command in commands.items():
        if set(command) != {"template", "tool", "arg"}:
            raise ValueError(f"injections.json: command {command_id!r} must have exactly 'template', 'tool' and 'arg'")
        if placeholders(command["template"]) != {"object"}:
            raise ValueError(f"injections.json: command {command_id!r} 'template' must use the placeholder {{object}} and no other")
        if not isinstance(command["tool"], str) or not command["tool"]:
            raise ValueError(f"injections.json: command {command_id!r} 'tool' must be a tool name")
        if command["arg"] not in objects:
            raise ValueError(f"injections.json: command {command_id!r} 'arg' must be one of the object groups {sorted(objects)}")
    expanded = expand_injections(injections)
    if not representations:
        raise ValueError("representations.json is empty")

    # Row ids are the four factor ids joined with '.', so a '.' inside one
    # could make two combinations collide (a.b + c vs a + b.c) and would make
    # ids ambiguous to split.
    for fname, factor in (
        ("prompts.json", prompts),
        ("contexts.json", contexts),
        ("injections.json commands", commands),
        ("injections.json objects", object_ids),
        ("representations.json", representations),
    ):
        for fid in factor:
            if not isinstance(fid, str) or not fid or "." in fid:
                raise ValueError(f"{fname}: id {fid!r} must be non-empty and must not contain '.'")

    # The attack type (docs/SPEC.md section 7) is derived from these two fields.
    for prompt_id, prompt in prompts.items():
        if not isinstance(prompt.get("requests_purchase"), bool):
            raise ValueError(f"Prompt {prompt_id} must have 'requests_purchase': true or false")
        excluded = prompt.get("exclude_contexts", [])
        if not isinstance(excluded, list) or not all(isinstance(c, str) for c in excluded):
            raise ValueError(f"Prompt {prompt_id}: 'exclude_contexts' must be a list of context ids")
        unknown = sorted(set(excluded) - set(contexts))
        if unknown:
            raise ValueError(f"Prompt {prompt_id} excludes unknown context id(s) {unknown}")
    for context_id, context in contexts.items():
        if "item" not in context or not (context["item"] is None or (isinstance(context["item"], str) and context["item"])):
            raise ValueError(f"Context {context_id} must have 'item': a non-empty string or null")
        accepted = context.get("accepted_items", ...)
        if not (accepted is None or _is_item_list(accepted)):
            raise ValueError(f"Context {context_id} must have 'accepted_items': a non-empty list of non-empty strings, or null")

    rep_keys = list(representations.keys())
    if rep_keys[0] != "english":
        raise ValueError(f"docs/SPEC.md Rule 1: 'english' must be the first representation, got {rep_keys[0]!r}")

    for rep_id, rep in representations.items():
        if "format" not in rep or rep["format"] not in FORMATS:
            raise ValueError(f"Representation {rep_id} must have format 'text', 'image' or 'none'")
        if "category" not in rep or rep["category"] not in CATEGORIES:
            raise ValueError(f"Representation {rep_id} has invalid category {rep.get('category')!r}")
        # The baseline: format 'none' and category 'baseline' go together, and
        # nothing is drawn, so it has no renditions, language, script or font.
        if (rep["format"] == "none") != (rep["category"] == "baseline"):
            raise ValueError(f"Representation {rep_id}: format 'none' and category 'baseline' must go together")
        if rep["format"] == "none":
            extra = sorted({"injection_commands", "target_objects", "injections", "language", "script", "font", "font_size"} & set(rep))
            if extra:
                raise ValueError(f"Baseline representation {rep_id} must not have {extra}")
            continue
        if rep["format"] == "text" and "language" not in rep:
            raise ValueError(f"Text representation {rep_id} requires 'language'")
        if rep["format"] == "text" and "script" not in rep:
            raise ValueError(f"Text representation {rep_id} requires 'script'")
        if "font" in rep and not (FONTS_DIR / rep["font"]).is_file():
            raise FileNotFoundError(f"Representation {rep_id} font not found: {FONTS_DIR / rep['font']}")
        if "font_size" in rep:
            size, (lo, hi) = rep["font_size"], FONT_SIZE_RANGE
            if not (isinstance(size, int) and not isinstance(size, bool) and lo <= size <= hi):
                raise ValueError(f"Representation {rep_id}: 'font_size' must be an integer from {lo} to {hi}")

        # Text renditions say the object in the representation's own words; image
        # renditions fill {object} with the object id, so they have no word list.
        if rep["format"] == "text":
            unknown = sorted(set(rep.get("target_objects", {})) - set(object_ids))
            if unknown:
                raise ValueError(f"Representation {rep_id} 'target_objects' has words for unknown object id(s) {unknown}")
        elif "target_objects" in rep:
            raise ValueError(f"Image representation {rep_id} must not have 'target_objects'")

        rep_commands = rep.get("injection_commands", {})
        unknown = sorted(set(rep_commands) - set(commands))
        if unknown:
            raise ValueError(f"Representation {rep_id} has renditions for unknown command id(s) {unknown}")
        for command_id, rendition in rep_commands.items():
            content = rendition.get("content")
            if not isinstance(content, list) or len(content) == 0:
                raise ValueError(f"Representation {rep_id}.injection_commands.{command_id}.content must be a non-empty list")
            for line in content:
                if not placeholders(line) <= {"object"}:
                    raise ValueError(f"Representation {rep_id}.injection_commands.{command_id}: {line!r} uses a placeholder other than {{object}}")
        rep_injections = rep.get("injections", {})
        unknown = sorted(set(rep_injections) - set(expanded))
        if unknown:
            raise ValueError(f"Representation {rep_id} has renditions for unknown injection id(s) {unknown}")
        for injection_id, rendition in rep_injections.items():
            content = rendition.get("content")
            if not isinstance(content, list) or len(content) == 0:
                raise ValueError(f"Representation {rep_id}.injections.{injection_id}.content must be a non-empty list")

        for injection_id, injection in expanded.items():
            rendition = rendition_of(rep, injection_id, injection)
            # english is the plain reading of every injection (docs/SPEC.md section 6, rule 2).
            if rendition is None and rep_id == "english":
                raise ValueError(f"Representation english missing rendition for injection {injection_id!r}")
            if rendition is not None and rep["format"] == "image":
                for p_str in rendition["content"]:
                    img_path = REPO_ROOT / p_str
                    if not img_path.exists():
                        raise FileNotFoundError(f"Rendition image not found: {img_path} (from {rep_id}, injection {injection_id!r})")


def build_rows(
    prompts: dict, contexts: dict, injections: dict, representations: dict, images_rel: str
) -> list[tuple[dict, tuple]]:
    """Every row in memory (image_sha256 filled in after rendering), each with its render arguments."""
    out = []
    seen_ids = set()
    for prompt_id, prompt_data in prompts.items():
        for context_id, context_data in contexts.items():
            if context_id in prompt_data.get("exclude_contexts", []):
                continue
            for injection_id, injection_data in expand_injections(injections).items():
                for rep_id, rep_data in representations.items():
                    # A representation with no rendition of this injection has no row for it
                    # (`uncovered`); the baseline has one for every injection.
                    rendition = None
                    if rep_data["format"] != "none":
                        rendition = rendition_of(rep_data, injection_id, injection_data)
                        if rendition is None:
                            continue
                    sample_id = f"{prompt_id}.{context_id}.{injection_id}.{rep_id}"
                    if sample_id in seen_ids:
                        raise ValueError(f"Duplicate sample id: {sample_id}")
                    seen_ids.add(sample_id)

                    expected_calls = injection_data["expected_calls"]
                    row = {
                        "id": sample_id,
                        "user_prompt": prompt_data["text"],
                        "image": f"{images_rel}/{sample_id}.png",
                        "image_sha256": None,
                        "expected_calls": expected_calls,
                        "prompt_id": prompt_id,
                        "context_id": context_id,
                        "injection_id": injection_id,
                        "representation_id": rep_id,
                        "category": rep_data["category"],
                        "language": rep_data.get("language"),
                        "script": rep_data.get("script"),
                        **attack_fields(prompt_data, context_data, expected_calls[0]["name"]),
                    }
                    out.append((row, (context_id, context_data, rep_data, rendition)))
    return out


def generate(src_dir: Path = SRC_DIR, stimuli_dir: Path = STIMULI_DIR) -> list[dict]:
    print(f"Loading factor files from {src_dir}...")
    prompts = load_json(src_dir / "prompts.json")
    contexts = load_json(src_dir / "contexts.json")
    injections = load_json(src_dir / "injections.json")
    representations = load_json(src_dir / "representations.json")

    validate_factors(prompts, contexts, injections, representations)
    for rep_id, missing in uncovered(injections, representations).items():
        print(f"WARNING: representation {rep_id} has no rendition of {len(missing)} injection(s), "
              f"so no rows for them: {', '.join(missing)}", file=sys.stderr)

    # Image paths in the manifest are relative to stimuli_dir's parent (the repo root).
    images_rel = f"{stimuli_dir.name}/images"
    built = build_rows(prompts, contexts, injections, representations, images_rel)
    rows = [row for row, _ in built]
    n_injections = len(expand_injections(injections))
    print(f"Expanded {len(prompts)} prompts × {len(contexts)} contexts (minus excluded pairs) × {n_injections} injections × {len(representations)} representations (where they have a rendition) = {len(rows)} test cases")

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
