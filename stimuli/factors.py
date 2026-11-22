"""The factor files in stimuli/src/ (docs/SPEC.md): loading, validating, and expanding
injections into their renditions.

Injections are injection commands × target objects: each command takes the objects of
one type (`object_type`, also the argument of its tool that the object fills), giving one
injection per pair, id `<command>_<object>`. A representation renders an injection by
filling `{object}` (str.format syntax) in its rendition of the command, or gives a whole
rendition of the injection (`injections`).
"""

from __future__ import annotations

import inspect
import string
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from harness.tools import TOOLS  # noqa: E402
from stimuli.files import load_json  # noqa: E402
from stimuli.render import FONT_SIZE_RANGE, FONTS_DIR  # noqa: E402
from stimuli.schema import (  # noqa: E402
    Context, Factors, Injection, InjectionCommand, Prompt, Rendition, Representation, TargetObject,
)

SRC_DIR = REPO_ROOT / "stimuli" / "src"

FORMATS = ("text", "image", "none")
CATEGORIES = ("natural", "constructed", "symbols", "opaque", "obfuscated", "keyed", "baseline")
FILES = ("prompts", "contexts", "target_objects", "injection_commands", "representations")


def load_factors(src_dir: Path = SRC_DIR) -> Factors:
    """The five factor files, validated."""
    raw = {name: load_json(src_dir / f"{name}.json") for name in FILES}
    validate(raw)
    f = _build(raw)
    # english is the plain reading of every injection (docs/SPEC.md section 6, rule 2).
    missing = [i.id for i in expand_injections(f).values() if rendition_of(f.representations["english"], i) is None]
    if missing:
        raise ValueError(f"Representation english has no rendition of {missing}")
    return f


def _rendition(r: dict) -> Rendition:
    return Rendition(tuple(r["content"]), r.get("notes"))


def _build(raw: dict) -> Factors:
    """Validated factor files -> typed factors."""
    reps = {}
    for rid, r in raw["representations"].items():
        reps[rid] = Representation(
            id=rid, format=r["format"], category=r["category"], language=r.get("language"),
            script=r.get("script"), font=r.get("font"), font_size=r.get("font_size"), notes=r.get("notes"),
            injection_commands={k: _rendition(v) for k, v in r.get("injection_commands", {}).items()},
            target_objects=dict(r.get("target_objects", {})),
            injections={k: _rendition(v) for k, v in r.get("injections", {}).items()},
        )
    return Factors(
        prompts={pid: Prompt(pid, p["text"], p["expected_tool"], p.get("object"), tuple(p.get("exclude_contexts", [])))
                 for pid, p in raw["prompts"].items()},
        contexts={cid: Context(cid, c["header"], tuple(c["lines"]), c["item"]) for cid, c in raw["contexts"].items()},
        target_objects={oid: TargetObject(oid, kind, tuple(o["accepted_items"]))
                        for kind, group in raw["target_objects"].items() for oid, o in group.items()},
        injection_commands={cid: InjectionCommand(cid, c["object_type"], c["expected_tool"])
                            for cid, c in raw["injection_commands"].items()},
        representations=reps,
    )


def placeholders(text: str) -> set[str]:
    """The str.format field names used in `text`."""
    return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}


def expand_injections(f: Factors) -> dict[str, Injection]:
    """Every command × target object of its type, keyed by injection id `<command>_<object>`."""
    out = {}
    for command in f.injection_commands.values():
        for obj in f.target_objects.values():
            if obj.type == command.object_type:
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


def _is_item_list(x) -> bool:
    """A non-empty list of non-empty strings: the shape of every `accepted_items`."""
    return isinstance(x, list) and bool(x) and all(isinstance(a, str) and a.strip() for a in x)


def _tool_args(name: str) -> list[str]:
    """The arguments of a harness tool (harness/tools/mock_tools.py)."""
    return list(inspect.signature(TOOLS[name]()).parameters)


def _check_content(where: str, rendition: dict) -> None:
    content = rendition.get("content")
    if not isinstance(content, list) or not content:
        raise ValueError(f"{where}.content must be a non-empty list")
    for line in content:
        if not placeholders(line) <= {"object"}:
            raise ValueError(f"{where}: {line!r} uses a placeholder other than {{object}}")


def validate(raw: dict) -> None:
    """The rules of docs/SPEC.md sections 3 to 6 and 8 on the loaded factor files (file
    name without .json -> contents). Raises on the first broken one."""
    for name in FILES:
        if not raw[name]:
            raise ValueError(f"{name}.json is empty")
    target_objects, commands = raw["target_objects"], raw["injection_commands"]

    object_ids: list[str] = []
    for kind, group in target_objects.items():
        if not isinstance(group, dict) or not group:
            raise ValueError(f"target_objects.json: {kind} must be a non-empty object keyed by object id")
        for obj, spec in group.items():
            if set(spec) != {"accepted_items"} or not _is_item_list(spec["accepted_items"]):
                raise ValueError(f"target_objects.json: {obj!r} must have exactly 'accepted_items', a non-empty list of non-empty strings")
        object_ids += group
    duplicates = sorted({o for o in object_ids if object_ids.count(o) > 1})
    if duplicates:
        raise ValueError(f"target_objects.json: object id(s) {duplicates} appear under more than one type")

    # Sample ids join factor ids with '.', so a '.' inside one could make two
    # combinations collide (a.b + c vs a + b.c) and would make ids ambiguous to split.
    for name in ("prompts", "contexts", "injection_commands", "representations"):
        for fid in raw[name]:
            if not isinstance(fid, str) or not fid or "." in fid:
                raise ValueError(f"{name}.json: id {fid!r} must be non-empty and must not contain '.'")
    for fid in object_ids:
        if not fid or "." in fid:
            raise ValueError(f"target_objects.json: id {fid!r} must be non-empty and must not contain '.'")

    for command_id, command in commands.items():
        if set(command) != {"object_type", "expected_tool"}:
            raise ValueError(f"injection_commands.json: {command_id!r} must have exactly 'object_type' and 'expected_tool'")
        if command["expected_tool"] not in TOOLS:
            raise ValueError(f"injection_commands.json: {command_id!r} 'expected_tool' must be one of harness.tools.TOOLS {list(TOOLS)}")
        if command["object_type"] not in target_objects:
            raise ValueError(f"injection_commands.json: {command_id!r} 'object_type' must be one of {sorted(target_objects)}")
        if command["object_type"] not in _tool_args(command["expected_tool"]):
            raise ValueError(f"injection_commands.json: {command_id!r} 'object_type' must be an argument of the tool "
                             f"{command['expected_tool']!r}: {_tool_args(command['expected_tool'])}")

    for prompt_id, prompt in raw["prompts"].items():
        unknown_keys = sorted(set(prompt) - {"text", "expected_tool", "object", "exclude_contexts"})
        if unknown_keys or not isinstance(prompt.get("text"), str) or "expected_tool" not in prompt:
            raise ValueError(f"Prompt {prompt_id} must have 'text' and 'expected_tool', and may have 'object' and 'exclude_contexts'")
        if prompt["expected_tool"] is not None and prompt["expected_tool"] not in TOOLS:
            raise ValueError(f"Prompt {prompt_id}: 'expected_tool' must be null or one of harness.tools.TOOLS {list(TOOLS)}")
        if "object" in prompt and prompt["object"] not in object_ids:
            raise ValueError(f"Prompt {prompt_id}: 'object' must be a target object id")
        excluded = prompt.get("exclude_contexts", [])
        if not isinstance(excluded, list) or not all(isinstance(c, str) for c in excluded):
            raise ValueError(f"Prompt {prompt_id}: 'exclude_contexts' must be a list of context ids")
        unknown = sorted(set(excluded) - set(raw["contexts"]))
        if unknown:
            raise ValueError(f"Prompt {prompt_id} excludes unknown context id(s) {unknown}")

    for context_id, context in raw["contexts"].items():
        if set(context) != {"header", "lines", "item"}:
            raise ValueError(f"Context {context_id} must have exactly 'header', 'lines' and 'item'")
        if not (context["item"] is None or context["item"] in object_ids):
            raise ValueError(f"Context {context_id}: 'item' must be a target object id or null")

    if next(iter(raw["representations"])) != "english":
        raise ValueError("docs/SPEC.md section 6, rule 1: 'english' must be the first representation")
    expanded = {f"{c}_{o}" for c, command in commands.items() for o in target_objects[command["object_type"]]}
    for rep_id, rep in raw["representations"].items():
        if rep.get("format") not in FORMATS:
            raise ValueError(f"Representation {rep_id} must have format {FORMATS}")
        if rep.get("category") not in CATEGORIES:
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
        if rep["format"] == "text" and not ("language" in rep and "script" in rep):
            raise ValueError(f"Text representation {rep_id} requires 'language' and 'script'")
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

        for command_id, rendition in rep.get("injection_commands", {}).items():
            if command_id not in commands:
                raise ValueError(f"Representation {rep_id} has a rendition of unknown command {command_id!r}")
            _check_content(f"{rep_id}.injection_commands.{command_id}", rendition)
        for injection_id, rendition in rep.get("injections", {}).items():
            if injection_id not in expanded:
                raise ValueError(f"Representation {rep_id} has a rendition of unknown injection {injection_id!r}")
            _check_content(f"{rep_id}.injections.{injection_id}", rendition)
            if rep["format"] == "image":
                for p in rendition["content"]:
                    if not (REPO_ROOT / p).is_file():
                        raise FileNotFoundError(f"Rendition image not found: {REPO_ROOT / p} (from {rep_id}, injection {injection_id!r})")
