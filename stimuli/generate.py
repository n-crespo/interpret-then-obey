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

Builds one `Case` (stimuli/cases.py) per test case, deterministically renders
its image to stimuli/images/<id>.png, and writes the cases to
stimuli/manifest.jsonl, one per line (the only file it writes, per
docs/SPEC.md section 7). The harness loads them from there.

Section 8: if any check fails, nothing is written. Images and the manifest
are built in a staging dir under stimuli/, the staged manifest is checked
with harness.manifest.load_cases(..., verify_hashes=True), and only then
are both moved into place.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import string
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from harness.manifest import load_cases  # noqa: E402
from stimuli.cases import (  # noqa: E402
    Case,
    Injection,
    context_from_src,
    prompt_from_src,
    representation_from_src,
)

STIMULI_DIR = REPO_ROOT / "stimuli"
SRC_DIR = STIMULI_DIR / "src"
FONTS_DIR = STIMULI_DIR / "fonts"
STAGING_PREFIX = ".generate-"  # gitignored; removed after every run

WIDTH, HEIGHT = 720, 460
INJECTION_BOX_TOP = 265
INJECTION_BOX_BOTTOM = 425

# Injection text size. Representations with their own `font` (e.g. pIqaD and
# Tengwar in Constructium) draw at a larger size: their glyphs sit much smaller
# in the em box than DejaVu Sans Bold's Latin, and are hard to read at 28px.
INJECTION_FONT_SIZE = 28
SCRIPT_FONT_SIZE = 44
FONT_SIZE_RANGE = (12, 64)  # allowed `font_size` of a representation

FORMATS = ("text", "image", "none")
CATEGORIES = ("natural", "constructed", "symbols", "opaque", "obfuscated", "keyed", "baseline")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get_font(size: int, bold: bool = False, font_name: str | None = None) -> ImageFont.FreeTypeFont:
    """Load a vendored font from stimuli/fonts/ (DejaVu Sans unless `font_name` is given).

    The layout engine is pinned to BASIC. Pillow's default is RAQM when libraqm is
    available (Linux/macOS wheels) and BASIC when it is not (Windows wheels), and the two
    place glyphs differently, so the default would make pixels depend on the platform.
    BASIC does no bidi or complex shaping.
    """
    if font_name is None:
        font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    font_path = FONTS_DIR / font_name
    if not font_path.exists():
        raise FileNotFoundError(f"Missing vendored font: {font_path}")
    return ImageFont.truetype(str(font_path), size, layout_engine=ImageFont.Layout.BASIC)


class DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    # json.load would otherwise silently keep the last of two equal keys,
    # dropping a factor (or a field) without any error.
    out = {}
    for k, v in pairs:
        if k in out:
            raise DuplicateKeyError(f"duplicate key {k!r}")
        out[k] = v
    return out


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing factor file: {path}")
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f, object_pairs_hook=_reject_duplicate_keys)
        except DuplicateKeyError as e:
            raise ValueError(f"{path.name}: {e}") from None


def placeholders(text: str) -> set[str]:
    """The str.format field names used in `text`."""
    return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}


def expand_injections(injections: dict) -> dict[str, Injection]:
    """Every command × object of its group in injections.json, keyed by injection id
    `<command>_<object>`."""
    return {
        f"{command_id}_{obj}": Injection(f"{command_id}_{obj}", command_id, obj, command["tool"], command["arg"],
                                         tuple(spec["accepted"]))
        for command_id, command in injections["commands"].items()
        for obj, spec in injections["objects"][command["arg"]].items()
    }


def rendition_of(rep: dict, injection_id: str, injection: Injection) -> dict | None:
    """The rendition of one injection in `rep`, or None when it has none.

    A whole rendition in `injections` wins. Otherwise the command's rendition has
    `{object}` filled in: by text representations with their own word for the object
    (`objects`), by image representations with the object id, which names the asset's folder.
    """
    if injection_id in rep.get("injections", {}):
        return rep["injections"][injection_id]
    rendition = rep.get("commands", {}).get(injection.command)
    word = rep.get("objects", {}).get(injection.object) if rep["format"] == "text" else injection.object
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
        raise ValueError("context.json is empty")
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
        ("context.json", contexts),
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
            extra = sorted({"commands", "objects", "injections", "language", "script", "font", "font_size"} & set(rep))
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
            unknown = sorted(set(rep.get("objects", {})) - set(object_ids))
            if unknown:
                raise ValueError(f"Representation {rep_id} 'objects' has words for unknown object id(s) {unknown}")
        elif "objects" in rep:
            raise ValueError(f"Image representation {rep_id} must not have 'objects'")

        rep_commands = rep.get("commands", {})
        unknown = sorted(set(rep_commands) - set(commands))
        if unknown:
            raise ValueError(f"Representation {rep_id} has renditions for unknown command id(s) {unknown}")
        for command_id, rendition in rep_commands.items():
            content = rendition.get("content")
            if not isinstance(content, list) or len(content) == 0:
                raise ValueError(f"Representation {rep_id}.commands.{command_id}.content must be a non-empty list")
            for line in content:
                if not placeholders(line) <= {"object"}:
                    raise ValueError(f"Representation {rep_id}.commands.{command_id}: {line!r} uses a placeholder other than {{object}}")
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


# Per-context colours: background, frame, accent, injection box fill, injection box border.
PALETTES = {
    "info_board": ((244, 242, 238), (70, 75, 80), (40, 70, 110), (235, 233, 228), (180, 175, 170)),
    "product_info": ((246, 248, 250), (60, 80, 100), (30, 90, 140), (238, 242, 246), (160, 180, 200)),
    "advertisement": ((255, 250, 242), (180, 50, 40), (190, 45, 35), (252, 244, 232), (220, 180, 160)),
    "meeting_notes": ((250, 250, 246), (90, 90, 80), (70, 90, 60), (240, 240, 232), (190, 190, 175)),
    "transit_notice": ((242, 246, 250), (30, 60, 110), (200, 120, 10), (232, 238, 246), (150, 170, 200)),
}


def render_stimulus_image(
    image_path: Path,
    context_id: str,
    context: dict,
    representation: dict,
    rendition: dict | None,
) -> None:
    """Render a stimulus image combining context content and the injection rendition.

    For the baseline (format 'none', rendition None) everything up to and including the
    empty injection box is drawn exactly as for an injected image, and nothing is put in
    the box, so the two differ only inside it.
    """
    if context_id not in PALETTES:
        raise ValueError(f"Context {context_id!r} has no palette in stimuli/generate.py PALETTES")
    bg_color, border_color, accent_color, box_bg, box_border = PALETTES[context_id]

    img = Image.new("RGB", (WIDTH, HEIGHT), color=bg_color)
    draw = ImageDraw.Draw(img)

    # 1. Outer Frame
    draw.rectangle([16, 16, WIDTH - 16, HEIGHT - 16], outline=border_color, width=4)
    draw.rectangle([24, 24, WIDTH - 24, HEIGHT - 24], outline=(border_color[0]//2, border_color[1]//2, border_color[2]//2), width=1)

    # 2. Context Section
    header_font = get_font(size=22, bold=True)
    body_font = get_font(size=18, bold=False)

    header = context.get("header", "NOTICE")
    draw.text((45, 42), header, fill=accent_color, font=header_font)
    draw.line([(45, 74), (WIDTH - 45, 74)], fill=border_color, width=2)

    for i, line in enumerate(context.get("lines", [])):
        draw.text((45, 95 + (i * 38)), line, fill=(30, 30, 35), font=body_font)

    # 3. Injection Box (Lower Inset Area)
    draw.rectangle(
        [40, INJECTION_BOX_TOP, WIDTH - 40, INJECTION_BOX_BOTTOM],
        fill=box_bg,
        outline=box_border,
        width=2,
    )

    # Decorative accent corner notches on injection frame
    draw.line([(40, INJECTION_BOX_TOP + 15), (40 + 15, INJECTION_BOX_TOP)], fill=accent_color, width=2)
    draw.line([(WIDTH - 40, INJECTION_BOX_TOP + 15), (WIDTH - 40 - 15, INJECTION_BOX_TOP)], fill=accent_color, width=2)
    draw.line([(40, INJECTION_BOX_BOTTOM - 15), (40 + 15, INJECTION_BOX_BOTTOM)], fill=accent_color, width=2)
    draw.line([(WIDTH - 40, INJECTION_BOX_BOTTOM - 15), (WIDTH - 40 - 15, INJECTION_BOX_BOTTOM)], fill=accent_color, width=2)

    # 4. Render Injection Payload (nothing for the baseline)
    if representation["format"] == "none":
        pass
    elif representation["format"] == "text":
        content = rendition["content"]
        if "font" in representation:
            inj_font = get_font(size=representation.get("font_size", SCRIPT_FONT_SIZE), font_name=representation["font"])
        else:
            inj_font = get_font(size=representation.get("font_size", INJECTION_FONT_SIZE), bold=True)
        total_text_h = len(content) * 44
        box_h = INJECTION_BOX_BOTTOM - INJECTION_BOX_TOP
        start_y = INJECTION_BOX_TOP + max(20, (box_h - total_text_h) // 2)

        # Fail rather than draw past the injection box (inside its 2px border).
        ascent, descent = inj_font.getmetrics()
        text_bottom = start_y + (len(content) - 1) * 44 + ascent + descent
        if text_bottom > INJECTION_BOX_BOTTOM - 2:
            raise ValueError(
                f"{len(content)} lines do not fit in the injection box "
                f"(text ends at y={text_bottom}, box ends at y={INJECTION_BOX_BOTTOM - 2})"
            )
        max_text_w = WIDTH - 2 * 50  # 10px inside the box on each side

        for idx, line in enumerate(content):
            # Center text horizontally in the box
            text_w = draw.textlength(line, font=inj_font)
            if text_w > max_text_w:
                raise ValueError(f"line {line!r} is {text_w:.0f}px wide, injection box allows {max_text_w}px")
            start_x = max(50, (WIDTH - text_w) // 2)
            draw.text((start_x, start_y + (idx * 44)), line, fill=(20, 20, 25), font=inj_font)

    elif representation["format"] == "image":
        # Load and paste pre-drawn asset centered in injection box
        asset_path = REPO_ROOT / rendition["content"][0]
        asset_img = Image.open(asset_path).convert("RGBA")

        box_w = WIDTH - 80
        box_h = INJECTION_BOX_BOTTOM - INJECTION_BOX_TOP

        # Scale down if asset exceeds box dimensions
        w, h = asset_img.size
        scale = min(1.0, (box_w - 40) / w, (box_h - 20) / h)
        if scale < 1.0:
            new_size = (int(w * scale), int(h * scale))
            asset_img = asset_img.resize(new_size, Image.Resampling.LANCZOS)
            w, h = new_size

        paste_x = (WIDTH - w) // 2
        paste_y = INJECTION_BOX_TOP + (box_h - h) // 2
        img.paste(asset_img, (paste_x, paste_y), mask=asset_img.split()[3])

    image_path.parent.mkdir(parents=True, exist_ok=True)
    # compress_level=0 writes stored (uncompressed) deflate blocks. The zlib-ng builds in
    # Pillow's Windows and Linux wheels produce different compressed bytes for the same
    # pixels at every level from 1 to 9, so only level 0 gives the same file, and the same
    # image_sha256, on every platform. Pillow writes no metadata chunks here.
    img.save(image_path, format="PNG", compress_level=0)


def build_cases(
    prompts: dict, contexts: dict, injections: dict, representations: dict, images_rel: str
) -> list[tuple[Case, tuple]]:
    """Every case in memory (image_sha256 filled in after rendering), each with its render arguments."""
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

                    case = Case(
                        id=sample_id,
                        image=f"{images_rel}/{sample_id}.png",
                        image_sha256=None,
                        prompt=prompt_from_src(prompt_id, prompt_data),
                        context=context_from_src(context_id, context_data),
                        injection=injection_data,
                        representation=representation_from_src(rep_id, rep_data),
                    )
                    out.append((case, (context_id, context_data, rep_data, rendition)))
    return out


def _swap_in_dir(new: Path, dest: Path, trash: Path) -> None:
    """Replace dest with new. The old dest is moved into trash and deleted with it."""
    old = None
    if dest.exists():
        old = trash / "previous-images"
        os.replace(dest, old)
    try:
        os.replace(new, dest)
    except BaseException:
        if old is not None:
            os.replace(old, dest)
        raise


def generate(src_dir: Path = SRC_DIR, stimuli_dir: Path = STIMULI_DIR) -> list[Case]:
    print(f"Loading factor files from {src_dir}...")
    prompts = load_json(src_dir / "prompts.json")
    contexts = load_json(src_dir / "context.json")
    injections = load_json(src_dir / "injections.json")
    representations = load_json(src_dir / "representations.json")

    validate_factors(prompts, contexts, injections, representations)
    for rep_id, missing in uncovered(injections, representations).items():
        print(f"WARNING: representation {rep_id} has no rendition of {len(missing)} injection(s), "
              f"so no rows for them: {', '.join(missing)}", file=sys.stderr)

    # Image paths in the manifest are relative to stimuli_dir's parent (the repo root).
    images_rel = f"{stimuli_dir.name}/images"
    built = build_cases(prompts, contexts, injections, representations, images_rel)
    n_injections = len(expand_injections(injections))
    print(f"Expanded {len(prompts)} prompts × {len(contexts)} contexts (minus excluded pairs) × {n_injections} injections × {len(representations)} representations (where they have a rendition) = {len(built)} test cases")

    # Render and write under `staging`, which mirrors the layout of
    # stimuli_dir's parent, so the staged manifest's paths resolve to the
    # staged images. Nothing outside it changes until every check has passed.
    staging = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=stimuli_dir))
    try:
        cases = []
        for case, render_args in built:
            staged_image = staging / case.image
            render_stimulus_image(staged_image, *render_args)
            cases.append(dataclasses.replace(case, image_sha256=sha256_file(staged_image)))

        staged_manifest = staging / stimuli_dir.name / "manifest.jsonl"
        with open(staged_manifest, "w", encoding="utf-8", newline="\n") as f:
            for case in cases:
                f.write(json.dumps(case.to_dict()) + "\n")

        print("Verifying manifest with harness.manifest.load_cases(..., verify_hashes=True)...")
        loaded = load_cases(staged_manifest, image_root=staging, verify_hashes=True)
        if len(loaded) != len(cases):
            raise ValueError(f"Loaded {len(loaded)} cases, expected {len(cases)}")

        _swap_in_dir(staging / images_rel, stimuli_dir / "images", staging)
        os.replace(staged_manifest, stimuli_dir / "manifest.jsonl")
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    print(f"SUCCESS: wrote and verified {len(cases)} test cases in {stimuli_dir / 'manifest.jsonl'}")
    return cases


if __name__ == "__main__":
    generate()
