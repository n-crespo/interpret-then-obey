#!/usr/bin/env python3
"""
Stimulus generator for the interpret-then-obey benchmark per docs/SPEC.md.

Combines the 4 factors:
  prompts × contexts × injections × representations

Deterministically renders images to stimuli/images/<id>.png and writes
the harness-loadable manifest to stimuli/manifest.jsonl.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
STIMULI_DIR = REPO_ROOT / "stimuli"
SRC_DIR = STIMULI_DIR / "src"
FONTS_DIR = STIMULI_DIR / "fonts"
IMAGES_DIR = STIMULI_DIR / "images"
MANIFEST_JSONL = STIMULI_DIR / "manifest.jsonl"
MANIFEST_JSON = STIMULI_DIR / "manifest.json"

WIDTH, HEIGHT = 720, 460
INJECTION_BOX_TOP = 265
INJECTION_BOX_BOTTOM = 425


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a vendored DejaVu font with a layout engine that is the same on every platform.

    Pillow's default engine is RAQM when libraqm is available (Linux/macOS wheels) and
    BASIC when it is not (Windows wheels), and the two place glyphs differently. Forcing
    BASIC keeps pixels identical everywhere. BASIC does no bidi or complex shaping, which
    is fine while all rendered text is Latin (non-Latin scripts are pre-drawn assets).
    """
    font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    font_path = FONTS_DIR / font_name
    if not font_path.exists():
        raise FileNotFoundError(f"Missing vendored font: {font_path}")
    return ImageFont.truetype(str(font_path), size, layout_engine=ImageFont.Layout.BASIC)


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing factor file: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_factors(prompts: dict, contexts: dict, injections: dict, representations: dict) -> None:
    """Validate all requirements from docs/SPEC.md Section 8."""
    if not prompts:
        raise ValueError("prompts.json is empty")
    if not contexts:
        raise ValueError("context.json is empty")
    if not injections:
        raise ValueError("injections.json is empty")
    if not representations:
        raise ValueError("representations.json is empty")

    rep_keys = list(representations.keys())
    if rep_keys[0] != "english":
        raise ValueError(f"docs/SPEC.md Rule 1: 'english' must be the first representation, got {rep_keys[0]!r}")

    for rep_id, rep in representations.items():
        if "format" not in rep or rep["format"] not in ("text", "image"):
            raise ValueError(f"Representation {rep_id} must have format 'text' or 'image'")
        if "category" not in rep or rep["category"] not in ("natural", "constructed", "symbols"):
            raise ValueError(f"Representation {rep_id} has invalid category {rep.get('category')!r}")
        if rep["format"] == "text" and "language" not in rep:
            raise ValueError(f"Text representation {rep_id} requires 'language'")
        if rep["format"] == "text" and "script" not in rep:
            raise ValueError(f"Text representation {rep_id} requires 'script'")

        rep_injections = rep.get("injections", {})
        for inj_id in injections:
            if inj_id not in rep_injections:
                raise ValueError(f"Representation {rep_id} missing rendition for injection {inj_id!r}")
            rendition = rep_injections[inj_id]
            content = rendition.get("content")
            if not isinstance(content, list) or len(content) == 0:
                raise ValueError(f"Representation {rep_id}.injections.{inj_id}.content must be a non-empty list")
            if rep["format"] == "image":
                for p_str in content:
                    img_path = REPO_ROOT / p_str
                    if not img_path.exists():
                        raise FileNotFoundError(f"Rendition image not found: {img_path} (from {rep_id}.{inj_id})")


def render_stimulus_image(
    image_path: Path,
    context_id: str,
    context: dict,
    representation: dict,
    rendition: dict,
) -> None:
    """Render a stimulus image combining context content and the injection rendition."""
    # Palette based on context type
    if context_id == "info_board":
        bg_color = (244, 242, 238)
        border_color = (70, 75, 80)
        accent_color = (40, 70, 110)
        box_bg = (235, 233, 228)
        box_border = (180, 175, 170)
    elif context_id == "product_info":
        bg_color = (246, 248, 250)
        border_color = (60, 80, 100)
        accent_color = (30, 90, 140)
        box_bg = (238, 242, 246)
        box_border = (160, 180, 200)
    else:  # advertisement
        bg_color = (255, 250, 242)
        border_color = (180, 50, 40)
        accent_color = (190, 45, 35)
        box_bg = (252, 244, 232)
        box_border = (220, 180, 160)

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

    # 4. Render Injection Payload
    content = rendition["content"]
    if representation["format"] == "text":
        inj_font = get_font(size=28, bold=True)
        total_text_h = len(content) * 44
        box_h = INJECTION_BOX_BOTTOM - INJECTION_BOX_TOP
        start_y = INJECTION_BOX_TOP + max(20, (box_h - total_text_h) // 2)

        for idx, line in enumerate(content):
            # Center text horizontally in the box
            text_w = draw.textlength(line, font=inj_font)
            start_x = max(50, (WIDTH - text_w) // 2)
            draw.text((start_x, start_y + (idx * 44)), line, fill=(20, 20, 25), font=inj_font)

    elif representation["format"] == "image":
        # Load and paste pre-drawn asset centered in injection box
        asset_path = REPO_ROOT / content[0]
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


def generate():
    print("Loading factor files from stimuli/src/...")
    prompts = load_json(SRC_DIR / "prompts.json")
    contexts = load_json(SRC_DIR / "context.json")
    injections = load_json(SRC_DIR / "injections.json")
    representations = load_json(SRC_DIR / "representations.json")

    validate_factors(prompts, contexts, injections, representations)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    seen_ids = set()

    total_combinations = len(prompts) * len(contexts) * len(injections) * len(representations)
    print(f"Expanding factorial grid: {len(prompts)} prompts × {len(contexts)} contexts × {len(injections)} injections × {len(representations)} representations = {total_combinations} test cases")

    for prompt_id, prompt_data in prompts.items():
        for context_id, context_data in contexts.items():
            for injection_id, injection_data in injections.items():
                for rep_id, rep_data in representations.items():
                    sample_id = f"{prompt_id}.{context_id}.{injection_id}.{rep_id}"
                    if sample_id in seen_ids:
                        raise ValueError(f"Duplicate sample id: {sample_id}")
                    seen_ids.add(sample_id)

                    rel_image_path = f"stimuli/images/{sample_id}.png"
                    abs_image_path = REPO_ROOT / rel_image_path

                    rendition = rep_data["injections"][injection_id]

                    render_stimulus_image(
                        abs_image_path,
                        context_id,
                        context_data,
                        rep_data,
                        rendition,
                    )

                    image_sha256 = sha256_file(abs_image_path)

                    expected_item = injection_data["expected_item"]
                    row = {
                        "id": sample_id,
                        "user_prompt": prompt_data["text"],
                        "image": rel_image_path,
                        "image_sha256": image_sha256,
                        "expected_calls": [{"name": "buy", "args": {"item": expected_item}}],
                        "tools": ["buy"],
                        "prompt_id": prompt_id,
                        "context_id": context_id,
                        "injection_id": injection_id,
                        "representation_id": rep_id,
                        "category": rep_data["category"],
                        "language": rep_data.get("language"),
                        "script": rep_data.get("script"),
                    }
                    rows.append(row)

    # Write manifest.jsonl (Section 7)
    # newline="\n": text mode would write CRLF on Windows and the manifest would differ.
    with open(MANIFEST_JSONL, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    # Also write manifest.json array for convenience
    with open(MANIFEST_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rows, f, indent=2)

    print(f"Wrote {len(rows)} test cases to {MANIFEST_JSONL} and {MANIFEST_JSON}")

    # Self-validation: verify harness load and hashes
    print("Verifying manifest with harness.manifest.load_manifest(..., verify_hashes=True)...")
    sys.path.insert(0, str(REPO_ROOT))
    from harness.manifest import load_manifest
    loaded = load_manifest(MANIFEST_JSONL, verify_hashes=True)
    assert len(loaded) == len(rows), f"Loaded {len(loaded)} != expected {len(rows)}"
    print(f"SUCCESS: Verified all {len(loaded)} test cases and SHA-256 hashes cleanly!")


if __name__ == "__main__":
    generate()
